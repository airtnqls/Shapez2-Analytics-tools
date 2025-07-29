# 임시 claw_tracer.py 파일
# 나중에 실제 claw 기능을 구현할 예정

def claw_process(shape_code: str) -> str:
    print(f"DEBUG: claw_process 함수 호출됨. 입력 도형 코드: {shape_code}")
    from shape import Shape, Layer, Quadrant 
    
    # 추가: shape_code가 너무 길거나 유효하지 않은 문자를 포함하는 경우 필터링
    # 유효한 모양 코드에 포함될 수 있는 문자: C, S, R, W, c, P, -, :, r, g, b, m, c, y, u, w
    # 대략적인 길이 제한 (예: 5층 최대 8*5 = 40자 + 콜론)
    # 실제로는 더 복잡한 검사가 필요하지만, 임시로 간단한 필터링
    valid_chars = set('CSRWcPrgbmyuw-:')
    if not all(char in valid_chars for char in shape_code) or len(shape_code) > 100: # 넉넉하게 100자로 제한
        print(f"DEBUG_ERROR: 잘못된 도형 코드 형식 또는 너무 김. 원본 도형 코드 반환: {shape_code}")
        return shape_code

    try: # 전체 함수를 try-except로 감싸서 예외 포착
        initial_shape = Shape.from_string(shape_code)
        current_shape = initial_shape.copy()
        print(f"DEBUG: 초기 Shape 객체 생성됨: {repr(initial_shape)}")
        
        # 2. 최 하단층에 P가 1개 이하면 오류
        if not current_shape.layers:
            print(f"DEBUG_ERROR: 빈 도형. 최하단층 없음. 원본 도형 코드 반환: {shape_code}")
            return shape_code
        
        bottom_layer = current_shape.layers[0]
        pin_count = sum(1 for q in bottom_layer.quadrants if q and q.shape == 'P')
        print(f"DEBUG: 최하단층 핀 개수: {pin_count}")
        if pin_count < 1:
            print(f"DEBUG_ERROR: 최하단층에 'P' 조각이 1개 미만. 핀 개수: {pin_count}. 원본 도형 코드 반환: {shape_code}")
            return shape_code

        # 3. 최 하단층에 S가 있다면 그 사분면을 각각 저장합니다. (최대2개. 그 이상이라면 오류)
        s_quad_indices = []
        p_quad_indices_from_original_bottom_layer = [] # 원본 최하단층에서 'P' 조각이 있던 위치 저장
        print(f"DEBUG: 최하단층 사분면 내용 확인: {bottom_layer.quadrants}") # 추가된 디버그
        for i, quad in enumerate(bottom_layer.quadrants):
            # 'S'가 모든 일반 도형(C, R, S, W)을 뜻한다는 사용자님의 지시에 따라 수정
            if quad and quad.shape in ['C', 'R', 'S', 'W']:
                s_quad_indices.append(i)
            if quad and quad.shape == 'P': # 'P' 조각 위치도 저장
                p_quad_indices_from_original_bottom_layer.append(i)
            
        print(f"DEBUG: 최하단층 'S' 조각 인덱스: {s_quad_indices}")
        print(f"DEBUG: 원본 최하단층 'P' 조각 인덱스: {p_quad_indices_from_original_bottom_layer}") # 디버그 추가
        
        if len(s_quad_indices) > 2:
            print(f"DEBUG_ERROR: 최하단층에 'S' 조각이 2개 초과. 'S' 인덱스: {s_quad_indices}. 원본 도형 코드 반환: {shape_code}")
            return shape_code

        # 5. 가장 높은 층의 'c' 조각 개수 검사 및 기준점/반대편 사분면 결정
        highest_c_layer = -1
        found_c_quad_info = None

        for l_idx in range(len(initial_shape.layers) - 1, -1, -1):
            c_in_this_layer = []
            for q_idx in range(4):
                quad = initial_shape._get_piece(l_idx, q_idx)
                if quad and quad.shape == 'c':
                    c_in_this_layer.append((l_idx, q_idx))

            if c_in_this_layer:
                if len(c_in_this_layer) > 1:
                    print(f"DEBUG_ERROR: 'c'를 찾은 가장 높은 층에 'c' 조각이 2개 초과. 층: {l_idx}, 해당 층의 'c' 조각: {c_in_this_layer}. 원본 도형 코드 반환: {shape_code}")
                    return shape_code
                highest_c_layer = c_in_this_layer[0][0]
                found_c_quad_info = c_in_this_layer[0]
                break

        if highest_c_layer == -1:
            print(f"DEBUG_ERROR: 도형 전체에서 'c'를 찾을 수 없음. 원본 도형 코드 반환: {shape_code}")
            return shape_code

        c_layer, c_quad_idx = found_c_quad_info
        # 6. 기준점 사분면의 반대편 사분면 결정
        opposite_quad_idx = (c_quad_idx + 2) % 4

        # 4. 최 하단층을 완전히 제거한 뒤, 모든 도형의 층을 한칸씩 내립니다。
        print(f"DEBUG: 층 이동 시작. 원본 층 개수: {len(current_shape.layers)}")
        new_layers_after_claw = [layer.copy() for layer in current_shape.layers[1:]]
        shape_after_claw = Shape(new_layers_after_claw)
        print(f"DEBUG: 초기 층 이동 후. 현재 shape_after_claw: {repr(shape_after_claw)}")

        # 빈 상위 층 제거 (깔끔한 repr을 위해)
        while len(shape_after_claw.layers) > 0 and shape_after_claw.layers[-1].is_empty():
            shape_after_claw.layers.pop()
        print(f"DEBUG: 빈 상위 층 제거 후. 현재 shape_after_claw: {repr(shape_after_claw)}")

        # --- 추가된 로직 시작 ---
        # 4-0. 원본 최하단층의 'P' 위치에 따라 새 0층에 'c' 채우기
        if len(p_quad_indices_from_original_bottom_layer) > 0 and len(shape_after_claw.layers) > 0: # P가 있었고, 도형이 비어있지 않다면
            print(f"DEBUG: 원본 최하단층 'P' 위치 ({p_quad_indices_from_original_bottom_layer})에 'c' 채우기 시도.")
            for p_q_idx in p_quad_indices_from_original_bottom_layer:
                # 새로운 0층 (이전의 1층)에서 해당 사분면이 비어있는지 확인
                if shape_after_claw._get_piece(0, p_q_idx) is None:
                    shape_after_claw.layers[0].quadrants[p_q_idx] = Quadrant('c', 'y')
                    print(f"DEBUG: 새로운 0층, 사분면 {p_q_idx}에 'c' 채움. 현재 도형: {repr(shape_after_claw)}")
        # --- 추가된 로직 끝 ---

        # 4-1. 삭제된 1층 S 위치에 따라 S 배치 및 주변 C 채우기
        print(f"DEBUG: 'S' 배치 및 'C' 채우기 시작. 'S' 조각 인덱스: {s_quad_indices}")
        from shape import Quadrant, Layer # Ensure Quadrant and Layer are imported for local use

        for s_q_idx in s_quad_indices: # 각 S가 있던 사분면에 대해
            print(f"DEBUG: 사분면 {s_q_idx} 처리 중 (새로운 S 재배치 로직)")

            target_s_layer = -1 # S를 배치할 최종 층 인덱스
            quads_to_fill_with_c = [] # Adjacent '-'를 'c'로 채울 좌표 (l, q) 리스트

            # 1. 해당 사분면(s_q_idx)의 2층(인덱스 1)부터 시작하여 점점 올라감 (Shape.MAX_LAYERS까지)
            for l_idx in range(1, Shape.MAX_LAYERS): # 2층 (인덱스 1)부터 시작
                # 현재 층이 존재하는지 확인하고, 없으면 생성 (S를 배치할 층까지)
                while len(shape_after_claw.layers) <= l_idx:
                    shape_after_claw.layers.append(Layer([None]*4))
                    print(f"DEBUG: 층 확장 중. 목표 층: {l_idx}. 현재 층: {len(shape_after_claw.layers)}")

                # 해당 층(l_idx)에서 s_q_idx에 인접한 두 사분면 찾기
                adjacent_quad_indices = []
                for q_check_idx in range(4):
                    if shape_after_claw._is_adjacent(s_q_idx, q_check_idx):
                        adjacent_quad_indices.append(q_check_idx)

                # 인접한 사분면이 2개가 아닌 경우 (예외 상황) 스킵
                if len(adjacent_quad_indices) != 2:
                    print(f"DEBUG_ERROR: 사분면 {s_q_idx}에 대해 인접한 사분면을 2개 찾지 못함 (예상치 못한 상황). 스킵.")
                    continue 

                adj_q1_idx, adj_q2_idx = adjacent_quad_indices[0], adjacent_quad_indices[1]
                adj_q1_piece = shape_after_claw._get_piece(l_idx, adj_q1_idx)
                adj_q2_piece = shape_after_claw._get_piece(l_idx, adj_q2_idx)

                print(f"DEBUG: 층 {l_idx}, 사분면 {s_q_idx}. 인접 사분면 조각 확인: {repr(adj_q1_piece)} (q{adj_q1_idx}), {repr(adj_q2_piece)} (q{adj_q2_idx})")

                # 조건 1: 인접한 사분면 두 개가 전부 P 또는 - 일 경우
                is_adj1_p_or_empty = (adj_q1_piece is None) or (adj_q1_piece.shape == 'P')
                is_adj2_p_or_empty = (adj_q2_piece is None) or (adj_q2_piece.shape == 'P')
                
                # 조건 2: -가 하나 이상있어야함.
                is_at_least_one_empty = (adj_q1_piece is None) or (adj_q2_piece is None)

                if is_adj1_p_or_empty and is_adj2_p_or_empty and is_at_least_one_empty:
                    # 멈춤 조건 충족! 이 층이 target_s_layer가 됩니다.
                    target_s_layer = l_idx
                    print(f"DEBUG: 층 {l_idx}에서 멈춤 조건 충족. target_s_layer 설정: {target_s_layer}")
                    
                    # 멈춘 경우. 그 인접한 - 를 c로 바꿈. (실제로 비어있던 곳만)
                    if adj_q1_piece is None:
                        quads_to_fill_with_c.append((l_idx, adj_q1_idx))
                    if adj_q2_piece is None:
                        quads_to_fill_with_c.append((l_idx, adj_q2_idx))
                    
                    break # 현재 s_q_idx에 대한 층 탐색 중단

            # S를 배치할 target_s_layer가 결정되었으면 (멈춤 조건이 충족되었다면)
            if target_s_layer != -1:
                # S를 target_s_layer, s_q_idx에 배치
                # target_s_layer까지 레이어가 이미 확장되었거나, 존재한다고 가정
                shape_after_claw.layers[target_s_layer].quadrants[s_q_idx] = Quadrant('C', 'u')
                print(f"DEBUG: 층 {target_s_layer}, 사분면 {s_q_idx}에 'S' 배치. 현재 도형: {repr(shape_after_claw)}")

                # 멈춤 조건에서 찾은 인접한 '-'를 'c'로 바꿈.
                for l_c, q_c in quads_to_fill_with_c:
                    # 해당 위치에 크리스탈 배치 전, 해당 칸이 비어있는지 다시 확인 (안전장치)
                    if shape_after_claw._get_piece(l_c, q_c) is None:
                        shape_after_claw.layers[l_c].quadrants[q_c] = Quadrant('c', 'y')
                        print(f"DEBUG: 층 {l_c}, 사분면 {q_c}에 'C' (크리스탈) 배치. 현재 도형: {repr(shape_after_claw)}")

                        # 추가된 C의 윗 공간이 '-'인 경우 또 C 추가 (위로 전파)
                        current_fill_l = l_c + 1 # 바로 윗 층부터 확인
                        while True:
                            # MAX_LAYERS를 초과하면 멈춤
                            if current_fill_l >= Shape.MAX_LAYERS:
                                print(f"DEBUG: MAX_LAYERS 도달. 'C' 상단 채우기 중단.")
                                break

                            # 층이 존재하지 않으면 확장
                            while len(shape_after_claw.layers) <= current_fill_l:
                                shape_after_claw.layers.append(Layer([None]*4))
                                print(f"DEBUG: 'C' 상단 채우기 중 층 확장. 목표 층: {current_fill_l}. 현재 층: {len(shape_after_claw.layers)}")
                            
                            piece_above = shape_after_claw._get_piece(current_fill_l, q_c)
                            print(f"DEBUG: 층 {current_fill_l}, 사분면 {q_c}에서 'C' 상단 채우기 확인 중. 조각: {piece_above}")

                            # 윗 공간이 비어있다면 (None) 'c'로 채우고 계속 위로
                            if piece_above is None:
                                shape_after_claw.layers[current_fill_l].quadrants[q_c] = Quadrant('c', 'y')
                                print(f"DEBUG: 층 {current_fill_l}, 사분면 {q_c}에 'C' (크리스탈) 상단 채움. 현재 도형: {repr(shape_after_claw)}")
                                current_fill_l += 1 # 다음 층으로 이동
                            elif piece_above.shape == 'c': # 이미 C라면 계속 위로 (기존 C 연결)
                                current_fill_l += 1
                            else: # 비어있지 않고 C도 아니라면 멈춤
                                print(f"DEBUG: 층 {current_fill_l}, 사분면 {q_c}에서 'C' 상단 채우기 막힘. 조각: {repr(piece_above)}")
                                break
            else:
                print(f"DEBUG: 사분면 {s_q_idx}에 대한 멈춤 조건을 찾지 못했습니다. S 배치 및 C 채우기 건너뜜.")
                continue # 다음 s_q_idx로 넘어감

        # 7. '반대편' 사분면의 최 상단층에 c를 추가하고, 그 아래층을 c로 채우고를 반복합니다. -가 아닌 다른 도형에 의해 막힐때 까지.
        # '최 상단층'은 가장 높은 인덱스를 의미합니다. '아래층'은 인덱스가 감소하는 방향입니다.
        # Shape.MAX_LAYERS - 1부터 0까지 역순으로 순회
        print(f"DEBUG: 반대 사분면 {opposite_quad_idx}에서 'C' 채우기 시작 (최상단부터)")
        for l_fill_idx in range(Shape.MAX_LAYERS - 1, -1, -1):
            # 이 인덱스까지 레이어가 존재하는지 확인하고, 없으면 추가합니다.
            while len(shape_after_claw.layers) <= l_fill_idx:
                # 새로운 빈 레이어를 상단(최대 인덱스)에 추가하여 위쪽으로 확장
                shape_after_claw.layers.append(Layer([None]*4))
            
            current_quad_at_pos = shape_after_claw._get_piece(l_fill_idx, opposite_quad_idx)
            print(f"DEBUG: 층 {l_fill_idx}, 사분면 {opposite_quad_idx}에 'C' 채우기 확인 중. 조각: {current_quad_at_pos}")

            # 비어있지 않고 크리스탈 조각도 아니라면 중단
            if current_quad_at_pos is not None and current_quad_at_pos.shape != 'c':
                print(f"DEBUG: 층 {l_fill_idx}, 사분면 {opposite_quad_idx}에서 조각 {repr(current_quad_at_pos)}에 의해 'C' 채우기 막힘")
                break
            
            # 크리스탈 'c'를 'y' 색상으로 채웁니다.
            shape_after_claw.layers[l_fill_idx].quadrants[opposite_quad_idx] = Quadrant('c', 'y')
            print(f"DEBUG: 층 {l_fill_idx}, 사분면 {opposite_quad_idx}에 'C' 채움. 현재 도형: {repr(shape_after_claw)}")

        print(f"DEBUG: 'C' 채우기 완료. 최종 반환 전 도형: {repr(shape_after_claw)}")
        return repr(shape_after_claw)

    except Exception as e:
        import traceback
        print(f"DEBUG_EXCEPTION: claw_process에서 예상치 못한 오류 발생: {e}")
        traceback.print_exc() # 전체 스택 트레이스 출력
        return shape_code # 오류 발생 시 원본 shape_code 반환


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