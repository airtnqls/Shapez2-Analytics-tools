# claw_tracer.py: Claw 기능의 임시 구현 및 추적 파일 (최종 수정 버전)

import traceback
from typing import List, Tuple, Dict

# 순환 참조를 피하기 위해 shape 관련 import는 함수 내부로 이동합니다.

# --- 상수 정의 ---
_VALID_SHAPE_CHARS = set('CSRWcPrgbmyuw-:')
_MAX_SHAPE_CODE_LENGTH = 100
_GENERAL_SHAPE_TYPES = {'C', 'R', 'S', 'W'} # 이 일반도형은 S라 불립니다.
_BLOCKER_SHAPE_TYPES = _GENERAL_SHAPE_TYPES.union({'P'})


class _ClawLogicError(Exception):
    """Claw 처리 중 논리 오류 발생 시 조기 종료를 위한 사용자 정의 예외"""
    pass


# --- 로직 헬퍼 함수들 ---

def _validate_shape_code(shape_code: str):
    if not all(char in _VALID_SHAPE_CHARS for char in shape_code) or len(shape_code) > _MAX_SHAPE_CODE_LENGTH:
        raise _ClawLogicError(f"DEBUG_ERROR: 잘못된 도형 코드 형식이거나 너무 깁니다.")

def _get_static_info(shape: 'Shape') -> Tuple[List[int], int]:
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
    return pins, highest_c_info[1]

def _find_s_star_group(start_q: int, shape: 'Shape') -> List[Tuple[int, int]]:
    """설명해주신 규칙에 따라 -S를 중심으로 그룹을 찾습니다."""
    group = set()
    q_to_process = [(1, start_q)] # Start at layer 1 for -S
    print(f"DEBUG: _find_s_star_group 호출됨. 시작: (1, {start_q})")

    while q_to_process:
        l, q = q_to_process.pop(0)
        if (l, q) in group:
            print(f"DEBUG: ({l}, {q}) 이미 그룹에 있음. 건너뜀.")
            continue

        current_piece = shape._get_piece(l, q)
        if not (current_piece and current_piece.shape in _BLOCKER_SHAPE_TYPES): # S 또는 P 조각이 그룹의 일부가 될 수 있음
            print(f"DEBUG: ({l}, {q}) 조각이 일반 도형 또는 P가 아님. 건너뜀.")
            continue

        group.add((l, q))
        print(f"DEBUG: ({l}, {q}) 그룹에 추가됨. 현재 그룹: {sorted(list(group))}")

        for adj_q in [aq for aq in range(4) if shape._is_adjacent(q, aq)]:
            # Rule A and B: Apply to adjacent pieces at the *current layer* (l)
            adj_piece = shape._get_piece(l, adj_q)
            
            if adj_piece and adj_piece.shape in _GENERAL_SHAPE_TYPES: # Found an adjacent general shape
                blocker = shape._get_piece(l + 1, adj_q)
                
                # Rule A: Adjacent S (adj_piece) at current layer (l) has empty space directly above
                if blocker is None:
                    if (l, adj_q) not in group: # Avoid re-adding existing group members
                        print(f"DEBUG: 규칙 A - 인접 ({l}, {adj_q}) 조각 ({adj_piece.shape}) 위가 비어있음. 탐색 큐에 추가.")
                        q_to_process.append((l, adj_q))
                # Rule B: Adjacent S (adj_piece) at current layer (l) is blocked by S/P, and that blocker's top is empty
                elif blocker.shape in _BLOCKER_SHAPE_TYPES and shape._get_piece(l + 2, adj_q) is None:
                    # Only add if not already in group
                    if (l, adj_q) not in group:
                        print(f"DEBUG: 규칙 B - 인접 ({l}, {adj_q}) 조각 ({adj_piece.shape}) 위 ({blocker.shape})가 막혔고, 그 위가 비었음. 탐색 큐에 추가.")
                        q_to_process.append((l, adj_q))
                    if (l + 1, adj_q) not in group: # Add the blocker piece if it's new to the group
                        print(f"DEBUG: 규칙 B - 블로커 ({l+1}, {adj_q}) 조각 ({blocker.shape})도 그룹에 추가. 탐색 큐에 추가.")
                        q_to_process.append((l + 1, adj_q))
    
    print(f"DEBUG: _find_s_star_group 종료. 최종 그룹: {sorted(list(group))}")
    return sorted(list(group))

def _count_empty_above(l: int, q: int, shape: 'Shape', ignored_coords: set[Tuple[int, int]] = None) -> int:
    from shape import Shape
    count = 0
    if ignored_coords is None:
        ignored_coords = set()
    for l_check in range(l + 1, Shape.MAX_LAYERS):
        piece = shape._get_piece(l_check, q)
        if piece is None or (l_check, q) in ignored_coords: # If piece is None or it's one of the ignored (group's own) pieces
            count += 1
        else:
            break # Found a blocking piece that is NOT part of the group
    return count

def _is_sky_open_above(shape: 'Shape', current_l: int, current_q: int) -> bool:
    """주어진 층과 사분면 위로 하늘이 완전히 뚫려 있는지 확인합니다."""
    from shape import Shape
    for l_check in range(current_l + 1, Shape.MAX_LAYERS):
        if shape._get_piece(l_check, current_q) is not None:
            return False
    return True

def _move_s_group(group: List[Tuple[int, int]], shape: 'Shape', ref_shape: 'Shape'):
    """
    그룹을 새로운 규칙에 따라 이동시킵니다.
    1. 각 그룹 사분면의 상단 빈 공간 최소값만큼 일괄 상향 이동.
    2. 이동 후, 유효한 인접 조건(양쪽에 S가 아닌 그룹 외 S가 없을 것)을 만족할 때까지 하향 이동.
    """
    from shape import Layer

    if not group: return

    # 그룹의 원본 위치를 set으로 저장하여 빠른 조회를 위함 (_count_empty_above에서 무시할 좌표)
    original_group_coords = {(l, q) for l, q in group}

    # 1. 각 사분면별 그룹 조각 중 가장 높은 층의 조각 찾기
    highest_layer_per_quadrant_in_group = {}
    for l, q in group:
        if q not in highest_layer_per_quadrant_in_group or l > highest_layer_per_quadrant_in_group[q][0]:
            highest_layer_per_quadrant_in_group[q] = (l, q)
    print(f"DEBUG: 각 사분면의 그룹 최고층 조각: {highest_layer_per_quadrant_in_group}")

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
    print(f"DEBUG: 그룹 {group}의 초기 이동 거리 (최소 연속 빈 공간): {initial_shift}")

    # 2. 유효한 위치를 찾을 때까지 하향 이동 반복
    # current_shift는 최종적으로 적용될 상대적인 이동 거리 (original layer + current_shift = final layer)
    # initial_shift에서 시작하여 필요하면 1씩 감소합니다.
    current_relative_shift = initial_shift
    
    while True:
        if current_relative_shift < 0: # Prevent going below original layer
            current_relative_shift = 0
            print(f"DEBUG: 0층 아래로 내려갈 수 없음. 최종 유효 이동 거리: {current_relative_shift}")
            break # Stop descending if we hit the bottom

        is_current_position_valid = True
        
        # Calculate hypothetical positions for the current shift
        hypothetical_group_positions = {(l_orig + current_relative_shift, q_orig) for l_orig, q_orig in group}
        
        print(f"DEBUG: 유효성 검사 시작 (현재 상대 이동: {current_relative_shift}). 가상 그룹 위치: {hypothetical_group_positions}")

        # 유효성 검사용 임시 도형 생성: working_shape에서 그룹 조각들을 제거한 상태
        temp_shape_for_validation = shape.copy()
        # 그룹의 원본 위치에 해당하는 조각들을 temp_shape_for_validation에서 제거
        for l_orig, q_orig in group:
            if l_orig < len(temp_shape_for_validation.layers) and temp_shape_for_validation.layers[l_orig]:
                temp_shape_for_validation.layers[l_orig].quadrants[q_orig] = None
        print(f"DEBUG: 유효성 검사용 임시 도형 (그룹 조각 제거 후): {repr(temp_shape_for_validation)}")

        # Check validity based on the rule: "각 그룹의 S들의 양쪽에 그룹이 아닌 S가 하나라도 있을 경우, 그 위치는 허용되지않은 위치이므로, 한칸 내립니다."
        for l_orig, q_orig in group:
            l_hypo, q_hypo = l_orig + current_relative_shift, q_orig

            # Only check for 'S' pieces within the group, ignore 'P' or others if they were part of group
            original_piece_type = ref_shape._get_piece(l_orig, q_orig)
            print(f"DEBUG: 유효성 검사 중 - 그룹 조각 (원본): ({l_orig}, {q_orig}), 가상: ({l_hypo}, {q_hypo}), 유형: {original_piece_type.shape if original_piece_type else 'None'}")
            if not original_piece_type or original_piece_type.shape not in _GENERAL_SHAPE_TYPES: # 'S' (일반 도형) 조각이 아니면 건너뜀
                print(f"DEBUG: ({l_orig}, {q_orig})은 S (일반 도형) 조각이 아님. 인접 검사 건너뜀.")
                continue # Only check S pieces within the group

            # Check adjacent quadrants at the hypothetical layer
            for adj_q in [aq for aq in range(4) if shape._is_adjacent(q_hypo, aq)]:
                # Use temp_shape_for_validation for checking adjacent pieces
                adjacent_piece_at_hypo_l = temp_shape_for_validation._get_piece(l_hypo, adj_q) # temp_shape 사용
                print(f"DEBUG:   - 인접 조각 검사: 가상 ({l_hypo}, {adj_q}), 유형: {adjacent_piece_at_hypo_l.shape if adjacent_piece_at_hypo_l else 'None'}")

                # Is it an 'S' and NOT part of the hypothetical group itself?
                is_adjacent_s = (adjacent_piece_at_hypo_l and adjacent_piece_at_hypo_l.shape in _GENERAL_SHAPE_TYPES)
                is_not_group_member = ((l_hypo, adj_q) not in hypothetical_group_positions)
                
                print(f"DEBUG:     - is_adjacent_s: {is_adjacent_s}, is_not_group_member: {is_not_group_member}")

                if is_adjacent_s and is_not_group_member:
                    
                    print(f"DEBUG: 유효성 검사 실패! 그룹 'S' 조각 ({l_hypo}, {q_hypo}) 옆({adj_q})에 그룹 외 'S' 조각({adjacent_piece_at_hypo_l.shape})이 있음.")
                    is_current_position_valid = False
                    break # Found an invalid adjacency, no need to check further for this shift
            
            if not is_current_position_valid:
                break # Break if invalidity found for any piece in the group

        if is_current_position_valid:
            print(f"DEBUG: 유효성 검사 통과. 최종 상대 이동 거리: {current_relative_shift}")
            break # Found a valid position, exit descent loop
        else:
            current_relative_shift -= 1 # Move down one layer and re-check
            print(f"DEBUG: 유효성 검사 실패. 한 칸 내림. 새 상대 이동: {current_relative_shift}")

    final_shift = current_relative_shift # This is the final net shift from original position

    # --- 최종 이동 실행 ---
    if final_shift != 0: # Only move if there's a net shift
        print(f"DEBUG: 그룹 {group}을(를) 최종적으로 {final_shift}칸 이동 실행.")
        
        pieces_to_move_with_original_coords = [
            {'piece': ref_shape._get_piece(l, q), 'from': (l, q)} for l, q in group
        ]
        
        # Sort by layer descending for clearing (to avoid overwriting before clearing)
        # This is important if moving downwards, but also good practice.
        pieces_to_move_with_original_coords.sort(key=lambda x: x['from'][0], reverse=True)

        # 1. 원본 위치의 조각들 모두 제거
        for item in pieces_to_move_with_original_coords:
            l_orig, q_orig = item['from']
            if l_orig < len(shape.layers) and shape.layers[l_orig]: # Ensure layer exists before accessing
                shape.layers[l_orig].quadrants[q_orig] = None
        
        # 2. 계산된 새 위치에 조각들 배치
        for item in pieces_to_move_with_original_coords:
            l_orig, q_orig = item['from']
            piece_obj = item['piece']
            
            new_l = l_orig + final_shift
            new_q = q_orig # Quadrant doesn't change
            
            # Ensure new_l is within bounds and layers exist
            if new_l < 0: new_l = 0 # Clamp to 0
            
            while len(shape.layers) <= new_l:
                shape.layers.append(Layer([None]*4))
            
            shape.layers[new_l].quadrants[new_q] = piece_obj
            print(f"DEBUG: 조각 {piece_obj.shape} {item['from']} -> ({new_l}, {new_q})로 이동 완료.")
    else:
        print(f"DEBUG: 최종 이동 거리 0. 그룹 {group} 이동 없음.")

def _find_twice_floating_s_group(start_l: int, start_q: int, shape: 'Shape', enable_s_below_rule: bool = False) -> List[Tuple[int, int]]:
    """'두번 뜬 S'를 중심으로 그룹을 찾습니다."""
    group = set()
    q_to_process = [(start_l, start_q)]
    print(f"DEBUG: _find_twice_floating_s_group 호출됨. 시작: ({start_l}, {start_q})")

    while q_to_process:
        l, q = q_to_process.pop(0)
        if (l, q) in group:
            print(f"DEBUG: ({l}, {q}) 이미 그룹에 있음. 건너뜀.")
            continue

        current_piece = shape._get_piece(l, q)
        if not (current_piece and current_piece.shape in _GENERAL_SHAPE_TYPES): # Only general shapes can be part of the group
            print(f"DEBUG: ({l}, {q}) 조각이 일반 도형이 아님. 건너뜀.")
            continue

        group.add((l, q))
        print(f"DEBUG: ({l}, {q}) 그룹에 추가됨. 현재 그룹: {sorted(list(group))}")

        # Rule 1: Adjacent S on the same layer with empty space above
        for adj_q in [aq for aq in range(4) if shape._is_adjacent(q, aq)]:
            adj_l = l
            adj_piece = shape._get_piece(adj_l, adj_q)
            if (adj_piece and adj_piece.shape in _GENERAL_SHAPE_TYPES and
                shape._get_piece(adj_l + 1, adj_q) is None): # Empty above adjacent piece
                if (adj_l, adj_q) not in group:
                    print(f"DEBUG: 규칙 1 - 인접 ({adj_l}, {adj_q}) 조각 ({adj_piece.shape}) 위가 비어있음. 탐색 큐에 추가.")
                    q_to_process.append((adj_l, adj_q))
        
        # Rule 2: S below the current piece (that was just added to the group)
        if enable_s_below_rule and l > 0: # Ensure we don't go below layer 0
            piece_below = shape._get_piece(l - 1, q)
            if (piece_below and piece_below.shape in _GENERAL_SHAPE_TYPES): # Check if piece below is general shape
                if (l - 1, q) not in group:
                    print(f"DEBUG: 규칙 2 - 아래 ({l-1}, {q}) 조각 ({piece_below.shape})이 일반 도형임. 탐색 큐에 추가.")
                    q_to_process.append((l - 1, q))
    
    print(f"DEBUG: _find_twice_floating_s_group 종료. 최종 그룹: {sorted(list(group))}")
    return sorted(list(group))

def _relocate_s_pieces(working_shape: 'Shape', ref_shape: 'Shape'):
    """S 조각들을 재배치/생성합니다. 그룹화를 먼저 처리합니다."""
    from shape import Quadrant
    
    processed_q = set()
    print(f"DEBUG: _relocate_s_pieces 호출됨. 초기 processed_q: {processed_q}")
    print(f"DEBUG: Initial ref_shape: {repr(ref_shape)}") # ref_shape의 전체 표현 추가

    # New: 0. '두번 뜬 S' 그룹 탐색 및 처리 (최우선)
    print("DEBUG: '두번 뜬 S' 패턴 탐색 시작...")
    # Pattern: Layer 1 is None, Layer 2 is 'S', Layer 3 is None, Layer 4 is 'S' or 'C'
    twice_floating_s_q_indices = []
    for q_idx in range(4):
        # Layer 0 (1층) can be anything, so no check here.
        p1 = ref_shape._get_piece(1, q_idx) # Layer 1 (2층)
        p2 = ref_shape._get_piece(2, q_idx) # Layer 2 (3층)
        p3 = ref_shape._get_piece(3, q_idx) # Layer 3 (4층)
        p4 = ref_shape._get_piece(4, q_idx) # Layer 4 (5층)

        print(f"DEBUG: '두번 뜬 S' 검사 중 - 사분면 {q_idx}:\n" \
              f"  2층(L1): {p1}\n" \
              f"  3층(L2): {p2}\n" \
              f"  4층(L3): {p3}\n" \
              f"  5층(L4): {p4}")

        if (p1 is None and # 2층이 비어있고
            p2 and p2.shape in _GENERAL_SHAPE_TYPES and # 3층이 S이고 (여기 수정됨)
            p3 is None and # 4층이 비어있고
            p4 and p4.shape in _GENERAL_SHAPE_TYPES.union({'c'})): # 5층이 S or C인경우. (여기 수정됨)
            twice_floating_s_q_indices.append(q_idx)
            print(f"DEBUG: '두번 뜬 S' 후보 발견: 사분면 {q_idx}")
        else:
            print(f"DEBUG: 사분면 {q_idx}는 '두번 뜬 S' 패턴과 불일치.")
    
    if twice_floating_s_q_indices:
        print(f"DEBUG: '두번 뜬 S' 그룹 탐색 및 처리 시작 (시작점 후보: {twice_floating_s_q_indices})...")
        for s_q_idx in twice_floating_s_q_indices:
            # The actual 'S' for 'twice floating S' is at layer 2
            if (2, s_q_idx) in processed_q:
                print(f"DEBUG: ({2}, {s_q_idx}) 이미 처리된 '두번 뜬 S'의 일부임. 건너뜀.")
                continue
            
            # Check if layer 0 (1층) is 'P' for this specific quadrant
            p0_at_s_q_idx = ref_shape._get_piece(0, s_q_idx)
            enable_s_below = (p0_at_s_q_idx and p0_at_s_q_idx.shape == 'P')
            print(f"DEBUG: 사분면 {s_q_idx}의 1층(L0)은 P: {enable_s_below}")

            group = _find_twice_floating_s_group(2, s_q_idx, working_shape, enable_s_below) # enable_s_below 전달
            if group: # Only process if a group was actually found
                print(f"DEBUG: 사분면 {s_q_idx} (2층)을(를) 중심으로 '두번 뜬 S' 그룹 발견: {group}")
                print(f"DEBUG: _move_s_group 호출 (ref_shape로 working_shape 전달). 현재 working_shape: {repr(working_shape)}") # 로그 추가
                _move_s_group(group, working_shape, working_shape) # ref_shape를 working_shape로 변경
                processed_q.update(group) # Update with all coords in the moved group
                print(f"DEBUG: '두번 뜬 S' 그룹 처리 후 processed_q: {processed_q}")

    # 1. 뜬 S(-S)를 중심으로 그룹 형성 및 처리 (기존 로직)
    print(f"DEBUG: '뜬 S(-S)' 그룹 탐색 시작. 현재 processed_q: {processed_q}")
    # Floating S: Layer 0 is None, Layer 1 is S/C/R/W
    floating_s_q_indices = [
        q for q in range(4) if ref_shape._get_piece(0, q) is None and 
        (p1 := ref_shape._get_piece(1, q)) and p1.shape in _GENERAL_SHAPE_TYPES
    ]
    if floating_s_q_indices:
        print(f"DEBUG: '뜬 S(-S)' 그룹 탐색 및 처리 시작 (시작점 후보: {floating_s_q_indices})...")
        for s_q_idx in floating_s_q_indices:
            # Check if this (1, s_q_idx) was already part of a 'twice floating S' group
            if (1, s_q_idx) in processed_q:
                print(f"DEBUG: ({1}, {s_q_idx}) 이미 처리된 그룹의 일부임. 건너뜀.")
                continue
            
            group = _find_s_star_group(s_q_idx, working_shape)
            if group: # Only process if a group was actually found
                print(f"DEBUG: 사분면 {s_q_idx}을(를) 중심으로 그룹 발견: {group}")
                print(f"DEBUG: _move_s_group 호출 (ref_shape로 working_shape 전달). 현재 working_shape: {repr(working_shape)}") # 로그 추가
                _move_s_group(group, working_shape, working_shape) # ref_shape를 working_shape로 변경
                processed_q.update(group) # Update with all coords in the moved group
                print(f"DEBUG: '뜬 S(-S)' 그룹 처리 후 processed_q: {processed_q}")
            
    # 2. 그룹에 속하지 않은 바닥 S 개별 처리 (기존 로직)
    print(f"DEBUG: '바닥 S' 개별 처리 시작. 현재 processed_q: {processed_q}")
    bottom_s_q_indices = [
        q for q in range(4) if (p0 := ref_shape._get_piece(0, q)) and p0.shape in _GENERAL_SHAPE_TYPES
    ]
    ungrouped_bottom_s = [q for q in bottom_s_q_indices if (0, q) not in processed_q] # Check if base S itself was processed
    if ungrouped_bottom_s:
        print(f"DEBUG: '바닥 S' 개별 처리 시작 (대상: {ungrouped_bottom_s})...")
        for s_q_idx in ungrouped_bottom_s:
            # This is where the _find_s_relocation_spot and subsequent placement happens.
            # No need to check processed_q again here as it's for individual base S.
            # The relocation places new 'C's, which won't be in processed_q from previous moves.
            print(f"DEBUG: _find_s_relocation_spot 호출 (ref_shape로 working_shape 전달). 현재 working_shape: {repr(working_shape)}") # 로그 추가
            l_target, fill_c = _find_s_relocation_spot(working_shape, s_q_idx, working_shape) # ref_shape를 working_shape로 변경
            print(f"DEBUG: 사분면 {s_q_idx}의 '바닥 S' 재배치 위치: L{l_target}, 채울 C: {fill_c}")
            if l_target != -1:
                # The piece at (0, s_q_idx) is effectively removed later by slicing layers[1:]
                # So we are placing a *new* C at l_target.
                working_shape.layers[l_target].quadrants[s_q_idx] = Quadrant('C', 'u')
                print(f"DEBUG: ({l_target}, {s_q_idx})에 'C' 배치됨.")
                _place_and_propagate_c(working_shape, fill_c, ref_shape)

def _find_s_relocation_spot(shape: 'Shape', q_idx: int, ref_shape: 'Shape') -> Tuple[int, List[Tuple[int, int]]]: # ref_shape 추가
    """개별 S를 배치할 최적 위치를 찾습니다."""
    from shape import Shape, Layer
    print(f"DEBUG: _find_s_relocation_spot 호출됨. q_idx: {q_idx}")

    # Case 1: Sky is open above the current quadrant
    # Check if the sky is open from layer 0 upwards for the specific quadrant.
    # If so, find the *first* available spot according to original adjacency rules.
    if _is_sky_open_above(shape, 0, q_idx):
        print(f"DEBUG: _find_s_relocation_spot - Case 1 (하늘이 열려있음)")
        for l_idx in range(0, Shape.MAX_LAYERS):
            adj = [q for q in range(4) if shape._is_adjacent(q_idx, q)]
            if len(adj) != 2: # Keep original defensive check
                continue
            p1, p2 = shape._get_piece(l_idx, adj[0]), shape._get_piece(l_idx, adj[1])

            # Original condition: both adjacent spots must not be blocked by general shapes
            if not (p1 and p1.shape in _GENERAL_SHAPE_TYPES) and not (p2 and p2.shape in _GENERAL_SHAPE_TYPES):
                print(f"DEBUG: Case 1 - 적합한 위치 찾음: L{l_idx}, 인접 채울 C: {[(l_idx, a) for a, p in zip(adj, [p1,p2]) if p is None]}")
                return l_idx, [(l_idx, a) for a, p in zip(adj, [p1,p2]) if p is None]
        print(f"DEBUG: Case 1 - 적합한 위치 찾지 못함.")
        return -1, [] # No suitable spot found even with open sky

    # Case 2: Sky is NOT open above the current quadrant
    # Find the highest possible layer `l_target` such that it satisfies adjacency rules
    # AND the layer directly above is blocked, or it is the top layer.
    # The search stops as soon as a valid layer with a blocker above is found.
    print(f"DEBUG: _find_s_relocation_spot - Case 2 (하늘이 닫혀있음)")
    
    # 1. '천장' (가장 낮은 층의 블로커) 찾기
    top_blocker_layer = Shape.MAX_LAYERS # 기본값: 천장 없음 (모두 비어있음)
    for l_check in range(1, Shape.MAX_LAYERS): # 0층(바닥 S가 있는 층)은 건너뛰고 1층부터 검사
        if shape._get_piece(l_check, q_idx) is not None:
            top_blocker_layer = l_check
            print(f"DEBUG: q_idx {q_idx}의 천장 발견: L{top_blocker_layer} (조각: {shape._get_piece(l_check, q_idx)})")
            break
    
    # 2. 천장 바로 아래칸부터 시작하여 유효성 검사 및 하향 이동 반복
    found_l_target = -1
    current_l_target_attempt = top_blocker_layer - 1
    print(f"DEBUG: 천장({top_blocker_layer}) 아래칸부터 재배치 탐색 시작: L{current_l_target_attempt}")

    while current_l_target_attempt >= 0:
        l_idx = current_l_target_attempt
        print(f"DEBUG: 현재 재배치 시도 층: L{l_idx}, q_idx: {q_idx}")

        # 현재 위치가 비어있는지 확인
        current_spot_piece = ref_shape._get_piece(l_idx, q_idx) # ref_shape를 사용합니다
        if current_spot_piece is not None: 
            print(f"DEBUG: L{l_idx}, q{q_idx} 이미 조각({current_spot_piece.shape}) 있음. 한 칸 내림.")
            current_l_target_attempt -= 1
            continue
        
        # 인접 조건 검사
        can_place_central_c = False
        adj = [q for q in range(4) if shape._is_adjacent(q_idx, q)]
        if len(adj) == 2:
            p1 = ref_shape._get_piece(l_idx, adj[0]) # ref_shape를 사용합니다
            p2 = ref_shape._get_piece(l_idx, adj[1]) # ref_shape를 사용합니다
            if not ((p1 and p1.shape in _GENERAL_SHAPE_TYPES) and \
                    (p2 and p2.shape in _GENERAL_SHAPE_TYPES)):
                can_place_central_c = True
        
        print(f"DEBUG: L{l_idx}, q{q_idx} (비어있음): can_place_central_c={can_place_central_c}")

        if can_place_central_c:
            # 이 위치는 유효한 빈 공간이며 인접 조건도 만족. 여기가 최종 타겟.
            found_l_target = l_idx
            print(f"DEBUG: 유효한 재배치 위치 찾음: L{found_l_target}. 탐색 중단.")
            break
        else:
            # 인접 조건 불만족. 한 칸 내림.
            print(f"DEBUG: L{l_idx}, q{q_idx} 인접 조건 불만족. 한 칸 내림.")
            current_l_target_attempt -= 1

    
    if found_l_target != -1:
        # 최종적으로 결정된 가장 높은 유효한 빈 공간에 대한 fill_c_coords 계산
        adj = [q for q in range(4) if shape._is_adjacent(q_idx, q)]
        fill_c_coords = []
        if len(adj) == 2: # Ensure we have two adjacent quadrants for fill_c
            # fill_c를 계산할 때도 ref_shape를 사용합니다.
            p1 = ref_shape._get_piece(found_l_target, adj[0])
            p2 = ref_shape._get_piece(found_l_target, adj[1])
            if p1 is None:
                fill_c_coords.append((found_l_target, adj[0]))
            if p2 is None:
                fill_c_coords.append((found_l_target, adj[1]))
        print(f"DEBUG: Case 2 - 최종 반환 위치: L{found_l_target}, 채울 C: {fill_c_coords}")
        return found_l_target, fill_c_coords

    print(f"DEBUG: _find_s_relocation_spot - 최종적으로 위치를 찾지 못함. q_idx: {q_idx}")
    return -1, [] # Fallback if no spot found in either case (highly unlikely given MAX_LAYERS)

def _place_and_propagate_c(shape: 'Shape', coords: List[Tuple[int, int]], ref_shape: 'Shape'):
    from shape import Quadrant
    # coords에 지정된 위치에 c 조각을 배치하고 위로 전파
    for l, q in coords:
        if shape._get_piece(l, q) is None:
            shape.layers[l].quadrants[q] = Quadrant('c', 'g')
            _propagate_c_upwards(shape, l + 1, q, ref_shape)

def _propagate_c_upwards(shape, l_start, q, ref_shape):
    from shape import Shape, Layer, Quadrant
    l = l_start
    while l < Shape.MAX_LAYERS:
        if _is_adjacent_to_ref_c(l, q, ref_shape): break
        while len(shape.layers) <= l: shape.layers.append(Layer([None] * 4))
        p = shape._get_piece(l, q)
        if p is None: shape.layers[l].quadrants[q] = Quadrant('c', 'm'); l += 1
        elif p.shape == 'c': l += 1
        else: break

def _is_adjacent_to_ref_c(l, q, ref_shape):
    coords = [(l-1, q), (l+1, q)] + [(l, aq) for aq in range(4) if ref_shape._is_adjacent(q, aq)]
    for cl, cq in coords:
        if 0 <= cl < len(ref_shape.layers) and (p := ref_shape._get_piece(cl, cq)) and p.shape == 'c': return True
    return False

def _fill_opposite_quadrant(shape: 'Shape', opposite_q_idx: int):
    from shape import Shape, Layer, Quadrant
    print(f"DEBUG: 반대 사분면({opposite_q_idx})에 c 채우기...")
    for l_idx in range(Shape.MAX_LAYERS -1, -1, -1):
        while len(shape.layers) <= l_idx: shape.layers.append(Layer([None]*4))
        p = shape._get_piece(l_idx, opposite_q_idx)
        if p is not None and p.shape != 'c': break
        shape.layers[l_idx].quadrants[opposite_q_idx] = Quadrant('c', 'y')

def _fill_c_from_pins(shape: 'Shape', p_indices: list[int]):
    from shape import Quadrant
    if not p_indices or not shape.layers: return
    print("DEBUG: 핀 위치에 c 채우기 (새로운 0층)...")
    for q_idx in p_indices:
        if shape._get_piece(0, q_idx) is None:
            shape.layers[0].quadrants[q_idx] = Quadrant('c', 'b')

# --- 메인 프로세스 함수 ---
def claw_process(shape_code: str) -> str:
    from shape import Shape, Layer
    print(f"DEBUG: claw_process 호출됨. 입력: {shape_code}")
    
    original_max_layers = Shape.MAX_LAYERS
    try:
        _validate_shape_code(shape_code)
        initial_shape = Shape.from_string(shape_code)
        working_shape = initial_shape.copy()
        print(f"DEBUG: 초기 도형: {repr(initial_shape)}")
        pins, c_quad_idx = _get_static_info(initial_shape)

        Shape.MAX_LAYERS += 1
        working_shape.layers.append(Layer([None]*4))
        print(f"DEBUG: 임시 공간 확보 (MAX_LAYERS={Shape.MAX_LAYERS})")

        _relocate_s_pieces(working_shape, initial_shape)
        _fill_opposite_quadrant(working_shape, (c_quad_idx + 2) % 4)
        print(f"DEBUG: 공중 작업 후 (파괴 전): {repr(working_shape)}")

        final_layers = [layer.copy() for layer in working_shape.layers[1:]]
        final_shape = Shape(final_layers)
        
        _fill_c_from_pins(final_shape, pins)
        
        while final_shape.layers and final_shape.layers[-1].is_empty():
            final_shape.layers.pop()
        
        final_code = repr(final_shape)
        print(f"DEBUG: 최종 반환: {final_code}")
        return final_code

    except _ClawLogicError as e:
        print(str(e)); return shape_code
    except Exception as e:
        print(f"DEBUG_EXCEPTION: 예상치 못한 오류: {e}"); traceback.print_exc()
        return shape_code
    finally:
        Shape.MAX_LAYERS = original_max_layers
        print(f"DEBUG: MAX_LAYERS 원상 복귀 (MAX_LAYERS={Shape.MAX_LAYERS})")

def verify_claw_process(original_shape_str: str) -> bool:
    """Claw 처리 후 결과를 검증하는 함수"""
    from shape import Shape, Layer, Quadrant # Import necessary classes locally
    # 1. claw_process 결과 Shape 객체로 변환
    original_shape = Shape.from_string(original_shape_str)

    # 클로 프로세스 적용
    # claw_process 함수는 문자열을 기대하므로 original_shape_str을 전달합니다.
    processed_shape = Shape.from_string(claw_process(original_shape_str))
    # 3. processed_shape에 push_pin을 적용
    push_pinned_result = processed_shape.push_pin()

    # 4. push_pinned_result와 original_shape가 동일한지 비교
    return repr(push_pinned_result) == original_shape_str