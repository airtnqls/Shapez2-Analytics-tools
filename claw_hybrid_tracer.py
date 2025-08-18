"""
하이브리드 도형 분석 모듈

이 모듈은 Shape 클래스의 하이브리드 분석 로직을 담당합니다.
하이브리드 분석은 도형을 마스크 기반으로 두 부분으로 분리하는 기능을 제공합니다.
"""

from typing import Set, Tuple
from shape import Shape, Layer


def claw_hybrid(shape: Shape) -> Tuple[Shape, Shape]:
    """
    하이브리드 함수: 입력을 마스크 기반으로 두 부분으로 분리합니다.
    
    Args:
        shape: 분석할 도형
        claw: 클로 모드 여부 (True일 때 P와 S를 마스크 0으로 설정)
        
    Returns:
        (output_a, output_b): 마스크 0 부분과 마스크 1 부분으로 분리된 두 도형
    """
    mask = {}
    
    # 1. 각 셀에 대응되는 (사분면x층) 크기의 임시 마스크를 만듭니다 (1로 초기화)
    for l in range(len(shape.layers)):
        for q in range(4):
            mask[(l, q)] = 1
            
    # 2. 0층의 P는 마스크 0으로 설정
    for q in range(4):
        piece = shape._get_piece(0, q)
        if piece and (piece.shape == 'P' or piece.shape == 'S'):
            mask[(0, q)] = 0
        
# 3. 클로시 크리스탈 주변 마스크 0으로 설정
    # 모든 크리스탈을 찾습니다
    for l in range(len(shape.layers)):
        for q in range(4):
            piece = shape._get_piece(l, q)
            if piece and piece.shape == 'c':
                # 크리스탈의 상, 좌, 우 (양쪽 사분면, 위 레이어)를 마스크 0으로 만들고 그 아래 모든 영역도 0으로 만듭니다
                
                # 상 (위 레이어의 같은 사분면)
                upper_piece = shape._get_piece(l, q)
                if upper_piece:  # 빈칸이 아닌 경우에만
                    for upper_l in range(l, len(shape.layers)):
                        mask[(upper_l, q)] = 0
                
                # 좌 사분면 (현재 층과 그 아래)
                left_q = (q - 1) % 4
                left_piece = shape._get_piece(l, left_q)
                if left_piece:  # 빈칸이 아닌 경우에만
                    for lower_l in range(l + 1):
                        mask[(lower_l, left_q)] = 0
                
                # 우 사분면 (현재 층과 그 아래)
                right_q = (q + 1) % 4
                right_piece = shape._get_piece(l, right_q)
                if right_piece:  # 빈칸이 아닌 경우에만
                    for lower_l in range(l + 1):
                        mask[(lower_l, right_q)] = 0
    
    # 4. 각 사분면의 가장 높은 크리스탈을 찾습니다
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
    
    # 5. 마스크 영역 0인 부분만으로 임시 도형을 만들어 불안정한 도형 검사
    current_layer = 0
    while current_layer < len(shape.layers):
        # 현재까지의 마스크 0 부분만으로 임시 도형 생성
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
        
        # 현재 층에서 불안정한 도형 탐색 (마스크 0 영역에서만)
        # 마스크를 리버스하여 전달 (1과 0을 바꿈)
        reversed_mask = {}
        for key, value in mask.items():
            reversed_mask[key] = 1 - value
        unstable_coords = _find_unstable_at_layer(temp_shape, current_layer, reversed_mask)
        
        # 불안정한 도형이 존재할 때, 원본 도형에서 양쪽 사분면 중 마스크 1이면서 S인 부분 찾기
        mask_changed = False
        if unstable_coords:
            for unstable_l, unstable_q in unstable_coords:
                # 양쪽 사분면 검사 (불안정한 도형이 있는 사분면과 인접한 사분면들)
                adjacent_quads = []
                if unstable_q == 0:
                    adjacent_quads = [1, 3]
                elif unstable_q == 1:
                    adjacent_quads = [0, 2]
                elif unstable_q == 2:
                    adjacent_quads = [1, 3]
                elif unstable_q == 3:
                    adjacent_quads = [0, 2]
                
                for check_q in adjacent_quads:
                    if (mask.get((unstable_l, check_q), 0) == 1 and 
                        shape._get_piece(unstable_l, check_q) and 
                        shape._get_piece(unstable_l, check_q).shape == 'S'):
                        # 해당 부분과 그 아래를 마스크 0으로 변경
                        for below_l in range(unstable_l + 1):
                            mask[(below_l, check_q)] = 0
                        mask_changed = True
            
            # 마스크가 변경되었으면 현재 층부터 다시 검사
            if mask_changed:
                continue
        
        # 불안정한 도형이 없거나 마스크 변경이 없으면 다음 층으로
        current_layer += 1
    
    # 6. 특별 조건 검사: S 도형이 아래가 비어있고 옆 사분면이 마스크 0이면서 S 또는 c인 경우
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
    
    # 7. 수정된 물리 적용으로 불안정한 도형 검사 (층별 순차 처리)
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
    
    # 8. 출력 A (마스크 0 부분만), 출력 B (마스크 1 부분만)
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
    
    # max_layers 설정
    output_a.max_layers = shape.max_layers
    output_b.max_layers = shape.max_layers
    
    # 빈 레이어 제거
    while len(output_a.layers) > 0 and output_a.layers[-1].is_empty():
        output_a.layers.pop()
    while len(output_b.layers) > 0 and output_b.layers[-1].is_empty():
        output_b.layers.pop()
    
    # B 출력에서 각 레이어별로 ----로 아예 빈 층 제거
    # 모든 빈 레이어를 제거 (위에서부터 순서대로)
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
