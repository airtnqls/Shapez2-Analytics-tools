import traceback
from typing import List, Tuple, Dict, Optional, Callable

# 순환 참조를 피하기 위해 shape 관련 import는 함수 내부로 이동합니다.
from shape import Shape, Layer, Quadrant

# --- 로깅 시스템 ---
_log_callback: Optional[Callable[[str], None]] = None

def _log(message: str):
    """로그 메시지를 출력합니다. GUI 콜백이 설정되어 있으면 GUI로 전송합니다."""
    # _log_callback이 None이면 아무것도 출력하지 않고, 아니면 콜백을 호출합니다.
    if _log_callback is not None:
        _log_callback(message)


# --- 상수 정의 ---
_VALID_SHAPE_CHARS = set('CSRWcPrgbmyuw-:')
_MAX_SHAPE_CODE_LENGTH = 100
_GENERAL_SHAPE_TYPES = {'C', 'R', 'S', 'W'} # 이 일반도형은 S라 불립니다.
_BLOCKER_SHAPE_TYPES = _GENERAL_SHAPE_TYPES.union({'P'})
_INVALID_ADJACENCY_SHAPES = _GENERAL_SHAPE_TYPES.union({'c'}) # 새로운 상수 추가
# S 는 일반 도형입니다.
# - 는 빈 공간입니다.
# c 는 크리스탈 입니다.
# P 는 핀 입니다.


class _ClawLogicError(Exception):
    """Claw 처리 중 논리 오류 발생 시 조기 종료를 위한 사용자 정의 예외"""
    pass


# --- 공통 유틸 (중복 코드 함수화: 동작 동일, 가독성만 개선) ---

def _ensure_layer(shape: Shape, l: int):
    """레이어 인덱스 l까지 존재하도록 확장"""
    while len(shape.layers) <= l:
        shape.layers.append(Layer([None]*4))

def _get(shape: Shape, l: int, q: int):
    """조각 읽기(기존 _get_piece 호출 래핑: 호출부 간결화)"""
    return shape._get_piece(l, q)

def _set(shape: Shape, l: int, q: int, piece: Quadrant | None):
    """조각 쓰기(필요시 레이어 확장 포함)"""
    _ensure_layer(shape, l)
    shape.layers[l].quadrants[q] = piece

def _adj2(shape: Shape, q: int) -> list[int]:
    """사분면 q의 인접 2개 반환(기존 패턴 래핑)"""
    return [aq for aq in range(4) if shape._is_adjacent(q, aq)]

def _copy_without(shape: Shape, coords: list[tuple[int,int]]) -> Shape:
    """coords 위치를 None으로 비운 사본 생성(임시 검증용)"""
    s = shape.copy()
    for l, q in coords:
        if 0 <= l < len(s.layers):
            s.layers[l].quadrants[q] = None
    return s

def _range_top_down(max_exclusive: int):
    """range(max_exclusive-1, -1, -1) 래퍼: 가독성"""
    return range(max_exclusive - 1, -1, -1)

def _sky_open_above(shape: Shape, l: int, q: int) -> bool:
    """_is_sky_open_above와 동일 동작을 1줄 호출로"""
    for l_check in range(l + 1, Shape.MAX_LAYERS):
        if shape._get_piece(l_check, q) is not None:
            return False
    return True

def _adjacent_coords(shape: Shape, l: int, q: int) -> list[tuple[int,int]]:
    """같은 층 인접 2칸의 좌표 튜플 리스트"""
    return [(l, aq) for aq in _adj2(shape, q)]


# --- 로직 헬퍼 함수들 ---

def _validate_shape_code(shape_code: str):
    if not all(char in _VALID_SHAPE_CHARS for char in shape_code) or len(shape_code) > _MAX_SHAPE_CODE_LENGTH:
        raise _ClawLogicError(f"DEBUG_ERROR: 잘못된 도형 코드 형식이거나 너무 깁니다.")

def _get_static_info(shape: Shape) -> Tuple[List[int], int, int]:
    if not shape.layers: raise _ClawLogicError("DEBUG_ERROR: 빈 도형입니다.")
    pins = [q for q, p in enumerate(shape.layers[0].quadrants) if p and p.shape == 'P']
    highest_c_info = (-1, -1)
    for l_idx in range(len(shape.layers) - 1, -1, -1):
        c_in_layer = [q for q, p in enumerate(shape.layers[l_idx].quadrants) if p and p.shape == 'c']
        if c_in_layer:
            if len(c_in_layer) > 1: raise _ClawLogicError(f"DEBUG_ERROR: 최고층 'c'가 2개 초과.")
            highest_c_info = (l_idx, c_in_layer[0])
            break
    if len(pins) < 1: raise _ClawLogicError(f"DEBUG_ERROR: 최하단층에 'P' 조각이 1개 미만입니다.")
    if highest_c_info[0] == -1: raise _ClawLogicError("DEBUG_ERROR: 도형에 'c' 조각이 없습니다.")
    return pins, highest_c_info[0], highest_c_info[1] # 최고층 크리스탈 층 정보 추가 반환

def _find_s_star_group(start_q: int, shape: Shape) -> List[Tuple[int, int]]:
    """설명해주신 규칙에 따라 -S를 중심으로 그룹을 찾습니다. (탐색 범위 제한)"""
    group = set()
    q_to_process = [(1, start_q)] # Start at layer 1 for -S
    _log(f"DEBUG: _find_s_star_group 호출됨. 시작: (1, {start_q})")

    # 탐색 허용 범위 계산
    valid_search_coords = set()
    valid_search_coords.add((1, start_q)) # 시작점
    
    # 시작점의 바로 옆 (현재 레이어)
    for adj_q_initial in _adj2(shape, start_q):
        valid_search_coords.add((1, adj_q_initial))
        # 시작점 옆의 바로 위 (다음 레이어)
        valid_search_coords.add((2, adj_q_initial))
    
    # 시작점의 바로 위 (다음 레이어)
    valid_search_coords.add((2, start_q))

    _log(f"DEBUG: _find_s_star_group - 허용된 탐색 범위: {sorted(list(valid_search_coords))}")

    while q_to_process:
        l, q = q_to_process.pop(0)
        if (l, q) in group:
            _log(f"DEBUG: ({l}, {q}) 이미 그룹에 있음. 건너뜀.")
            continue

        current_piece = _get(shape, l, q)
        if not (current_piece and current_piece.shape in _BLOCKER_SHAPE_TYPES): # S 또는 P 조각이 그룹의 일부가 될 수 있음
            _log(f"DEBUG: ({l}, {q}) 조각이 일반 도형 또는 P가 아님. 건너뜀.")
            continue

        group.add((l, q))
        _log(f"DEBUG: ({l}, {q}) 그룹에 추가됨. 현재 그룹: {sorted(list(group))}")

        for (adj_l, adj_q) in _adjacent_coords(shape, l, q):
            # Rule A and B: Apply to adjacent pieces at the *current layer* (l)
            adj_piece = _get(shape, adj_l, adj_q)
            
            # 여기서 큐에 추가할 때 valid_search_coords 확인
            if adj_piece and adj_piece.shape in _GENERAL_SHAPE_TYPES: # Found an adjacent general shape
                blocker = _get(shape, l + 1, adj_q)
                
                # Rule A: Adjacent S (adj_piece) at current layer (l) has empty space directly above
                if blocker is None:
                    if (l, adj_q) not in group and (l, adj_q) in valid_search_coords: # 범위 내에 있고 그룹에 없으면 추가
                        _log(f"DEBUG: 규칙 A - 인접 ({l}, {adj_q}) 조각 ({adj_piece.shape}) 위가 비어있음. 탐색 큐에 추가 (범위 내).")
                        q_to_process.append((l, adj_q))
                    elif (l, adj_q) not in valid_search_coords:
                        _log(f"DEBUG: 규칙 A - 인접 ({l}, {adj_q}) 조각 ({adj_piece.shape}) 범위 밖. 건너뜀.")
                # Rule B: Adjacent S (adj_piece) at current layer (l) is blocked by S/P, and that blocker's top is empty
                elif blocker.shape in _BLOCKER_SHAPE_TYPES and _get(shape, l + 2, adj_q) is None:
                    if (l, adj_q) not in group and (l, adj_q) in valid_search_coords: # 범위 내에 있고 그룹에 없으면 추가
                        _log(f"DEBUG: 규칙 B - 인접 ({l}, {adj_q}) 조각 ({adj_piece.shape}) 위 ({blocker.shape})가 막혔고, 그 위가 비었음. 탐색 큐에 추가 (범위 내).")
                        q_to_process.append((l, adj_q))
                    elif (l, adj_q) not in valid_search_coords:
                        _log(f"DEBUG: 규칙 B - 인접 ({l}, {adj_q}) 조각 ({adj_piece.shape}) 범위 밖. 건너뜀.")

                    if (l + 1, adj_q) not in group and (l + 1, adj_q) in valid_search_coords: # 블로커도 범위 내에 있고 그룹에 없으면 추가
                        _log(f"DEBUG: 규칙 B - 블로커 ({l+1}, {adj_q}) 조각 ({blocker.shape})도 그룹에 추가. 탐색 큐에 추가 (범위 내)." )
                        q_to_process.append((l + 1, adj_q))
                    elif (l + 1, adj_q) not in valid_search_coords:
                        _log(f"DEBUG: 규칙 B - 블로커 ({l+1}, {adj_q}) 조각 ({blocker.shape}) 범위 밖. 건너뜀.")
    
    _log(f"DEBUG: _find_s_star_group 종료. 최종 그룹: {sorted(list(group))}")
    return sorted(list(group))

def _count_empty_above(l: int, q: int, shape: Shape, ignored_coords: set[Tuple[int, int]] = None) -> int:
    count = 0
    if ignored_coords is None:
        ignored_coords = set()
    for l_check in range(l + 1, Shape.MAX_LAYERS):
        piece = _get(shape, l_check, q)
        if piece is None or (l_check, q) in ignored_coords: # If piece is None or it's one of the ignored (group's own) pieces
            count += 1
        else:
            break # Found a blocking piece that is NOT part of the group
    return count

def _is_sky_open_above(shape: Shape, current_l: int, current_q: int) -> bool:
    """주어진 층과 사분면 위로 하늘이 완전히 뚫려 있는지 확인합니다."""
    return _sky_open_above(shape, current_l, current_q)

def _move_s_group(group: List[Tuple[int, int]], shape: Shape, ref_shape: Shape, highest_c_layer: int, c_quad_idx: int):
    """
    그룹을 새로운 규칙에 따라 이동시킵니다.
    1. 각 그룹 사분면의 상단 빈 공간 최소값만큼 일괄 상향 이동.
    2. 이동 후, 유효한 인접 조건(양쪽에 S가 아닌 그룹 외 S가 없을 것)을 만족할 때까지 하향 이동.
    """

    if not group: return
    if len(group) == 1:
        _log(f"DEBUG: 그룹에 단 하나의 요소만 있어 이동하지 않습니다: {group}")
        return

    # 그룹의 원본 위치를 set으로 저장하여 빠른 조회를 위함 (_count_empty_above에서 무시할 좌표)
    original_group_coords = {(l, q) for l, q in group}

    # 1. 각 사분면별 그룹 조각 중 가장 높은 층의 조각 찾기
    highest_layer_per_quadrant_in_group = {}
    for l, q in group:
        if q not in highest_layer_per_quadrant_in_group or l > highest_layer_per_quadrant_in_group[q][0]:
            highest_layer_per_quadrant_in_group[q] = (l, q)
            _log(f"DEBUG: 각 사분면의 그룹 최고층 조각: {highest_layer_per_quadrant_in_group}")

    # 2. 초기 상향 이동 거리 결정 (각 그룹 대표 조각 위에 연속된 빈 공간의 최솟값)
    min_continuous_empty_above = float('inf')
    if not highest_layer_per_quadrant_in_group: # Should not happen if group is not empty
        min_continuous_empty_above = 0
    else:
        for l_highest, q_highest in highest_layer_per_quadrant_in_group.values():
            # 수정된 _count_empty_above 호출: 그룹의 원본 위치를 무시하도록 전달
            empty_count = _count_empty_above(l_highest, q_highest, ref_shape, original_group_coords)
            min_continuous_empty_above = min(min_continuous_empty_above, empty_count)

    initial_shift = min_continuous_empty_above
    _log(f"DEBUG: 그룹 {group}의 초기 이동 거리 (최소 연속 빈 공간): {initial_shift}")

    # 2. 유효한 위치를 찾을 때까지 하향 이동 반복
    # current_shift는 최종적으로 적용될 상대적인 이동 거리 (original layer + current_shift = final layer)
    # initial_shift에서 시작하여 필요하면 1씩 감소합니다.
    current_relative_shift = initial_shift
    
    while True:
        if current_relative_shift < 0: # Prevent going below original layer
            current_relative_shift = 0
            _log(f"DEBUG: 0층 아래로 내려갈 수 없음. 최종 유효 이동 거리: {current_relative_shift}")
            break # Stop descending if we hit the bottom

        # 유효성 검사용 임시 도형 생성: working_shape에서 그룹 조각들을 제거한 상태
        temp_shape_for_validation = _copy_without(shape, group)
        _log(f"DEBUG: 유효성 검사용 임시 도형 (그룹 조각 제거 후): {repr(temp_shape_for_validation)}")

        # 가상 이동된 그룹의 위치를 계산
        hypothetical_group_positions = {(l_orig + current_relative_shift, q_orig) for l_orig, q_orig in group}
        _log(f"DEBUG: 가상 그룹 위치: {hypothetical_group_positions}")

        # Check validity based on the rule: "각 그룹의 S들의 양쪽에 그룹이 아닌 S가 하나라도 있을 경우, 그 위치는 허용되지않은 위치이므로, 한칸 내립니다."
        is_current_position_valid = True # 이 플래그는 유효성 검사에만 사용하며, 하향 이동 중단에 사용하지 않음.
        should_descend_further = False # 유효하지 않은 인접성이 발견되면 True로 설정하여 하향 이동을 계속 유도
        
        # 현재 그룹의 모든 조각이 새로운 가상 위치로 이동했을 때의 유효성 검사.
        for l_orig, q_orig in group:
            l_hypo, q_hypo = l_orig + current_relative_shift, q_orig

            # 이동할 위치가 이미 막혀있는지 확인
            # 그룹의 원본 조각이 이동할 위치에 있으면 안되지만, 이는 이미 `temp_shape_for_validation`에서 제거된 상태.
            # 따라서 `temp_shape_for_validation`에서 해당 가상 위치에 다른 조각이 있는지 확인.
            if _is_position_blocked(temp_shape_for_validation, l_hypo, q_hypo):
                _log(f"DEBUG: _move_s_group: 가상 위치 ({l_hypo}, {q_hypo})가 다른 조각으로 막혀있음. 하향 이동 필요.")
                should_descend_further = True
                break # 막혀있으면 이 시도는 유효하지 않으므로 바로 다음 층으로

            original_piece_type = _get(ref_shape, l_orig, q_orig)
            if original_piece_type and original_piece_type.shape in _GENERAL_SHAPE_TYPES: # 'S' (일반 도형) 조각만 인접 검사
                if not _check_s_placement_validity(temp_shape_for_validation, l_hypo, q_hypo, hypothetical_group_positions, highest_c_layer, c_quad_idx): # highest_c_layer, c_quad_idx 추가 전달
                    _log(f"DEBUG: _move_s_group: S ({l_hypo}, {q_hypo})의 인접성 유효성 검사 실패. 하향 이동 필요.")
                    is_current_position_valid = False # 인접성 문제 발생
                    should_descend_further = True # 인접성 문제도 하향 이동을 유도
            
        if not should_descend_further and is_current_position_valid: # 모든 조각이 유효하고 막힌 곳이 없는 경우
            _log(f"DEBUG: 유효성 검사 통과. 최종 상대 이동 거리: {current_relative_shift}")
            break # Found a valid position, exit descent loop
        else:
            current_relative_shift -= 1 # Move down one layer and re-check
            _log(f"DEBUG: 유효성 검사 실패 또는 막힌 위치 발견. 한 칸 내림. 새 상대 이동: {current_relative_shift}")

    final_shift = current_relative_shift # This is the final net shift from original position

    # 적합한 위치를 찾지 못했다면 이동하지 않음.
    if final_shift < 0:
        _log(f"DEBUG: 적합한 위치를 찾지 못했거나 유효하지 않은 최종 위치. 그룹 {group} 이동 취소.")
        return # 이동하지 않고 함수 종료

    # --- 최종 이동 실행 ---
    if final_shift != 0: # Only move if there's a net shift
        _log(f"DEBUG: 그룹 {group}을(를) 최종적으로 {final_shift}칸 이동 실행.")
        
        pieces_to_move_with_original_coords = [
            {'piece': _get(ref_shape, l, q), 'from': (l, q)} for l, q in group
        ]
        
        # Sort by layer descending for clearing (to avoid overwriting before clearing)
        pieces_to_move_with_original_coords.sort(key=lambda x: x['from'][0], reverse=True)

        # 1. 원본 위치의 조각들 모두 제거
        for item in pieces_to_move_with_original_coords:
            l_orig, q_orig = item['from']
            if l_orig < len(shape.layers) and shape.layers[l_orig]: # Ensure layer exists before accessing
                _set(shape, l_orig, q_orig, None)
        
        # 2. 계산된 새 위치에 조각들 배치
        for item in pieces_to_move_with_original_coords:
            l_orig, q_orig = item['from']
            piece_obj = item['piece']
            
            new_l = l_orig + final_shift
            new_q = q_orig # Quadrant doesn't change
            
            # Ensure new_l is within bounds and layers exist
            if new_l < 0: new_l = 0 # Clamp to 0
            
            _set(shape, new_l, new_q, piece_obj)
            _log(f"DEBUG: 조각 {piece_obj.shape} {item['from']} -> ({new_l}, {new_q})로 이동 완료.")
    else:
        _log(f"DEBUG: 최종 이동 거리 0. 그룹 {group} 이동 없음.")

def _find_twice_floating_s_group(start_l: int, start_q: int, shape: Shape, enable_s_below_rule: bool = False) -> List[Tuple[int, int]]:
    """'두번 뜬 S'를 중심으로 그룹을 찾습니다. (탐색 범위 제한)"""
    group = set()
    q_to_process = [(start_l, start_q)]
    _log(f"DEBUG: _find_twice_floating_s_group 호출됨. 시작: ({start_l}, {start_q})")

    # 탐색 허용 범위 계산
    valid_search_coords = set()
    valid_search_coords.add((start_l, start_q)) # 시작점
    
    # 시작점의 바로 옆 (현재 레이어)
    for adj_q_initial in _adj2(shape, start_q):
        valid_search_coords.add((start_l, adj_q_initial))
        # 시작점 옆의 바로 위 (다음 레이어)
        valid_search_coords.add((start_l + 1, adj_q_initial)) # '두 번 뜬 S'는 시작 층이 2층이므로, 3층까지 고려
    
    # 시작점의 바로 위 (다음 레이어)
    valid_search_coords.add((start_l + 1, start_q))

    # 시작점의 바로 아래 (이전 레이어) - enable_s_below_rule이 true일 때만 의미 있음
    if enable_s_below_rule and start_l > 0:
        valid_search_coords.add((start_l - 1, start_q))
        # 시작점 아래의 바로 옆
        for adj_q_below in _adj2(shape, start_q):
            valid_search_coords.add((start_l - 1, adj_q_below))
    
    _log(f"DEBUG: _find_twice_floating_s_group - 허용된 탐색 범위: {sorted(list(valid_search_coords))}")

    while q_to_process:
        l, q = q_to_process.pop(0)
        if (l, q) in group:
            _log(f"DEBUG: ({l}, {q}) 이미 그룹에 있음. 건너뜀.")
            continue

        current_piece = _get(shape, l, q)
        if not (current_piece and current_piece.shape in _GENERAL_SHAPE_TYPES): # Only general shapes can be part of the group
            _log(f"DEBUG: ({l}, {q}) 조각이 일반 도형이 아님. 건너뜀.")
            continue

        group.add((l, q))
        _log(f"DEBUG: ({l}, {q}) 그룹에 추가됨. 현재 그룹: {sorted(list(group))}")

        # Rule 1: Adjacent S on the same layer with empty space above
        for (adj_l, adj_q) in _adjacent_coords(shape, l, q):
            adj_piece = _get(shape, adj_l, adj_q)
            if (adj_piece and adj_piece.shape in _GENERAL_SHAPE_TYPES and
                _get(shape, adj_l + 1, adj_q) is None): # Empty above adjacent piece
                if (adj_l, adj_q) not in group and (adj_l, adj_q) in valid_search_coords: # 범위 내에 있고 그룹에 없으면 추가
                    _log(f"DEBUG: 규칙 1 - 인접 ({adj_l}, {adj_q}) 조각 ({adj_piece.shape}) 위가 비어있음. 탐색 큐에 추가 (범위 내).")
                    q_to_process.append((adj_l, adj_q))
                elif (adj_l, adj_q) not in valid_search_coords:
                    _log(f"DEBUG: 규칙 1 - 인접 ({adj_l}, {adj_q}) 조각 ({adj_piece.shape}) 범위 밖. 건너뜀.")
        
        # Rule 2: S'' (S'의 아래 S) 그룹화 규칙
        if enable_s_below_rule and l > 0:
            piece_below = _get(shape, l - 1, q) # This is S''
            if (piece_below and piece_below.shape in _GENERAL_SHAPE_TYPES):
                # S''의 바로 아래에 P가 있는지 확인
                piece_below_s_double_prime = _get(shape, l - 2, q)
                if piece_below_s_double_prime and piece_below_s_double_prime.shape == 'P':
                    _log(f"DEBUG: 규칙 2 - S'' ({l-1}, {q}) 아래에 P가 있어 그룹화하지 않음.")
                else:
                    # P가 없는 경우에만 그룹에 추가
                    if (l - 1, q) not in group and (l - 1, q) in valid_search_coords:
                        _log(f"DEBUG: 규칙 2 - 아래 ({l-1}, {q}) 조각 ({piece_below.shape})이 일반 도형이고 아래에 P가 없음. 탐색 큐에 추가 (범위 내).")
                        q_to_process.append((l - 1, q))
                    elif (l - 1, q) not in valid_search_coords:
                        _log(f"DEBUG: 규칙 2 - 아래 ({l-1}, {q}) 조각 ({piece_below.shape}) 범위 밖. 건너뜀.")
    
    _log(f"DEBUG: _find_twice_floating_s_group 종료. 최종 그룹: {sorted(list(group))}")
    return sorted(list(group))

def _relocate_s_pieces(working_shape: Shape, ref_shape: Shape, highest_c_layer: int, c_quad_idx: int):
    """S 조각들을 재배치/생성합니다. 그룹화를 먼저 처리합니다."""
    
    processed_q = set()
    _log(f"DEBUG: _relocate_s_pieces 호출됨. 초기 processed_q: {processed_q}")
    _log(f"DEBUG: Initial ref_shape: {repr(ref_shape)}") # ref_shape의 전체 표현 추가

    # New: 0. '두번 뜬 S' 그룹 탐색 및 처리 (최우선)
    _log("DEBUG: '두번 뜬 S' 패턴 탐색 시작...")
    # Pattern: Layer 1 is None, Layer 2 is 'S', Layer 3 is None, Layer 4 is 'S' or 'c'
    twice_floating_s_q_indices = []
    for q_idx in range(4):
        # Layer 0 (1층) can be anything, so no check here.
        p1 = _get(ref_shape, 1, q_idx) # Layer 1 (2층)
        p2 = _get(ref_shape, 2, q_idx) # Layer 2 (3층)
        p3 = _get(ref_shape, 3, q_idx) # Layer 3 (4층)
        p4 = _get(ref_shape, 4, q_idx) # Layer 4 (5층)

        _log(f"DEBUG: '두번 뜬 S' 검사 중 - 사분면 {q_idx}:\n" \
              f"  2층(L1): {p1}\n" \
              f"  3층(L2): {p2}\n" \
              f"  4층(L3): {p3}\n" \
              f"  5층(L4): {p4}")

        if (p1 is None and # 2층이 비어있고
            p2 and p2.shape in _GENERAL_SHAPE_TYPES and # 3층이 S이고 (여기 수정됨)
            p3 is None and # 4층이 비어있고
            p4 and p4.shape in _GENERAL_SHAPE_TYPES.union({'c'})): # 5층이 S or C인경우. (여기 수정됨)
            twice_floating_s_q_indices.append(q_idx)
            _log(f"DEBUG: '두번 뜬 S' 후보 발견: 사분면 {q_idx}")
        else:
            _log(f"DEBUG: 사분면 {q_idx}는 '두번 뜬 S' 패턴과 불일치.")
    
    if twice_floating_s_q_indices:
        _log(f"DEBUG: '두번 뜬 S' 그룹 탐색 및 처리 시작 (시작점 후보: {twice_floating_s_q_indices})...")
        for s_q_idx in twice_floating_s_q_indices:
            # The actual 'S' for 'twice floating S' is at layer 2
            if (2, s_q_idx) in processed_q:
                _log(f"DEBUG: ({2}, {s_q_idx}) 이미 처리된 '두번 뜬 S'의 일부임. 건너뜀.")
                continue
            
            # Check if layer 0 (1층) is 'P' for this specific quadrant
            p0_at_s_q_idx = _get(ref_shape, 0, s_q_idx)
            enable_s_below = (p0_at_s_q_idx and p0_at_s_q_idx.shape == 'P')
            _log(f"DEBUG: 사분면 {s_q_idx}의 1층(L0)은 P: {enable_s_below}")

            group = _find_twice_floating_s_group(2, s_q_idx, working_shape, enable_s_below) # enable_s_below 전달
            if group: # Only process if a group was actually found
                # NEW: 그룹의 모든 요소 하단이 비어있는지 검사
                all_bottoms_empty = True
                group_coords = set(group)
                for l, q in group:
                    l_below = l - 1
                    if l_below < 0: # 0층 아래는 바닥이므로 비어있지 않음
                        all_bottoms_empty = False
                        break
                    
                    piece_below = _get(working_shape, l_below, q)
                    if piece_below is not None and (l_below, q) not in group_coords:
                        # 그룹에 속하지 않은 조각이 아래에 있으면 비어있지 않음
                        all_bottoms_empty = False
                        break
                
                if all_bottoms_empty:
                    _log(f"DEBUG: 그룹 {group}의 모든 하단이 비어있어 이동하지 않습니다.")
                    # 이동하지 않으므로 processed_q 업데이트도 건너뜀
                else:
                    _log(f"DEBUG: 사분면 {s_q_idx} (2층)을(를) 중심으로 '두번 뜬 S' 그룹 발견: {group}")
                    _log(f"DEBUG: _move_s_group 호출 (ref_shape로 working_shape 전달). 현재 working_shape: {repr(working_shape)}") # 로그 추가
                    _move_s_group(group, working_shape, working_shape, highest_c_layer, c_quad_idx) # ref_shape를 working_shape로 변경
                    processed_q.update(group) # Update with all coords in the moved group
                    _log(f"DEBUG: '두번 뜬 S' 그룹 처리 후 processed_q: {processed_q}")

    # 1. 뜬 S(-S)를 중심으로 그룹 형성 및 처리 (기존 로직)
    _log(f"DEBUG: '뜬 S(-S)' 그룹 탐색 시작. 현재 processed_q: {processed_q}")
    # Floating S: Layer 0 is None, Layer 1 is S/C/R/W
    floating_s_q_indices = [
        q for q in range(4) if _get(ref_shape, 0, q) is None and 
        (p1 := _get(ref_shape, 1, q)) and p1.shape in _GENERAL_SHAPE_TYPES
    ]
    if floating_s_q_indices:
        _log(f"DEBUG: '뜬 S(-S)' 그룹 탐색 및 처리 시작 (시작점 후보: {floating_s_q_indices})...")
        for s_q_idx in floating_s_q_indices:
            # Check if this (1, s_q_idx) was already part of a 'twice floating S' group
            if (1, s_q_idx) in processed_q:
                _log(f"DEBUG: ({1}, {s_q_idx}) 이미 처리된 그룹의 일부임. 건너뜀.")
                continue
            
            group = _find_s_star_group(s_q_idx, working_shape)
            if group: # Only process if a group was actually found
                _log(f"DEBUG: 사분면 {s_q_idx}을(를) 중심으로 그룹 발견: {group}")
                _log(f"DEBUG: _move_s_group 호출 (ref_shape로 working_shape 전달). 현재 working_shape: {repr(working_shape)}") # 로그 추가
                _move_s_group(group, working_shape, working_shape, highest_c_layer, c_quad_idx) # ref_shape를 working_shape로 변경
                processed_q.update(group) # Update with all coords in the moved group
                _log(f"DEBUG: '뜬 S(-S)' 그룹 처리 후 processed_q: {processed_q}")
            
    # New: 2.1. 0층 S와 1층 P/S가 함께 있는 그룹 처리
    _log(f"DEBUG: '0층 S 위에 1층 P/S' 그룹 탐색 시작.")
    s_p_s_groups = []
    for q_idx in range(4):
        s0 = _get(ref_shape, 0, q_idx)
        p1_s1 = _get(ref_shape, 1, q_idx)

        if (s0 and s0.shape in _GENERAL_SHAPE_TYPES and
            p1_s1 and p1_s1.shape in _BLOCKER_SHAPE_TYPES and # P 또는 S
            (0, q_idx) not in processed_q and
            (1, q_idx) not in processed_q):
            
            group = [(0, q_idx), (1, q_idx)] # 0층 S와 1층 P/S를 그룹으로 묶음
            s_p_s_groups.append(group)
            _log(f"DEBUG: '0층 S 위에 1층 P/S' 그룹 후보 발견: {group}")
    
    for group in s_p_s_groups:
        _log(f"DEBUG: '0층 S 위에 1층 P/S' 그룹 처리 시작: {group}")
        _move_s_group(group, working_shape, working_shape, highest_c_layer, c_quad_idx) # 그룹 이동
        processed_q.update(group) # 처리된 좌표 업데이트
        _log(f"DEBUG: '0층 S 위에 1층 P/S' 그룹 처리 후 processed_q: {processed_q}")

    # Original 2. 바닥 S 개별 처리
    _log(f"DEBUG: '바닥 S' 개별 처리 시작. 현재 processed_q: {processed_q}")
    bottom_s_q_indices = [
        q for q in range(4) if (p0 := _get(ref_shape, 0, q)) and p0.shape in _GENERAL_SHAPE_TYPES
    ]
    ungrouped_bottom_s = [q for q in bottom_s_q_indices if (0, q) not in processed_q] # Check if base S itself was processed
    if ungrouped_bottom_s:
        _log(f"DEBUG: '바닥 S' 개별 처리 시작 (대상: {ungrouped_bottom_s})...")
        for s_q_idx in ungrouped_bottom_s:
            _log(f"DEBUG: _find_s_relocation_spot 호출 (ref_shape로 working_shape 전달). 현재 working_shape: {repr(working_shape)}") # 로그 추가
            l_target, fill_c, moved_s_pieces_from_relocation = _find_s_relocation_spot(working_shape, s_q_idx, working_shape, highest_c_layer, c_quad_idx) # 반환 값 추가
            _log(f"DEBUG: 사분면 {s_q_idx}의 '바닥 S' 재배치 위치: L{l_target}, 채울 S: {fill_c}, 실제로 옮겨질 S: {moved_s_pieces_from_relocation}")
            
            if l_target != -1:
                # 가상으로 옮겼던 S들을 실제로 옮기기
                if moved_s_pieces_from_relocation:
                    _log(f"DEBUG: 가상으로 옮겨졌던 S 조각들 실제로 이동 시작 ({len(moved_s_pieces_from_relocation)}개)...")
                    for (l_orig, q_orig), (l_new, q_new), piece_obj in moved_s_pieces_from_relocation:
                        if l_orig < len(working_shape.layers) and working_shape.layers[l_orig]:
                            working_shape.layers[l_orig].quadrants[q_orig] = None # 기존 위치 지우기
                        _ensure_layer(working_shape, l_new)
                        working_shape.layers[l_new].quadrants[q_new] = piece_obj # 새로운 위치에 배치
                        _log(f"DEBUG: 실제 S 이동: ({l_orig}, {q_orig}) -> ({l_new}, {q_new})에 {piece_obj.shape} 배치 완료.")

                # 중앙 S 배치
                # (0, s_q_idx)의 조각은 나중에 layers[1:] 슬라이싱으로 효과적으로 제거됩니다.
                # 따라서 l_target에 *새로운* C를 배치하는 것입니다.
                _ensure_layer(working_shape, l_target)
                working_shape.layers[l_target].quadrants[s_q_idx] = Quadrant('S', 'u')
                _log(f"DEBUG: ({l_target}, {s_q_idx})에 'S' 배치됨 (중앙 S).")

def _find_s_relocation_spot(shape: Shape, q_idx: int, ref_shape: Shape, highest_c_layer: int, c_quad_idx: int) -> Tuple[int, List[Tuple[int, int]], List[Tuple[Tuple[int, int], Tuple[int, int], Quadrant]]]:
    """개별 S를 배치할 최적 위치를 찾습니다."""
    _log(f"DEBUG: _find_s_relocation_spot 호출됨. q_idx: {q_idx}")

    # 실제로 이동된 S 조각들의 정보를 저장할 리스트
    actual_moved_s_pieces: List[Tuple[Tuple[int, int], Tuple[int, int], Quadrant]] = []

    # 케이스 1: 현재 사분면 위로 하늘이 열려있는 경우
    if _is_sky_open_above(shape, 0, q_idx):
        _log(f"DEBUG: _find_s_relocation_spot - Case 1 (하늘이 열려있음)")
        for l_idx in range(2, Shape.MAX_LAYERS): # 2층부터 시작 (3층)
            adj = _adj2(shape, q_idx)
            if len(adj) != 2: # 원래 방어적 검사 유지
                continue
            adj_coords = [(l_idx, adj[0]), (l_idx, adj[1])]
            p1, p2 = _get(shape, *adj_coords[0]), _get(shape, *adj_coords[1])

            # 원래 조건: 인접한 두 위치 모두 일반 도형으로 막혀있지 않아야 함
            if not ((p1 and p1.shape in _INVALID_ADJACENCY_SHAPES) or \
                    (p2 and p2.shape in _INVALID_ADJACENCY_SHAPES)): # 이 부분은 _check_s_placement_validity로 대체 예정
                _log(f"DEBUG: Case 1 - 적합한 위치 찾음: L{l_idx}, 인접 채울 c: {[(l_idx, a) for a, p in zip(adj, [p1,p2]) if p is None]}")
                # 이 부분도 _check_s_placement_validity를 사용하여 통합
                if _check_s_placement_validity(shape, l_idx, q_idx, set(), highest_c_layer, c_quad_idx):
                    return l_idx, [(l_idx, a) for a, p in zip(adj, [p1,p2]) if p is None], [] # 가상 이동된 S 없음
        _log(f"DEBUG: Case 1 - 적합한 위치 찾지 못함.")
        return -1, [], [] # 하늘이 열려있어도 적합한 위치를 찾지 못함

    # 케이스 2: 현재 사분면 위로 하늘이 열려있지 않은 경우
    _log(f"DEBUG: _find_s_relocation_spot - Case 2 (하늘이 닫혀있음)")
    
    # 1. '천장' (가장 낮은 층의 블로커) 찾기
    top_blocker_layer = Shape.MAX_LAYERS # 기본값: 천장 없음 (모두 비어있음)
    for l_check in range(1, Shape.MAX_LAYERS): # 0층(바닥 S가 있는 층)은 건너뛰고 1층부터 검사
        if _get(shape, l_check, q_idx) is not None:
            top_blocker_layer = l_check
            _log(f"DEBUG: q_idx {q_idx}의 천장 발견: L{top_blocker_layer} (조각: {_get(shape, l_check, q_idx)})个体")
            break
    
    found_l_target = -1
    
    # --- 첫 번째 시도: 일반적인 하향 이동 (가상 S 이동 없음) ---
    _log(f"DEBUG: 첫 번째 시도 시작 (가상 S 이동 없음). 천장({top_blocker_layer}) 아래칸부터 재배치 탐색 시작: L{top_blocker_layer - 1}")
    current_l_target_attempt = top_blocker_layer - 1
    while current_l_target_attempt >= 2: # 3층(인덱스 2)까지 내려감
        l_idx = current_l_target_attempt
        _log(f"DEBUG: 현재 재배치 시도 층 (1차): L{l_idx}, q_idx: {q_idx}")

        # 현재 위치가 비어있는지 확인
        current_spot_piece = _get(shape, l_idx, q_idx) # working_shape를 사용합니다.
        if current_spot_piece is not None: 
            _log(f"DEBUG: L{l_idx}, q{q_idx} 이미 조각({current_spot_piece.shape}) 있음. 한 칸 내림.")
            current_l_target_attempt -= 1
            continue
        
        # 인접 조건 검사
        can_place_central_c = False
        adj = _adj2(shape, q_idx)
        if len(adj) == 2:
            # p1 = _get(shape, *adj_coords[0]) # working_shape를 사용합니다.
            # p2 = _get(shape, *adj_coords[1]) # working_shape를 사용합니다.
            if not _check_s_placement_validity(shape, l_idx, q_idx, set(), highest_c_layer, c_quad_idx): # hypothetical_group_positions는 빈 set 전달, highest_c_layer, c_quad_idx 추가
                can_place_central_c = False # 양쪽에 하나라도 S 또는 c가 있으면 유효하지 않음
            else:
                can_place_central_c = True  # 유효함
        
        _log(f"DEBUG: L{l_idx}, q{q_idx} (비어있음): can_place_central_c={can_place_central_c}")

        if can_place_central_c:
            found_l_target = l_idx
            _log(f"DEBUG: 1차 시도에서 유효한 재배치 위치 찾음: L{found_l_target}. 탐색 중단.")
            break
        else:
            _log(f"DEBUG: L{l_idx}, q{q_idx} 인접 조건 불만족 (1차). 한 칸 내림.")
            current_l_target_attempt -= 1

    # --- 두 번째 시도: 첫 번째 시도에서 위치를 찾지 못했고, S 가상 이동 포함 ---
    if found_l_target == -1:
        _log(f"DEBUG: 첫 번째 시도에서 유효한 위치를 찾지 못함. 두 번째 시도 시작 (가상 S 이동 포함).")
        current_l_target_attempt = top_blocker_layer - 1 # 다시 천장 바로 아래부터 시작
        while current_l_target_attempt >= 2: # 3층(인덱스 2)까지 내려감
            l_idx = current_l_target_attempt
            _log(f"DEBUG: 현재 재배치 시도 층 (2차): L{l_idx}, q_idx: {q_idx}")

            # 현재 위치가 비어있는지 확인
            if _is_position_blocked(shape, l_idx, q_idx): # 새 헬퍼 함수 사용
                _log(f"DEBUG: L{l_idx}, q{q_idx} 이미 조각({_get(shape, l_idx, q_idx).shape if _get(shape, l_idx, q_idx) else 'None'}) 있음 (2차). 한 칸 내림.")
                current_l_target_attempt -= 1
                continue
            
            # 인접 조건 검사 (가상 S 이동 고려)
            can_place_central_c_with_virtual_move = False
            adj = _adj2(shape, q_idx)
            if len(adj) == 2:
                # 먼저 현재 상태로 유효성 확인
                if _check_s_placement_validity(shape, l_idx, q_idx, set(), highest_c_layer, c_quad_idx): # hypothetical_group_positions는 빈 set 전달, highest_c_layer, c_quad_idx 추가
                    can_place_central_c_with_virtual_move = True # 이미 유효하면 가상 이동 필요 없음
                    _log(f"DEBUG: 2차 시도 - L{l_idx}, q{q_idx} (비어있음): 가상 이동 없이도 유효함.")
                else:
                    # 현재 상태가 유효하지 않으면 가상 S 이동 시도
                    _log(f"DEBUG: 2차 시도 - L{l_idx}, q{q_idx}: 현재 상태 유효하지 않음. 가상 S 이동 시도.")
                    for adj_q in adj:
                        adj_piece = _get(shape, l_idx, adj_q) # working_shape의 인접 조각
                        
                        if adj_piece and adj_piece.shape in _GENERAL_SHAPE_TYPES: # 인접 조각이 S인 경우
                            # 그 S가 위쪽에 빈 공간이 있는지 검사
                            if not _is_position_blocked(shape, l_idx + 1, adj_q): # 새 헬퍼 함수 사용
                                # 빈 공간이 있다면, 그 S를 (가상으로)위로 옮긴 후, 지금 상태가 유효한 위치인지 검사
                                temp_shape_for_virtual_move = _copy_without(shape, [(l_idx, adj_q)])
                                
                                # 가상 이동: 새로운 위치에 S 배치
                                new_s_l = l_idx + 1
                                _ensure_layer(temp_shape_for_virtual_move, new_s_l)
                                temp_shape_for_virtual_move.layers[new_s_l].quadrants[adj_q] = adj_piece.copy() # 원본 조각 복사하여 배치
                                _log(f"DEBUG: 2차 시도 - 가상 이동: S ({l_idx}, {adj_q}) -> ({new_s_l}, {adj_q})")

                                # 가상 이동 후, S가 배치될 중앙 위치 (l_idx, q_idx)의 인접성 재평가
                                if _check_s_placement_validity(temp_shape_for_virtual_move, l_idx, q_idx, set(), highest_c_layer, c_quad_idx): # hypothetical_group_positions는 빈 set 전달, highest_c_layer, c_quad_idx 추가
                                    can_place_central_c_with_virtual_move = True
                                    _log(f"DEBUG: 2차 시도 - 가상 S 이동 후 유효한 위치 발견: L{l_idx}. 가상 이동된 S: ({l_idx}, {adj_q}) -> ({new_s_l}, {adj_q})")
                                    # 유효한 위치를 찾았으므로 실제 이동 정보를 저장
                                    actual_moved_s_pieces.append(((l_idx, adj_q), (new_s_l, adj_q), adj_piece.copy()))
                                    break
                
                if can_place_central_c_with_virtual_move:
                    found_l_target = l_idx
                    _log(f"DEBUG: 2차 시도에서 유효한 재배치 위치 찾음: L{found_l_target}. 탐색 중단.")
                    break
                else:
                    _log(f"DEBUG: L{l_idx}, q{q_idx} 인접 조건 불만족 (2차). 한 칸 내림.")
                    current_l_target_attempt -= 1


    # 최종 반환
    if found_l_target != -1:
        adj = _adj2(shape, q_idx)
        fill_c_coords = []
        if len(adj) == 2: # Ensure we have two adjacent quadrants for fill_c
            p1 = _get(shape, found_l_target, adj[0]) # working_shape 기준으로 판단
            p2 = _get(shape, found_l_target, adj[1]) # working_shape 기준으로 판단
            if p1 is None:
                fill_c_coords.append((found_l_target, adj[0]))
            if p2 is None:
                fill_c_coords.append((found_l_target, adj[1]))
        _log(f"DEBUG: Case 2 - 최종 반환 위치: L{found_l_target}, 채울 c: {fill_c_coords}")
        return found_l_target, fill_c_coords, actual_moved_s_pieces # 실제 이동된 S 정보 반환

    _log(f"DEBUG: _find_s_relocation_spot - 최종적으로 위치를 찾지 못함. q_idx: {q_idx}")
    return -1, [], [] # Fallback if no spot found in either case (highly unlikely given MAX_LAYERS)

def _place_and_propagate_c(shape: Shape, coords: List[Tuple[int, int]], ref_shape: Shape):
    # coords에 지정된 위치에 c 조각을 배치하고 위로 전파
    for l, q in coords:
        if _get(shape, l, q) is None:
            _set(shape, l, q, Quadrant('c', 'g'))
            _propagate_c_upwards(shape, l + 1, q, ref_shape)

def _propagate_c_upwards(shape, l_start, q, ref_shape):
    l = l_start
    while l < Shape.MAX_LAYERS:
        if _is_adjacent_to_ref_c(l, q, ref_shape): break
        _ensure_layer(shape, l)
        p = _get(shape, l, q)
        if p is None: 
            _set(shape, l, q, Quadrant('c', 'm'))
            # 새로 배치된 c 주변을 확인하고 P를 이동시키는 로직 호출
            l += 1
        elif p.shape == 'c': l += 1
        else: break

def _is_adjacent_to_ref_c(l, q, ref_shape):
    coords = [(l-1, q), (l+1, q)] + [(l, aq) for aq in range(4) if ref_shape._is_adjacent(q, aq)]
    for cl, cq in coords:
        if 0 <= cl < len(ref_shape.layers) and (p := ref_shape._get_piece(cl, cq)) and p.shape == 'c': return True
    return False

def _get_adjacent_matrix_coords(l: int, q: int, shape: Shape) -> set[Tuple[int, int]]:
    """주어진 크리스탈 조각의 상하좌우 외곽선 좌표를 반환합니다. (자신 위치 제외)"""
    coords = set()

    # 위아래
    if l + 1 < Shape.MAX_LAYERS:
        coords.add((l + 1, q))
    if l - 1 >= 0:
        coords.add((l - 1, q))

    # 같은 층의 인접 사분면
    for coord in _adjacent_coords(shape, l, q):
        coords.add(coord)
    
    # 크리스탈 자신의 위치는 제외
    if (l, q) in coords:
        coords.remove((l, q)) # Defensive check, should not be added by logic above

    return coords

def _check_s_placement_validity(shape: Shape, l: int, q: int, hypothetical_group_positions: set[Tuple[int, int]], highest_c_layer: int, c_quad_idx: int) -> bool:
    """
    S가 올려진 후에, 그 위치의 양쪽 모두 S 또는 c가 아니어야함.
    양쪽에 그룹이 아닌 S 또는 c가 하나라도 있는 경우 유효하지 않는 위치입니다.
    그룹 중 기준점(c)의 '반대쪽' 사분면에 있는 가장 높은 도형의 높이가
    기준점(c)의 높이 - 1 보다 같거나 높을때 유효하지 않다는 조건 추가.
    """
    adj = _adj2(shape, q)
    if len(adj) != 2:
        # Should always have 2 adjacent quadrants for S
        _log(f"DEBUG: _check_s_placement_validity: Quadrant {q} does not have 2 adjacent quadrants. Assuming invalid.")
        return False

    adj_coords = [(l, adj[0]), (l, adj[1])]
    p1_hypo = _get(shape, *adj_coords[0])
    p2_hypo = _get(shape, *adj_coords[1])

    # Check if either adjacent piece is an S or c AND not part of the hypothetical group
    is_p1_invalid_adj = (p1_hypo and p1_hypo.shape in _INVALID_ADJACENCY_SHAPES and adj_coords[0] not in hypothetical_group_positions)
    is_p2_invalid_adj = (p2_hypo and p2_hypo.shape in _INVALID_ADJACENCY_SHAPES and adj_coords[1] not in hypothetical_group_positions)

    if is_p1_invalid_adj or is_p2_invalid_adj:
        _log(f"DEBUG: _check_s_placement_validity: Invalid adjacency found. P1 invalid: {is_p1_invalid_adj}, P2 invalid: {is_p2_invalid_adj}")
        return False # Invalid if at least one side has a non-group S or c
    
    # NEW CONDITION: Check height of the highest piece in the opposite quadrant of 'c'
    opposite_q_from_c = (c_quad_idx + 2) % 4
    highest_piece_in_opposite_q_layer = -1 # Initialize with -1, meaning no piece found
    for l_check in _range_top_down(Shape.MAX_LAYERS):
        piece = _get(shape, l_check, opposite_q_from_c)
        
        # Check if a piece from the hypothetical group lands here
        is_hypothetical_piece = (l_check, opposite_q_from_c) in hypothetical_group_positions
        
        if piece is not None or is_hypothetical_piece:
            highest_piece_in_opposite_q_layer = l_check
            break

    if highest_piece_in_opposite_q_layer != -1 and highest_piece_in_opposite_q_layer >= (highest_c_layer - 1):
        _log(f"DEBUG: _check_s_placement_validity: Invalid due to opposite quadrant height. Highest piece in opposite_q ({highest_piece_in_opposite_q_layer}) is >= (highest_c_layer-1) ({highest_c_layer-1})")
        return False

    _log(f"DEBUG: _check_s_placement_validity: Valid adjacency and opposite quadrant height.")
    return True

def _is_position_blocked(shape: Shape, l: int, q: int) -> bool:
    """위치가 옮겨질 위치에 -가 아닌 다른 도형이 있다면 옮겨지지 않습니다."""
    if l >= Shape.MAX_LAYERS or l < 0: # Out of bounds is considered blocked
        _log(f"DEBUG: _is_position_blocked: ({l}, {q}) is out of bounds.")
        return True
    
    piece = _get(shape, l, q)
    if piece is not None:
        _log(f"DEBUG: _is_position_blocked: ({l}, {q}) is blocked by {piece.shape}.")
        return True
    
    _log(f"DEBUG: _is_position_blocked: ({l}, {q}) is not blocked (empty).")
    return False

def _fill_opposite_quadrant(shape: Shape, opposite_q_idx: int, highest_c_layer: int, ref_shape: Shape) -> List[Tuple[int, int]]:
    _log(f"DEBUG: 반대 사분면({opposite_q_idx})에 c 채우기...")
    newly_added_c_coords = [] # 새로 추가된 c 조각의 좌표를 저장할 리스트
    newly_added_adjacent_c_coords = [] # 새로 추가된 '옆' c 조각의 좌표를 저장할 리스트

    for l_idx in _range_top_down(Shape.MAX_LAYERS): # 원래대로 맨 위층부터 시작
        _ensure_layer(shape, l_idx)
        p = _get(shape, l_idx, opposite_q_idx)

        # 조건 1: 아래가 막혀있으면 중단
        if p is not None and p.shape != 'c':
            break

        # 조건 2: 아래가 비어있더라도, 그 양 옆에 '원본' c가 있으면 중단
        if p is None:
            has_adjacent_original_c = False
            for adj_l, adj_q in _adjacent_coords(shape, l_idx, opposite_q_idx):
                # shape(현재 모양)가 아닌 ref_shape(원본 모양)에서 c가 있는지 확인
                adj_piece_original = _get(ref_shape, adj_l, adj_q)
                if adj_piece_original and adj_piece_original.shape == 'c':
                    has_adjacent_original_c = True
                    break
            if has_adjacent_original_c:
                _log(f"DEBUG: ({l_idx}, {opposite_q_idx})는 비어있지만 양 옆에 '원본' c가 있어 기둥 확장 중단.")
                break

        _set(shape, l_idx, opposite_q_idx, Quadrant('c', 'y'))
        newly_added_c_coords.append((l_idx, opposite_q_idx)) # 기둥 c 조각 추가

        # 인접 사분면 채우기 시도 (3층부터 최고층 크리스탈 아래층까지)
        if l_idx >= 2 and l_idx < highest_c_layer: # 3층 (인덱스 2)부터 최고층 크리스탈 층 미만까지
            for (adj_l, aq_fill) in _adjacent_coords(shape, l_idx, opposite_q_idx):
                # 현재 층의 인접 사분면이 비어있을 경우에만 'c'로 채움
                # 그리고 원래 도형에도 c가 없어야 함.
                if _get(shape, adj_l, aq_fill) is None:
                    original_piece_at_adj = _get(ref_shape, adj_l, aq_fill)
                    if not (original_piece_at_adj and original_piece_at_adj.shape == 'c'): # 원본에 c가 아닌 경우에만 추가
                        # 옆옆 c (기둥이 아닌 원래 c) 검사
                        # aq_fill의 인접 사분면 중, opposite_q_idx가 아닌 다른 사분면
                        skip_expansion_due_to_far_c = False
                        adj_to_aq_fill = [q for q in range(4) if shape._is_adjacent(aq_fill, q) and q != opposite_q_idx]
                        for far_q in adj_to_aq_fill:
                            far_piece = _get(ref_shape, adj_l, far_q)
                            if far_piece and far_piece.shape == 'c':
                                _log(f"DEBUG: ({adj_l}, {aq_fill}) 옆옆 ({adj_l}, {far_q})에 기존 c({far_piece.shape}) 있음. 확장 건너뜀.")
                                skip_expansion_due_to_far_c = True
                                break
                        
                        if skip_expansion_due_to_far_c:
                            continue # 옆옆 c가 있어서 확장 건너뜀

                        _ensure_layer(shape, adj_l)
                        _set(shape, adj_l, aq_fill, Quadrant('c', 'y')) # 인접 사분면도 'c'로 채움
                        newly_added_c_coords.append((adj_l, aq_fill)) # 인접 c 조각 추가
                        newly_added_adjacent_c_coords.append((adj_l, aq_fill)) # 옆으로 추가된 c는 따로 저장
                        _log(f"DEBUG: 인접 사분면 ({adj_l}, {aq_fill})에 'c' 채움 (반대 사분면 채우기 로직).")
    return newly_added_c_coords, newly_added_adjacent_c_coords

def _fill_c_from_pins(shape: Shape, p_indices: list[int], ref_shape: Shape): # ref_shape 추가
    if not p_indices or not shape.layers: return
    _log("DEBUG: 핀 위치의 위의 빈 공간에 c 채우기 시작...") # 로그 메시지 변경
    for q_idx in p_indices:
        # 0층(핀 위치)에는 c를 직접 채우지 않고, 그 위층부터 전파 시작
        # if shape._get_piece(0, q_idx) is None: # 이 조건도 제거 (핀은 어차피 있음)
        #    shape.layers[0].quadrants[q_idx] = Quadrant('c', 'b') # 0층에 c 채우는 로직 제거
        #    _log(f"DEBUG: 핀 사분면 {q_idx}에 c 채움. 위로 전파 시작.")
        _log(f"DEBUG: 핀 사분면 {q_idx} 위로 c 전파 시작.") # 로그 추가
        _propagate_c_upwards(shape, 1, q_idx, ref_shape) # 1층부터 위로 전파 시작

def _lift_adjacent_pieces(shape: Shape, empty_spot_l: int, q_idx: int, highest_c_layer: int, c_quad_idx: int) -> bool:
    """
    주어진 빈 공간(empty_spot_l, q_idx) 주위가 막혀있을 때,
    인접한 P 또는 S 조각을 들어 올리는 로직.
    실제로 조각을 이동시켰으면 True를 반환합니다.
    """
    moved_something = False
    adj_q_coords = _adj2(shape, q_idx)

    # 1. 주변 세 방향이 막혔는지 먼저 확인
    check_coords = []
    for aq in adj_q_coords:
        check_coords.append((empty_spot_l, aq))
    if empty_spot_l + 1 < Shape.MAX_LAYERS:
        check_coords.append((empty_spot_l + 1, q_idx))

    is_surrounded = all(_is_position_blocked(shape, cl, cq) for cl, cq in check_coords)

    if not is_surrounded:
        return False # 세 방향이 모두 막히지 않았으면 아무것도 하지 않음

    _log(f"DEBUG: P ({empty_spot_l-1}, {q_idx}) 위 빈 공간 ({empty_spot_l}, {q_idx}) 발견 및 주변 막힘 확인.")
    
    # 2. 양 옆 조각들을 들어올리는 로직
    for adj_q_for_movement in adj_q_coords:
        piece_at_target_adj = _get(shape, empty_spot_l, adj_q_for_movement)

        if piece_at_target_adj and piece_at_target_adj.shape == 'P':
            # P 이동 규칙
            if not _is_position_blocked(shape, empty_spot_l + 1, adj_q_for_movement):
                _set(shape, empty_spot_l, adj_q_for_movement, None)
                _set(shape, empty_spot_l + 1, adj_q_for_movement, piece_at_target_adj)
                _log(f"DEBUG: Rule 1 (lift): P ({empty_spot_l}, {adj_q_for_movement}) -> ({empty_spot_l + 1}, {adj_q_for_movement})로 이동.")
                moved_something = True
            elif (p_above := _get(shape, empty_spot_l + 1, adj_q_for_movement)) and p_above.shape == 'P' and not _is_position_blocked(shape, empty_spot_l + 2, adj_q_for_movement):
                _set(shape, empty_spot_l, adj_q_for_movement, None)
                _set(shape, empty_spot_l + 1, adj_q_for_movement, None)
                _set(shape, empty_spot_l + 1, adj_q_for_movement, piece_at_target_adj)
                _set(shape, empty_spot_l + 2, adj_q_for_movement, p_above)
                _log(f"DEBUG: Rule 2 (lift): 두 P ({empty_spot_l}, {adj_q_for_movement}) -> ({empty_spot_l + 1}, {adj_q_for_movement})로 이동.")
                moved_something = True

        elif piece_at_target_adj and piece_at_target_adj.shape in _GENERAL_SHAPE_TYPES:
            # S 이동 규칙
            original_s_l = empty_spot_l
            original_s_q = adj_q_for_movement
            s_piece_obj = piece_at_target_adj
            current_s_l = original_s_l
            test_s_l = original_s_l
            
            while True:
                test_s_l += 1
                if _is_position_blocked(shape, test_s_l, original_s_q):
                    break
                
                temp_shape_for_s_val = _copy_without(shape, [(current_s_l, original_s_q)])
                
                if _check_s_placement_validity(temp_shape_for_s_val, test_s_l, original_s_q, set(), highest_c_layer, c_quad_idx):
                    _set(shape, current_s_l, original_s_q, None)
                    _set(shape, test_s_l, original_s_q, s_piece_obj)
                    _log(f"DEBUG: Rule 3 (lift): S ({original_s_l}, {original_s_q}) -> ({test_s_l}, {original_s_q})로 이동.")
                    moved_something = True
                    current_s_l = test_s_l # S의 현재 위치 업데이트
                else:
                    # 유효하지 않더라도 계속 위로 탐색
                    pass
    return moved_something

def _move_pieces_based_on_empty_spot_around_p(shape: Shape, ref_shape: Shape, pins: List[int], highest_c_layer: int, c_quad_idx: int):
    """
    P 위에 새로 추가된 c 조각 주변을 확인하고 P와 S를 이동시키는 로직.
    새로운 c의 좌표는 필요없으며, 전체 맵을 기준으로 빈 공간이 있을 때 P 또는 S를 이동시킴.
    """
    _log(f"DEBUG: _move_pieces_based_on_empty_spot_around_p 호출됨.")
    moved_something = False

    for q_idx in pins:
        l_idx = 0
        p_piece = _get(shape, l_idx, q_idx)
        if not (p_piece and p_piece.shape == 'P'):
            continue

        # P 바로 위(1층)가 비어있는지 확인
        if _is_position_blocked(shape, l_idx + 1, q_idx):
            continue

        adj_q_coords = _adj2(shape, q_idx)
        if len(adj_q_coords) != 2:
            continue
            
        # --- 시나리오 1: P 바로 위(1층)의 세 방향이 막혀있는 경우 ---
        if _lift_adjacent_pieces(shape, l_idx + 1, q_idx, highest_c_layer, c_quad_idx):
             moved_something = True
             continue # 이동이 발생했으면 다음 핀으로 넘어감

        # --- 시나리오 2: P 바로 위는 비어있고, 양쪽은 막혔지만, P의 두 칸 위(2층)가 비어있는 경우 ---
        # 1층의 양쪽이 막혔는지 확인
        is_adj_blocked = all(_is_position_blocked(shape, l_idx + 1, aq) for aq in adj_q_coords)
        # 2층이 비어있는지 확인
        is_two_up_empty = not _is_position_blocked(shape, l_idx + 2, q_idx)

        if is_adj_blocked and is_two_up_empty:
            _log(f"DEBUG: P({l_idx},{q_idx}) 위 연쇄 검사 조건 충족. L{l_idx+2}를 기준으로 들어올리기 시도.")
            # 2층을 기준으로 다시 들어올리기 시도
            if _lift_adjacent_pieces(shape, l_idx + 2, q_idx, highest_c_layer, c_quad_idx):
                moved_something = True
                
    return moved_something

# --- 메인 프로세스 함수 ---
def claw_process(shape_code: str, logger: Optional[Callable[[str], None]] = None) -> str:
    global _log_callback
    original_callback = _log_callback
    _log_callback = logger

    try:
        _log(f"DEBUG: claw_process 호출됨. 입력: {shape_code}")
        
        original_max_layers = Shape.MAX_LAYERS
        try:
            _validate_shape_code(shape_code)
            initial_shape = Shape.from_string(shape_code)
            working_shape = initial_shape.copy()
            _log(f"DEBUG: 초기 도형: {repr(initial_shape)}")
            pins, highest_c_layer, c_quad_idx = _get_static_info(initial_shape) # highest_c_layer 추가

            # 1. 초기 도형 기준, 모든 크리스탈의 외곽선 좌표 수집
            crystals_to_clear_outline = set()
            original_crystal_centers = set() # 원본 크리스탈의 중심 좌표를 저장할 집합 추가

            for l_idx, layer in enumerate(initial_shape.layers):
                for q_idx, piece in enumerate(layer.quadrants):
                    if piece and piece.shape == 'c':
                        original_crystal_centers.add((l_idx, q_idx)) # 원본 크리스탈 중심 저장
                        _log(f"DEBUG: 초기 도형에서 크리스탈 발견: ({l_idx}, {q_idx}). 윤곽선 좌표 수집 시작.")
                        adjacent_outline_coords = _get_adjacent_matrix_coords(l_idx, q_idx, initial_shape)
                        crystals_to_clear_outline.update(adjacent_outline_coords)
                        _log(f"DEBUG: 수집된 윤곽선 좌표: {sorted(list(adjacent_outline_coords))}")
            _log(f"DEBUG: 원본 크리스탈 중심 좌표: {sorted(list(original_crystal_centers))}") # 로그 추가

            # 2. 윤곽선 좌표에서 원본 크리스탈 중심 좌표를 제외하여 실제 제거할 좌표만 남김
            crystals_to_clear_outline.difference_update(original_crystal_centers)
            _log(f"DEBUG: 원본 크리스탈 제외 후 제거할 윤곽선 좌표: {sorted(list(crystals_to_clear_outline))}") # 로그 추가

            Shape.MAX_LAYERS += 1
            working_shape.layers.append(Layer([None]*4))
            _log(f"DEBUG: 임시 공간 확보 (MAX_LAYERS={Shape.MAX_LAYERS})")

            # S 조각 그룹 이동 (기존 로직 유지)
            _relocate_s_pieces(working_shape, initial_shape, highest_c_layer, c_quad_idx)
            _log(f"DEBUG: S 그룹 이동 후 working_shape: {repr(working_shape)}")

            # P 및 S 조각 이동 (새로운 반복 로직)
            _log("DEBUG: P 및 S 조각 이동 로직 시작...")
            moved_any_piece = True
            while moved_any_piece:
                moved_any_piece = _move_pieces_based_on_empty_spot_around_p(working_shape, initial_shape, pins, highest_c_layer, c_quad_idx)
                if moved_any_piece: # 이동이 발생했다면 디버그 메시지 출력
                    _log(f"DEBUG: _move_pieces_based_on_empty_spot_around_p 실행 후: {repr(working_shape)}")
                else:
                    _log("DEBUG: 더 이상 이동할 P 또는 S 조각이 없음. 이동 로직 종료.")

            # C 조각 추가 (모든 P, S 이동 후)
            _log(f"DEBUG: _fill_c_from_pins 호출 (ref_shape로 initial_shape 전달).")
            _fill_c_from_pins(working_shape, pins, initial_shape) 
            _log(f"DEBUG: 핀에 c 채운 후 working_shape: {repr(working_shape)}")

            _log(f"DEBUG: _fill_opposite_quadrant 호출 (ref_shape로 initial_shape 전달).")
            new_opposite_c_coords, new_adjacent_c_coords = _fill_opposite_quadrant(working_shape, (c_quad_idx + 2) % 4, highest_c_layer, initial_shape)
            _log(f"DEBUG: 반대 사분면 c 채운 후 working_shape: {repr(working_shape)}")

            # 새로 추가된 '옆' c 조각들의 바로 아래가 빈 공간일 경우 c 추가
            _log("DEBUG: 새로 추가된 '옆' c 조각 아래 빈 공간 채우기 시작...")
            for l_c, q_c in new_adjacent_c_coords: # new_opposite_c_coords 대신 new_adjacent_c_coords 사용
                if l_c > 0: # 0층보다 위인 경우에만 아래를 확인
                    piece_below_c = _get(working_shape, l_c - 1, q_c)
                    if piece_below_c is None: # 바로 아래가 빈 공간이면
                        # 원본 도형에도 해당 위치에 c가 없었는지 확인 (중복 방지)
                        original_piece_below = _get(initial_shape, l_c - 1, q_c)
                        # 3층(인덱스 2) 이상인 경우에만 아래에 c 추가
                        if not (original_piece_below and original_piece_below.shape == 'c') and (l_c - 1 >= 2):
                            _ensure_layer(working_shape, l_c - 1)
                            working_shape.layers[l_c - 1].quadrants[q_c] = Quadrant('c', 'y') # 'd' 대신 'y' 사용
                            _log(f"DEBUG: c ({l_c}, {q_c}) 아래 빈 공간 ({l_c-1}, {q_c})에 'c' 추가 완료 (옆 c 확장으로). ")
            _log(f"DEBUG: 아래 빈 공간 c 채우기 후 working_shape: {repr(working_shape)}")

            _log(f"DEBUG: 공중 작업 후 (파괴 전): {repr(working_shape)}")

            # --- 층 제거 직전 로직: 수집된 윤곽선 크리스탈 제거 ---
            _log(f"DEBUG: 층 제거 직전, 수집된 윤곽선 크리스탈({len(crystals_to_clear_outline)}개) 제거 시작...")
            for l_clear, q_clear in sorted(list(crystals_to_clear_outline)): # 정렬하여 디버그 가독성 향상
                # 원본 크리스탈의 중심 좌표는 제거하지 않음 (이미 crystals_to_clear_outline에서 제외됨)
                # if (l_clear, q_clear) in original_crystal_centers:
                #     _log(f"DEBUG: 윤곽선 위치 ({l_clear}, {q_clear})가 원본 크리스탈 중심이므로 건너뜀.")
                #     continue

                if 0 <= l_clear < len(working_shape.layers) and working_shape.layers[l_clear]:
                    current_piece_at_target = _get(working_shape, l_clear, q_clear)
                    if current_piece_at_target and current_piece_at_target.shape == 'c':
                        _set(working_shape, l_clear, q_clear, None)
                        _log(f"DEBUG: 크리스탈 윤곽선 위치 ({l_clear}, {q_clear})의 크리스탈 제거 완료.")
                    else:
                        _log(f"DEBUG: 크리스탈 윤곽선 위치 ({l_clear}, {q_clear})에 크리스탈 없음 또는 다른 조각({current_piece_at_target.shape if current_piece_at_target else 'None'})이 있어 건너뜀.")
                else:
                    _log(f"DEBUG: 크리스탈 윤곽선 위치 ({l_clear}, {q_clear}) 레이어 존재하지 않음. 건너뜀.")
            _log(f"DEBUG: 윤곽선 크리스탈 제거 후 working_shape: {repr(working_shape)}")

            final_layers = [layer.copy() for layer in working_shape.layers[1:]]
            final_shape = Shape(final_layers)
            
            # Removed: _fill_c_from_pins(final_shape, pins, initial_shape) 
            # Now happens earlier, applied to working_shape.
            
            # Moved here to avoid re-applying to final_shape
            # _fill_c_from_pins(final_shape, pins, initial_shape) # 이미 working_shape에 적용되었으므로 제거
            
            while final_shape.layers and final_shape.layers[-1].is_empty():
                final_shape.layers.pop()
            
            final_code = repr(final_shape)
            _log(f"DEBUG: 최종 반환: {final_code}")
            return final_code

        except _ClawLogicError as e:
            _log(str(e)); return shape_code
        except Exception as e:
            _log(f"DEBUG_EXCEPTION: 예상치 못한 오류: {e}"); traceback.print_exc()
            return shape_code
        finally:
            Shape.MAX_LAYERS = original_max_layers
            _log(f"DEBUG: MAX_LAYERS 원상 복귀 (MAX_LAYERS={Shape.MAX_LAYERS})")
    finally:
        _log_callback = original_callback

def verify_claw_process(original_shape_str: str) -> bool:
    """Claw 처리 후 결과를 검증하는 함수"""
    # 1. claw_process 결과 Shape 객체로 변환
    original_shape = Shape.from_string(original_shape_str)

    # 클로 프로세스 적용
    # claw_process 함수는 문자열을 기대하므로 original_shape_str을 전달합니다.
    processed_shape = Shape.from_string(claw_process(original_shape_str)) # logger=print 제거
    # 3. processed_shape에 push_pin을 적용
    push_pinned_result = processed_shape.push_pin()

    # 4. push_pinned_result와 original_shape가 동일한지 비교
    return repr(push_pinned_result) == original_shape_str