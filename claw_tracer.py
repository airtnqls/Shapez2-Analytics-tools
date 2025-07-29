# 임시 claw_tracer.py 파일
# 나중에 실제 claw 기능을 구현할 예정

def claw_process(shape_code: str) -> str:
    """Claw 처리 함수"""
    from shape import Shape, Layer, Quadrant # Import necessary classes locally
    
    # 1. str를 Shape 객체로 변환
    initial_shape = Shape.from_string(shape_code)
    current_shape = initial_shape.copy()

    # 2. 최 하단층에 P가 1개 이하면 오류
    if not current_shape.layers:
        return shape_code # Empty shape, no bottom layer
    
    bottom_layer = current_shape.layers[0]
    pin_count = sum(1 for q in bottom_layer.quadrants if q and q.shape == 'P')
    if pin_count < 1:
        return shape_code

    # 3. 최 하단층에 S가 있다면 그 사분면을 각각 저장합니다. (최대2개. 그 이상이라면 오류)
    s_quad_indices = []
    for i, quad in enumerate(bottom_layer.quadrants):
        if quad and quad.shape == 'S':
            s_quad_indices.append(i)
    
    if len(s_quad_indices) > 2:
        return shape_code

    # 4. 최 하단층을 완전히 제거한 뒤, 모든 도형의 층을 한칸씩 내립니다.
    # layers[0]이 바닥이므로, layers[0]을 제거하고 나머지 층들을 아래로 당겨오는 효과를 냅니다.
    # 즉, 원래의 1층이 새로운 0층이 되고, 2층이 새로운 1층이 되는 방식입니다.
    
    # 새로운 레이어 리스트를 만듭니다. (최하단층을 제외하고 복사)
    new_layers_after_claw = [layer.copy() for layer in current_shape.layers[1:]]
    
    # 이 new_layers 리스트를 사용하여 새로운 Shape 객체를 생성합니다.
    # 이렇게 하면 최하단층이 제거되고, 나머지 층들이 자동으로 한 칸씩 내려온 효과가 구현됩니다.
    shape_after_claw = Shape(new_layers_after_claw)

    # 빈 상위 층 제거 (깔끔한 repr을 위해)
    while len(shape_after_claw.layers) > 0 and shape_after_claw.layers[-1].is_empty():
        shape_after_claw.layers.pop()

    # 5. 그 도형에서 가장 높은 층에 있는 c를 찾습니다. 없다면 그 아래층을 찾습니다. 반복.
    #    그런데 그 처음으로 c를 찾은 층에 c가 두개 이상이라면 오류.
    # If layers[0] is bottom, highest C layer would be max index.
    highest_c_layer = -1 # Initialize to -1 to indicate not found
    found_c_quad_info = None # (layer_idx, quad_idx)
    
    # Iterate from top (highest index) to bottom (index 0) to find the highest 'c'
    for l_idx in range(len(shape_after_claw.layers) - 1, -1, -1): 
        c_in_this_layer = []
        for q_idx in range(4):
            quad = shape_after_claw._get_piece(l_idx, q_idx)
            if quad and quad.shape == 'c':
                c_in_this_layer.append((l_idx, q_idx))
        
        if c_in_this_layer:
            if len(c_in_this_layer) > 1:
                return shape_code # More than one 'c' in the highest layer where 'c' is found
            highest_c_layer = c_in_this_layer[0][0] # Store the layer index
            found_c_quad_info = c_in_this_layer[0]
            break
            
    if highest_c_layer == -1:
        return shape_code # No 'c' found in the entire shape

    c_layer, c_quad_idx = found_c_quad_info

    # 6. c를 찾았으면, 해당 사분면이 몇 사분면인지 저장하고(기준점), 그 반대 사분면도 저장합니다.(반대편 변수)
    #    (1사분면을 찾았다면 3사분면이 반대. 2면 4. / 3이면 1. /4면 2.)
    # Quadrant index mapping: 0=TR, 1=BR, 2=BL, 3=TL
    # 0 -> 2, 1 -> 3, 2 -> 0, 3 -> 1. This corresponds to (idx + 2) % 4
    opposite_quad_idx = (c_quad_idx + 2) % 4

    # 7. '반대편' 사분면의 최 상단층에 c를 추가하고, 그 아래층을 c로 채우고를 반복합니다. -가 아닌 다른 도형에 의해 막힐때 까지.
    # '최 상단층'은 가장 높은 인덱스를 의미합니다. '아래층'은 인덱스가 감소하는 방향입니다.
    # Iterate from Shape.MAX_LAYERS - 1 down to 0
    for l_fill_idx in range(Shape.MAX_LAYERS - 1, -1, -1):
        # Ensure layer exists up to this index
        while len(shape_after_claw.layers) <= l_fill_idx:
            # Add new empty layers at the top (highest index) if extending upwards
            shape_after_claw.layers.append(Layer([None]*4))

        current_quad_at_pos = shape_after_claw._get_piece(l_fill_idx, opposite_quad_idx)

        # Stop if blocked by a non-empty, non-crystal piece
        if current_quad_at_pos is not None and current_quad_at_pos.shape != 'c':
            break
        
        # Fill with crystal 'c' with 'y' color (standard crystal color)
        shape_after_claw.layers[l_fill_idx].quadrants[opposite_quad_idx] = Quadrant('c', 'y')

    # Apply physics one last time -> 물리 적용하지 않고 직접 한 칸씩 내린 상태로 반환
    return repr(shape_after_claw)


def verify_claw_process(original_input_code: str, processed_shape_str: str) -> bool:
    """Claw 처리 후 결과를 검증하는 함수"""
    from shape import Shape, Layer, Quadrant # Import necessary classes locally
    # 1. claw_process 결과 Shape 객체로 변환
    processed_shape = Shape.from_string(processed_shape_str)
    
    # 2. 원본 입력 Shape 객체로 변환
    original_shape = Shape.from_string(original_input_code)

    # 3. processed_shape에 push_pin을 적용
    push_pinned_result = processed_shape.push_pin()

    # 4. push_pinned_result와 original_shape가 동일한지 비교
    return repr(push_pinned_result) == repr(original_shape)