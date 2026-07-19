"""
하이브리드 도형 분석 모듈

이 모듈은 Shape 클래스의 하이브리드 분석 로직을 담당합니다.
하이브리드 분석은 도형을 마스크 기반으로 두 부분으로 분리하는 기능을 제공합니다.
"""

from typing import Set, Tuple
from shape import Shape, Layer, Quadrant

DEBUG_HYBRID = False

def _find_unstable_coords_by_physics(s: Shape) -> Set[Tuple[int, int]]:
    """도형 s에 대해 물리 적용 전/후를 비교하여 하층부터 불안정 좌표를 추정합니다.
    반환 좌표는 (layer, quadrant)이며, 하층(작은 layer) 우선으로 정렬 가능한 집합입니다.
    """
    try:
        s_before = s.copy()
        s_after = s.apply_physics()
        if repr(s_before) == repr(s_after):
            return set()
        # 단순 휴리스틱: 아래층부터 조각이 사라졌거나 이동한 분면을 불안정으로 표시
        unstable = set()
        max_layers = max(len(s_before.layers), len(s_after.layers))
        for l in range(max_layers):
            for q in range(4):
                pb = s_before._get_piece(l, q) if l < len(s_before.layers) else None
                pa = s_after._get_piece(l, q) if l < len(s_after.layers) else None
                if (pb and not pa) or (pb and pa and (pb.shape != pa.shape or pb.color != pa.color)):
                    unstable.add((l, q))
        return unstable
    except Exception:
        return set()

def _build_outputs_from_mask(shape: Shape, mask: dict) -> Tuple[Shape, Shape]:
    """현재 마스크 기준으로 출력 A(마스크0), B(마스크1)를 구성합니다.
    기존 단계 6의 출력 구성 로직을 그대로 사용합니다.
    """
    output_a_layers = []
    output_b_layers = []
    for l in range(len(shape.layers)):
        layer_a_quadrants = [None] * 4
        layer_b_quadrants = [None] * 4
        for q in range(4):
            piece = shape._get_piece(l, q)
            if piece:
                if mask.get((l, q), 0) == 0:
                    layer_a_quadrants[q] = piece.copy()
                else:
                    layer_b_quadrants[q] = piece.copy()
        output_a_layers.append(Layer(layer_a_quadrants))
        output_b_layers.append(Layer(layer_b_quadrants))

    output_a = Shape(output_a_layers)
    output_b = Shape(output_b_layers)
    output_a.max_layers = shape.max_layers
    output_b.max_layers = shape.max_layers

    return output_a, output_b

def _debug_print_mask(shape: Shape, mask: dict, title: str = None) -> None:
    """DEBUG: 현재 마스크를 층별 한 줄로 출력합니다.

    표기 규칙:
    - 각 분면은 [n:토큰] 형태로 표시 (토큰은 [조각문자][마스크값], 예: S0, c1, -1)
    - 분면 순서: [1,2,3,4] = [0=TR, 1=BR, 2=BL, 3=TL]
    - 출력 순서: 위층 → 아래층
    """
    if not DEBUG_HYBRID:
        return
    if title:
        print(f"=== {title} ===")
    if not shape.layers:
        print("(빈 도형)")
        return

    for l in range(len(shape.layers) - 1, -1, -1):  # 위층부터 출력
        tokens = []
        for q in [0, 1, 2, 3]:
            mv = mask.get((l, q), 0)
            tokens.append(str(mv))
        print(f"L{l}: {tokens[0]} {tokens[1]} {tokens[2]} {tokens[3]}")
    print("----------------")

def hybrid(shape: Shape) -> Tuple[Shape, Shape]:
    """
    하이브리드 함수: 입력을 마스크 기반으로 두 부분으로 분리합니다.
    
    Args:
        shape: 분석할 도형
        
    Returns:
        (output_a, output_b): 마스크 0 부분과 마스크 1 부분으로 분리된 두 도형
    """
    if DEBUG_HYBRID:
        try:
            print("=== HYBRID DEBUG START ===")
            print(f"입력: {repr(shape)}")
        except Exception:
            pass

    mask = {}
    
    # 1. 각 셀에 대응되는 (사분면x층) 크기의 임시 마스크를 만듭니다 (1로 초기화)
    for l in range(len(shape.layers)):
        for q in range(4):
            mask[(l, q)] = 1
    
    
    # 2. 각 사분면의 가장 높은 크리스탈을 찾습니다
    for q in range(4):
        highest_crystal_layer = -1
        for l in range(len(shape.layers) - 1, -1, -1):  # 위에서부터 탐색
            piece = shape._get_piece(l, q)
            if piece and piece.shape == 'c':
                highest_crystal_layer = l
                break
        
        # 각 크리스탈과 그 아래는 모두 마스크 영역을 0로 만듭니다
        if highest_crystal_layer >= 0:
            for l in range(highest_crystal_layer + 1):  # 해당 층과 그 아래 모든 층
                mask[(l, q)] = 0
    
    if DEBUG_HYBRID:
        _debug_print_mask(shape, mask, "단계 2: 크리스탈 기반 0 적용")
        
    # 3. 마스크 0 영역에서 불안정 도형 보정 (아래층부터 반복)
    while True:
        # 현재 마스크 기준으로 temp_shape 구성 (마스크 0 부분만 포함)
        temp_layers = []
        for l in range(len(shape.layers)):
            temp_quadrants = [None] * 4
            for q in range(4):
                if mask.get((l, q), 0) == 0:
                    piece = shape._get_piece(l, q)
                    if piece:
                        temp_quadrants[q] = piece.copy()
            temp_layers.append(Layer(temp_quadrants))

        temp_shape = Shape(temp_layers)

        # 마스크를 리버스하여 전달 (1과 0을 바꿈) → 마스크 0 영역의 불안정 좌표 계산
        reversed_mask = {k: 1 - v for k, v in mask.items()}
        unstable_coords = _find_unstable_at_layer(temp_shape, 0, reversed_mask)
        base_unstable_exists = bool(unstable_coords)

        if DEBUG_HYBRID:
            if unstable_coords:
                coords_display = [f"(L{l},Q{q+1})" for l, q in sorted(list(unstable_coords))]
                print(f"[3] 불안정 좌표: {', '.join(coords_display)}")
            else:
                print(f"[3] 불안정 좌표: 없음")

        # 기본 불안정이 전혀 없어도, simple_cutter 보조 검사를 진행합니다.

        # 아래층 우선으로 하나 처리 후 재평가
        mask_changed = False
        for unstable_l, unstable_q in sorted(list(unstable_coords), key=lambda x: (x[0], x[1])):
            if DEBUG_HYBRID:
                p = shape._get_piece(unstable_l, unstable_q)
                pch = p.shape if p else '-'
                print(f"  - 대상: L{unstable_l} Q{unstable_q+1} (piece={pch})")

            # 인접 분면 (동일층)
            if unstable_q == 0:
                adjacent_quads = [1, 3]
            elif unstable_q == 1:
                adjacent_quads = [0, 2]
            elif unstable_q == 2:
                adjacent_quads = [1, 3]
            else:
                adjacent_quads = [0, 2]

            if DEBUG_HYBRID:
                print(f"    인접 분면(동일층): {[q+1 for q in adjacent_quads]}")

            found_adjacent = False
            for check_q in adjacent_quads:
                if (mask.get((unstable_l, check_q), 0) == 1 and 
                    (pc := shape._get_piece(unstable_l, check_q)) and pc.shape == 'S'):
                    for below_l in range(unstable_l + 1):
                        mask[(below_l, check_q)] = 0
                    if DEBUG_HYBRID:
                        print(f"    동일층 S 발견: L{unstable_l} Q{check_q+1} → 열 마스크 0")
                    mask_changed = True
                    found_adjacent = True
                    break

            # 동일층 실패, c 위에 c'인 경우 위층에서 재탐색
            if (not found_adjacent and 
                (p0 := shape._get_piece(unstable_l, unstable_q)) and p0.shape == 'c' and 
                unstable_l + 1 < len(shape.layers) and 
                (p1 := shape._get_piece(unstable_l + 1, unstable_q)) and p1.shape == 'c'):
                upper_l = unstable_l + 1
                if DEBUG_HYBRID:
                    print(f"    동일층 S 없음, 위층 c' 감지 → L{upper_l}에서 인접 S 탐색")
                for check_q in adjacent_quads:
                    if (mask.get((upper_l, check_q), 0) == 1 and 
                        (pu := shape._get_piece(upper_l, check_q)) and pu.shape == 'S'):
                        for below_l in range(upper_l + 1):
                            mask[(below_l, check_q)] = 0
                        if DEBUG_HYBRID:
                            print(f"    위층 S 발견: L{upper_l} Q{check_q+1} → 열 마스크 0")
                        mask_changed = True
                        break

            if not found_adjacent and DEBUG_HYBRID:
                print("    인접 S 없음: 변경 없음")

            if mask_changed:
                if DEBUG_HYBRID:
                    _debug_print_mask(shape, mask, "단계 3: 변경 후 마스크")
                break  # 한 건 처리 후 즉시 재평가

        if mask_changed:
            continue

        # 위 처리로 변경이 없었다면, simple_cutter 기반 물리검사로 보조 판단
        sc_changed = False
        # 1) 수직 분할 (horizontal=False)
        west, east = temp_shape.simple_cutter(horizontal=False)
        for part in [west, east]:
            unstable_by_physics = _find_unstable_coords_by_physics(part)
            if unstable_by_physics:
                l0, q0 = min(unstable_by_physics, key=lambda x: (x[0], x[1]))
                # 원래 좌표계와 동일 (temp_shape와 동일한 레이어/사분면 인덱스)
                # 인접 S 로직 재사용
                if q0 == 0:
                    adj_qs = [1, 3]
                elif q0 == 1:
                    adj_qs = [0, 2]
                elif q0 == 2:
                    adj_qs = [1, 3]
                else:
                    adj_qs = [0, 2]
                for check_q in adj_qs:
                    if (mask.get((l0, check_q), 0) == 1 and 
                        (pc := shape._get_piece(l0, check_q)) and pc.shape == 'S'):
                        for bl in range(l0 + 1):
                            mask[(bl, check_q)] = 0
                        sc_changed = True
                        if DEBUG_HYBRID:
                            print(f"    [SC-수직] L{l0} Q{check_q+1} → 열 마스크 0")
                        break
                if sc_changed:
                    break
        if sc_changed:
            if DEBUG_HYBRID:
                _debug_print_mask(shape, mask, "단계 3: SC(수직) 변경 후 마스크")
            continue  # 수평 분할은 생략하고 재평가

        # 2) 수평 분할 (horizontal=True) — 기본 불안정이 없는 경우에만 검사
        if not base_unstable_exists and not sc_changed:
            north, south = temp_shape.simple_cutter(horizontal=True)
            for part in [north, south]:
                unstable_by_physics = _find_unstable_coords_by_physics(part)
                if unstable_by_physics:
                    l0, q0 = min(unstable_by_physics, key=lambda x: (x[0], x[1]))
                    if q0 == 0:
                        adj_qs = [1, 3]
                    elif q0 == 1:
                        adj_qs = [0, 2]
                    elif q0 == 2:
                        adj_qs = [1, 3]
                    else:
                        adj_qs = [0, 2]
                    for check_q in adj_qs:
                        if (mask.get((l0, check_q), 0) == 1 and 
                            (pc := shape._get_piece(l0, check_q)) and pc.shape == 'S'):
                            for bl in range(l0 + 1):
                                mask[(bl, check_q)] = 0
                            sc_changed = True
                            if DEBUG_HYBRID:
                                print(f"    [SC-수평] L{l0} Q{check_q+1} → 열 마스크 0")
                            break
                    if sc_changed:
                        break
        elif DEBUG_HYBRID and base_unstable_exists:
            print("    [SC-수평] 기본 불안정 존재 → 수평 검사는 다음 라운드로 보류")

        if sc_changed:
            if DEBUG_HYBRID:
                _debug_print_mask(shape, mask, "단계 3: SC(수평) 변경 후 마스크")
            continue

        # 모든 검사에서 변경이 없었고, 기본 불안정도 없으면 종료 (무한 루프 방지)
        if not unstable_coords:
            break
        else:
            # 기본 불안정은 있었으나 인접 S/보조 검사로는 손댈 수 없음 → 종료
            break

    if DEBUG_HYBRID:
        _debug_print_mask(shape, mask, "단계 3: 불안정 보정 완료")
    
    # 4. 특별 조건 검사: S 도형이 아래가 비어있고 옆 사분면이 마스크 0이면서 S 또는 c인 경우
    # 아래 레이어부터 위로 검사
    for current_layer in range(len(shape.layers)):
        for q in range(4):
            coord = (current_layer, q)
            if mask.get(coord, 0) != 1:
                continue
            
            piece = shape._get_piece(current_layer, q)
            if not piece or piece.shape != 'S':
                continue
            
            # 아래가 비어있는지 확인
            below_empty = current_layer == 0 or not shape._get_piece(current_layer-1, q)
            if not below_empty:
                continue
            
            # 현재 상태에서 지지되는지 확인
            temp_layers = []
            for l in range(len(shape.layers)):
                temp_quadrants = [None] * 4
                for tq in range(4):
                    if mask.get((l, tq), 0) == 1:
                        temp_piece = shape._get_piece(l, tq)
                        if temp_piece:
                            temp_quadrants[tq] = temp_piece.copy()
                temp_layers.append(Layer(temp_quadrants))
            
            temp_shape = Shape(temp_layers)
            unstable_coords = _find_unstable_at_layer(temp_shape, current_layer, mask)
            
            # 현재 좌표가 불안정한 경우에만 특별 조건 적용
            if coord in unstable_coords:
                # 옆 사분면 검사
                special_support_found = False
                for nq in range(4):
                    if _is_adjacent(q, nq):
                        neighbor_coord = (current_layer, nq)
                        if mask.get(neighbor_coord, 0) == 0:
                            neighbor_piece = shape._get_piece(*neighbor_coord)
                            if neighbor_piece and neighbor_piece.shape in ['S', 'c']:
                                special_support_found = True
                                break
                
                # 특별 조건이 만족되면 해당 좌표와 그 아래 모든 층을 마스크 0으로 변경
                if special_support_found:
                    for below_l in range(current_layer + 1):
                        mask[(below_l, q)] = 0
    if DEBUG_HYBRID:
        _debug_print_mask(shape, mask, "단계 4: 특별 조건 적용 후 마스크")
    
    # 5. 수정된 물리 적용으로 불안정한 도형 검사 (층별 순차 처리)
    # 맨 위 층부터 순서대로 아래로 진행
    for current_layer in range(len(shape.layers) - 1, -1, -1):  # 맨 위부터 아래로
        # 현재 층에서 마스크 1인 부분만 추출하여 임시 도형 생성
        temp_layers = []
        for l in range(len(shape.layers)):
            temp_quadrants = [None] * 4
            for q in range(4):
                if mask.get((l, q), 0) == 1:
                    piece = shape._get_piece(l, q)
                    if piece:
                        temp_quadrants[q] = piece.copy()
            temp_layers.append(Layer(temp_quadrants))
        
        temp_shape = Shape(temp_layers)
        
        # 현재 층에서 불안정한 도형 탐색
        unstable_coords = _find_unstable_at_layer(temp_shape, current_layer, mask)
        
        # 불안정한 도형과 그 아래의 마스크를 0으로 만듭니다
        for l, q in unstable_coords:
            for below_l in range(l + 1):  # 해당 층과 그 아래 모든 층
                mask[(below_l, q)] = 0
    if DEBUG_HYBRID:
        _debug_print_mask(shape, mask, "단계 5: 물리 검사 후 마스크")
    
    # 6. 출력 A (마스크 0 부분만), 출력 B (마스크 1 부분만)
    output_a, output_b = _build_outputs_from_mask(shape, mask)

    # 7. Stack 검증 및 output_a 분류 검증 반복 (무거운 연산이므로 최적화해야함.)
    if DEBUG_HYBRID:
        print("=== 단계 7: Stack 검증/분류 검증/마스크 최저층 상승 반복 ===")
    try:
        original_repr = repr(shape)
        min_floor = min((l for (l, _) in mask.keys()), default=0)
        max_floor = shape.max_layers - 1
        
        while True:
            # Stack 검증
            stacked = Shape.stack(output_a, output_b)
            stack_ok = (repr(stacked) == original_repr)
            
            # output_a 분류 검증 (skip=True로 하이브리드 로직 스킵)
            from shape_classifier import analyze_shape
            a_type, a_reason = analyze_shape(repr(output_a), output_a, skip=True)
            classification_ok = (a_type not in ["analyzer.shape_types.impossible", "analyzer.shape_types.unknown"])
            
            if DEBUG_HYBRID:
                print(f"  Stack 검증: {stack_ok}, A 분류: {a_type} ({a_reason})")
            
            if stack_ok and classification_ok:
                if DEBUG_HYBRID:
                    print("  Stack(A,B) == 입력 && A 분류 OK: 완료")
                break
                
            if min_floor >= max_floor:
                if DEBUG_HYBRID:
                    print("  최저층이 최대층에 도달. 종료")
                break
                
            # 최저층을 1 올리고, 그 아래는 모두 0
            min_floor += 1
            for l in range(min_floor):
                for q in range(4):
                    mask[(l, q)] = 0
            if DEBUG_HYBRID:
                _debug_print_mask(shape, mask, f"단계 7: 최저층 {min_floor} 적용 후 마스크")
            # 새 마스크로 출력 재구성
            output_a, output_b = _build_outputs_from_mask(shape, mask)
    except Exception as e:
        if DEBUG_HYBRID:
            print(f"  단계 7 예외: {e}")

    # 8. 출력 후처리 (빈 레이어 제거, B 하단 c 채우기)
    if DEBUG_HYBRID:
        print("=== 단계 8: 출력 후처리 ===")
    
    # A/B 끝 꼬리 빈 레이어 제거
    while len(output_a.layers) > 0 and output_a.layers[-1].is_empty():
        output_a.layers.pop()
    while len(output_b.layers) > 0 and output_b.layers[-1].is_empty():
        output_b.layers.pop()
    
    # B에서 완전 빈 레이어 제거
    i = len(output_b.layers) - 1
    while i >= 0:
        current_layer = output_b.layers[i]
        is_empty_layer = True
        for q in range(4):
            if current_layer.quadrants[q] is not None:
                is_empty_layer = False
                break
        if is_empty_layer:
            output_b.layers.pop(i)
        i -= 1

    # B의 각 분면에 대해, 첫 유효 조각 아래는 c로 채우기
    if output_b:
        for q in range(4):
            has_piece_above = False
            first_non_empty_layer = -1
            for l in range(len(output_b.layers)):
                piece = output_b._get_piece(l, q)
                if piece and piece.shape != '-':
                    has_piece_above = True
                    first_non_empty_layer = l
                    break
            if has_piece_above and first_non_empty_layer > 0:
                for l in range(first_non_empty_layer):
                    if output_b._get_piece(l, q) is None:
                        while len(output_b.layers) <= l:
                            output_b.layers.append(Layer([None, None, None, None]))
                        output_b.layers[l].quadrants[q] = Quadrant('c', 'w')

    return output_a, output_b


def _find_unstable_at_layer(temp_shape: Shape, target_layer: int, mask: dict) -> Set[Tuple[int, int]]:
    """특정 층에서 불안정한 좌표를 찾습니다."""
    # 지지 계산 (마스크 1 부분에서만)
    supported = set()
    
    # 0층은 무조건 지지됨
    for q in range(4):
        if mask.get((0, q), 0) == 1 and temp_shape._get_piece(0, q):
            supported.add((0, q))
    
    # 마스크 0인 부분 아래의 도형들도 지지됨 (절대 지지성)
    for l in range(len(temp_shape.layers)):
        for q in range(4):
            if mask.get((l, q), 0) == 1 and temp_shape._get_piece(l, q):
                # 바로 아래가 마스크 0이면 지지됨
                if l > 0 and mask.get((l-1, q), 0) == 0:
                    supported.add((l, q))
    
    # 연결성 기반 지지 전파
    while True:
        num_supported_before = len(supported)
        visited_groups = set()
        
        for l_start in range(len(temp_shape.layers)):
            for q_start in range(4):
                coord = (l_start, q_start)
                if (coord not in visited_groups and 
                    mask.get(coord, 0) == 1 and 
                    temp_shape._get_piece(*coord)):
                    
                    group = temp_shape._find_connected_group(l_start, q_start)
                    # 마스크 1인 부분만 필터링
                    mask_filtered_group = {c for c in group if mask.get(c, 0) == 1}
                    
                    if any(c in supported for c in mask_filtered_group):
                        supported.update(mask_filtered_group)
                    visited_groups.update(mask_filtered_group)
        
        # 수직 지지 확인
        for l in range(len(temp_shape.layers)):
            for q in range(4):
                coord = (l, q)
                if (coord in supported or 
                    mask.get(coord, 0) != 1 or 
                    not temp_shape._get_piece(*coord)):
                    continue
                
                piece = temp_shape._get_piece(l, q)
                if l > 0 and (l - 1, q) in supported:
                    supported.add(coord)
                elif piece and piece.shape != 'P':
                    # 수평 연결 지지
                    for nq in range(4):
                        if _is_adjacent(q, nq):
                            neighbor_coord = (l, nq)
                            if neighbor_coord in supported:
                                supporter = temp_shape._get_piece(*neighbor_coord)
                                if supporter and supporter.shape != 'P':
                                    supported.add(coord)
                                    break
        
        if len(supported) == num_supported_before:
            break
    
    # 불안정한 좌표 찾기 (마스크 1인 부분 중 지지되지 않은 부분)
    all_mask1_coords = {(l, q) for l in range(len(temp_shape.layers)) 
                        for q in range(4) 
                        if mask.get((l, q), 0) == 1 and temp_shape._get_piece(l, q)}
    unstable_coords = all_mask1_coords - supported
    
    return unstable_coords


def _is_adjacent(q1: int, q2: int) -> bool:
    """두 사분면이 인접하는지 확인합니다."""
    if q1 == q2: 
        return False
    # 새로운 인덱스 매핑: 0=TR(0,1), 1=BR(1,1), 2=BL(1,0), 3=TL(0,0)
    positions = {0: (0, 1), 1: (1, 1), 2: (1, 0), 3: (0, 0)}
    r1, c1 = positions[q1]
    r2, c2 = positions[q2]
    return abs(r1 - r2) + abs(c1 - c2) == 1
