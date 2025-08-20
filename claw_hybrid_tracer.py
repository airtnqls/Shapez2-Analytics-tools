"""
하이브리드 도형 분석 모듈

이 모듈은 Shape 클래스의 하이브리드 분석 로직을 담당합니다.
하이브리드 분석은 도형을 마스크 기반으로 두 부분으로 분리하는 기능을 제공합니다.
"""

from typing import Set, Tuple
from shape import Shape, Layer, Quadrant
from data_operations import simplify_shape
import re

# 하이브리드 패턴 매칭을 위한 정규식 패턴과 마스크 데이터
HYBRID_PATTERNS = {
    "P-PP:P-[^-][Sc]:PSc[^c]:[^-]-S[^c]:cS[^c][^c]": "0000:0000:0001:0001:0011",
    "P-PP:PSS[^c]:P-[^c][^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0001:0011:0011:0111",
    "--PP:PP[PS]c:SS[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]": "0000:0000:0010:0111:0111",
    "P-P[^c]:P-[^-][^c]:PSc[^c]:[^-]-S[^c]:cS[^c][^c]": "0001:0001:0001:0001:0011",
    "--PP:--[PS]c:SS[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]": "0000:0000:0010:0111:1111",
    "-PPP:SP[^c]S:-P[^c][^c]:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0010:0011:0011:0111",
    "-PPP:SP[^c]S:[S-][PS][^c][^c]:[c-]P[^c][^c]:cS[^c][^c]": "0000:0010:0011:0011:0011",
    "-PPP:SP[^c]S:-P[^c][^c]:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0010:0011:0011:1111",
    "P-PP:PSS[^c]:P.[^c][^c]:[PS]-[^c][^c]:cS[^c][^c]": "0000:0001:0011:0011:0011",
    ".-PP:.-c[SP]:-SS[^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0000:0001:0011:0111",
    "[P-]-[P-]P:.-.[PS]:SSS[^c]:S[^c][^c][^c]:c[^c][^c][^c]": "0000:0000:0001:0111:0111",
    "[P-][P-]PP:[P-].[^-][^-]:[PS].c[Sc]:[^-]-S[^c]:cS[^c][^c]": "0000:0000:0000:0001:0011",
    "P[P-]P[P-]:[^-]-[^c]-:cS[^c]S:[^c][^c][^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:1111:1111",
    "[P-][P-]PP:..[^-][^-]:[S-][S-][PS][Sc]:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0000:0000:0011:0111",
    "-.PP:-.[^-][^-]:[Sc]-[PS][^-]:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0000:0000:0011:1111",
    "P.P.:..[^c].:[Sc]S[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]": "0000:0010:0010:0111:0111",
    "...P:...[^c]:-[Sc]S[^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0001:0001:0011:0111",
    "..P.:..[PS].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0000:0010:0011:0111",
    "P..[^c]:[^-]..[^c]:[^-][Sc]S[^c]:[^-]-[^c][^c]:cS[^c][^c]": "0001:0001:0001:0011:0011",
    ".[P-][P-]P:...[^-]:.SS[^c]:.[P-][^c][^c]:cS[^c][^c]": "0000:0000:0001:0011:0011",
    "..P.:..[PS].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0000:0010:0011:1111",
    "..P.:..[^c].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0010:0010:0011:0111",
    "...P:...[^c]:S[Sc]S[^c]:S[^c][^c][^c]:c[^c][^c][^c]": "0000:0001:0001:0111:0111",
    "..P.:..[^c].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:0011:1111",
    "..P.:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:0111:1111",
    "P.P.:[^-].[^-].:..[^-].:cS[^c]S:[^c][^c][^c][^c]": "0000:0000:0000:0010:1111",
    "[PS].P.:..[PS].:..[^c].:cS[^c]S:[^c][^c][^c][^c]": "0000:0000:0010:0010:1111",
    "..P.:..[PS].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0000:0010:0010:0111",
    "..P.:..[^-].:..[PS].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0000:0000:0010:0111",
    "...P:...[^c]:.[Sc]S[^c]:..[^c][^c]:cS[^c][^c]": "0000:0001:0001:0011:0011",
    "..P.:..[^c].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0010:0010:0010:0111",
    "..P.:..[^c].:[Sc].[^c]S:..[^c][^c]:cS[^c][^c]": "0000:0010:0010:0011:0011",
    "..[PS].:..[^c].:..[^c].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0010:0010:0010:0011",
    "..P.:..[PS].:..[^c].:[Sc].[^c]S:cS[^c][^c]": "0000:0000:0010:0010:0011",
    "..P.:..[^c].:..[^c].:cS[^c]S:[^c][^c][^c][^c]": "0000:0010:0010:0010:1111",
    "..P.:..[PS].:..[^c][Sc]:..[^c][^c]:cS[^c][^c]": "0000:0000:0010:0011:0011",
    "....:....:..[PS].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0000:0000:0010:0011",
    "..P.:..[PS].:..[^c].:..[^c].:cS[^c]S": "0000:0000:0010:0010:0010",
    "....:....:..[^-].:[^-]-[PS][^-]:cS[^c][^c]": "0000:0000:0000:0000:0011",
    "....:....:..[PS][Sc]:.[P-][^c][^c]:cS[^c][^c]": "0000:0000:0000:0011:0011",
    "..[PS].:..[^c].:..[^c].:..[^c].:cS[^c]S": "0000:0010:0010:0010:0010",
    "....:....:..[PS].:..[^c].:cS[^c]S": "0000:0000:0000:0010:0010",
    "....:....:....:..[PS].:cS[^c]S": "0000:0000:0000:0000:0010"
}

DEBUG_HYBRID = False

def swap_2nd_and_4th(segment: str) -> str:
    """
    정규식 패턴 또는 일반 문자열에서 2번째와 4번째 '토큰'을 교체합니다.
    정규식의 문자 클래스 '[...]'는 하나의 토큰으로 취급합니다.
    """
    # 정규식을 사용해 패턴을 토큰 단위로 분리 (가장 중요한 변경점)
    # '[...]' 형태의 문자 클래스를 한 덩어리로 찾거나, 아니면 단일 문자를 찾음
    tokens = re.findall(r'\[.*?\]|.', segment)
    
    # 토큰이 정확히 4개일 때만 2번째(인덱스 1)와 4번째(인덱스 3) 교체
    if len(tokens) == 4:
        tokens[1], tokens[3] = tokens[3], tokens[1]
    else:
        # 디버깅을 위해 경고 메시지는 유지할 수 있습니다.
        # 이젠 이 메시지가 거의 나타나지 않을 것입니다.
        print(f"Warning: Segment '{segment}' does not consist of 4 tokens. Tokens found: {tokens}")

    return "".join(tokens)

# 원본과 복제본을 모두 담을 새로운 딕셔너리
extended_patterns = {}

# 원본 딕셔너리를 순회하며 작업 수행
for key, value in HYBRID_PATTERNS.items():
    # 1. 원본 키-값 쌍을 새로운 딕셔너리에 추가
    extended_patterns[key] = value

    # 2. 키와 값을 ':' 기준으로 분리
    key_segments = key.split(':')
    value_segments = value.split(':')

    # 3. 각 조각(segment)에 대해 변환 함수 적용
    # 리스트 컴프리헨션을 사용하여 코드를 간결하게 만듦
    swapped_key_segments = [swap_2nd_and_4th(seg) for seg in key_segments]
    swapped_value_segments = [swap_2nd_and_4th(seg) for seg in value_segments]

    # 4. 변환된 조각들을 다시 ':'로 합쳐서 새로운 키와 값을 생성
    new_key = ":".join(swapped_key_segments)
    new_value = ":".join(swapped_value_segments)
    
    # 5. 생성된 새로운 키-값 쌍을 원본 바로 다음에 추가
    if new_key in extended_patterns:
        continue
    extended_patterns[new_key] = new_value

# --- 결과 확인 ---

# print(f"원본 딕셔너리 항목 수: {len(HYBRID_PATTERNS)}")
# print(f"확장된 딕셔너리 항목 수: {len(extended_patterns)}")

# HYBRID_PATTERNS를 확장된 딕셔너리로 교체
HYBRID_PATTERNS = extended_patterns

def claw_hybrid(shape: Shape) -> Tuple[Shape, Shape]:
    """
    하이브리드 함수: 입력을 마스크 기반으로 두 부분으로 분리합니다. 패턴매칭 방식으로.
    
    Args:
        shape: 분석할 도형
        
    Returns:
        (output_a, output_b): 마스크 0 부분과 마스크 1 부분으로 분리된 두 도형
    """
    # 원본 도형을 보존하기 위해 깊은 복사 생성
    working_shape = shape.copy()
    
    mask = {}
    shape_str = repr(working_shape)
    simplified_str = simplify_shape(shape_str)
    
    # 전체 도형에서 가장 높은 크리스탈의 위치를 찾습니다
    highest_crystal_layer = -1
    highest_crystal_quadrant = -1
    
    # 모든 크리스탈을 찾으면서 동시에 가장 높은 크리스탈도 찾습니다
    for l in range(len(working_shape.layers) - 1, -1, -1):  # 위에서부터 탐색
        for q in range(4):
            piece = working_shape._get_piece(l, q)
            if piece and piece.shape == 'c':
                # 가장 높은 크리스탈 정보 저장 (첫 번째로 찾은 것이 가장 높음)
                if highest_crystal_layer == -1:
                    highest_crystal_layer = l
                    highest_crystal_quadrant = q
    
    # highest_crystal_quadrant 값에 따라 도형 회전
    if highest_crystal_quadrant == 1:
        working_shape = working_shape.rotate(clockwise=False)  # 270도 회전 (반시계방향 3번)
    elif highest_crystal_quadrant == 2:
        working_shape = working_shape.rotate_180()  # 180도 회전
    elif highest_crystal_quadrant == 3:
        working_shape = working_shape.rotate(clockwise=True)  # 90도 회전 (시계방향 1번)
    else:
        pass
    
    # 회전 후 도형을 원본으로 저장
    original_shape = working_shape.copy()
    
    # 회전된 도형으로 다시 문자열 생성
    shape_str = repr(working_shape)
    simplified_str = simplify_shape(shape_str)
    
    # 2. HYBRID_PATTERNS의 각 키에 대해 순차적으로 정규식 패턴 검사 및 검증
    best_output_a = None
    best_output_b = None
    
    for pattern_key in HYBRID_PATTERNS:
        # 도형의 층 수에 따라 패턴 키 조정
        adjusted_pattern_key = pattern_key
        shape_layers_count = len(working_shape.layers)
        
        # 4층 이하인 경우 뒤쪽 패턴 레이어 삭제
        if shape_layers_count <= 4:
            layers_to_remove = 5 - shape_layers_count  # 삭제할 레이어 수
            pattern_segments = pattern_key.split(':')
            adjusted_pattern_key = ':'.join(pattern_segments[:-layers_to_remove]) if layers_to_remove > 0 else pattern_key
       
        if re.fullmatch(adjusted_pattern_key, simplified_str):
            if DEBUG_HYBRID:
                print("=== 매칭 OK: 마스크 적용 및 출력 생성 시작 ===")
                print(f"선택된 패턴: {pattern_key}")
                print(f"적용 패턴: {adjusted_pattern_key}")
                print(f"도형(단순화): {simplified_str}")
            
            mask_str = HYBRID_PATTERNS[pattern_key]
            if DEBUG_HYBRID:
                print(f"마스크 문자열: {mask_str}")
            
            # 도형의 층 수에 따라 마스크 조정
            mask_layers = mask_str.split(':')
            if DEBUG_HYBRID:
                print(f"마스크 레이어 수 {len(mask_layers)} / 실제 레이어 수 {len(working_shape.layers)}")
                for l, layer_mask in enumerate(mask_layers):
                    if l < len(working_shape.layers):
                        print(f"- L{l} 마스크: {layer_mask}")
            
            # 마스크 문자열을 딕셔너리로 변환
            current_mask = {}
            for l, layer_mask in enumerate(mask_layers):
                if l < len(working_shape.layers):
                    for q, bit in enumerate(layer_mask):
                        if q < 4:
                            current_mask[(l, q)] = int(bit)
            
            # 현재 마스크로 출력 도형 생성
            output_a_layers = []
            output_b_layers = []
            
            for l in range(len(working_shape.layers)):
                layer_a_quadrants = [None] * 4
                layer_b_quadrants = [None] * 4
                
                for q in range(4):
                    piece = working_shape._get_piece(l, q)
                    if piece:
                        if current_mask.get((l, q), 0) == 0:
                            layer_a_quadrants[q] = piece.copy()
                            if DEBUG_HYBRID:
                                try:
                                    print(f"할당: L{l} Q{q} -> A | {repr(piece)}")
                                except Exception:
                                    print(f"할당: L{l} Q{q} -> A")
                        else:
                            layer_b_quadrants[q] = piece.copy()
                            if DEBUG_HYBRID:
                                try:
                                    print(f"할당: L{l} Q{q} -> B | {repr(piece)}")
                                except Exception:
                                    print(f"할당: L{l} Q{q} -> B")
                
                output_a_layers.append(Layer(layer_a_quadrants))
                output_b_layers.append(Layer(layer_b_quadrants))
            
            current_output_a = Shape(output_a_layers)
            current_output_b = Shape(output_b_layers)
            if DEBUG_HYBRID:
                try:
                    print(f"출력 A (트리밍 전): {repr(current_output_a)}")
                    print(f"출력 B (트리밍 전): {repr(current_output_b)}")
                except Exception:
                    pass
            
            # max_layers 설정
            current_output_a.max_layers = working_shape.max_layers
            current_output_b.max_layers = working_shape.max_layers
            
            # 빈 레이어 제거
            trim_a = 0
            while len(current_output_a.layers) > 0 and current_output_a.layers[-1].is_empty():
                current_output_a.layers.pop()
                trim_a += 1
            trim_b = 0
            while len(current_output_b.layers) > 0 and current_output_b.layers[-1].is_empty():
                current_output_b.layers.pop()
                trim_b += 1
            if DEBUG_HYBRID:
                print(f"트리밍: A에서 {trim_a}개, B에서 {trim_b}개 꼬리 빈 레이어 제거")
            
            # B 출력에서 각 레이어별로 ----로 아예 빈 층 제거
            # 모든 빈 레이어를 제거 (위에서부터 순서대로)
            i = len(current_output_b.layers) - 1
            while i >= 0:
                current_layer = current_output_b.layers[i]
                is_empty_layer = True
                for q in range(4):
                    if current_layer.quadrants[q] is not None:
                        is_empty_layer = False
                        break
                if is_empty_layer:
                    current_output_b.layers.pop(i)
                    if DEBUG_HYBRID:
                        print(f"B 비어있는 레이어 제거: L{i}")
                i -= 1
            
            # output_b가 완전히 비어있는지 확인 (유효하지 않은 분할)
            if len(current_output_b.layers) == 0:
                if DEBUG_HYBRID:
                    print("B가 완전히 비어있음 → 이 패턴 스킵")
                continue
            
            # output_b에 실제 조각이 있는지 확인
            has_actual_pieces = False
            for layer in current_output_b.layers:
                for q in range(4):
                    if layer.quadrants[q] is not None:
                        has_actual_pieces = True
                        break
                if has_actual_pieces:
                    break
            
            if not has_actual_pieces:
                if DEBUG_HYBRID:
                    print("B에 실제 조각이 없음 → 이 패턴 스킵")
                continue
            
            # Shape.stack으로 두 도형을 합쳐서 원본과 비교
            try:
                stacked_shape = Shape.stack(current_output_a, current_output_b)
                if DEBUG_HYBRID:
                    try:
                        print(f"스택 결과: {repr(stacked_shape)}")
                        print(f"원본 비교: {repr(original_shape)}")
                    except Exception:
                        pass
                
                if repr(stacked_shape) == repr(original_shape):
                    if DEBUG_HYBRID:
                        print("스택 == 원본: 일치")
                    
                    # 추가 검증: current_output_a가 불가능한 도형인지 확인
                    try:
                        from shape_classifier import analyze_shape
                        output_a_type, output_a_reason = analyze_shape(repr(current_output_a), current_output_a, True)
                        
                        
                        if output_a_type != "analyzer.shape_types.impossible":  # 불가능한 도형이 아니라면
                            # 성공! 원본과 동일하고 output_a도 유효
                            best_output_a = current_output_a
                            best_output_b = current_output_b
                            if DEBUG_HYBRID:
                                print(f"Analyzer OK: {output_a_type}")
                                print("=== 매칭 OK: 이 패턴 채택 ===")
                            break
                        else:
                            if DEBUG_HYBRID:
                                print(f"Analyzer 결과 불가 도형 → 이 패턴 스킵: {output_a_type}")
                            continue
                    except Exception as e:
                        if DEBUG_HYBRID:
                            print(f"Analyzer 예외 → 이 패턴 스킵: {e}")
                        continue
                else:
                    # 차이점 분석
                    if len(repr(stacked_shape)) != len(repr(original_shape)):
                        if DEBUG_HYBRID:
                            print("스택 != 원본: 길이 다름")
                    else:
                        # 문자별로 비교하여 첫 번째 차이점 찾기
                        for i, (orig_char, result_char) in enumerate(zip(repr(original_shape), repr(stacked_shape))):
                            if orig_char != result_char:
                                if DEBUG_HYBRID:
                                    print(f"스택 != 원본: 첫 차이 idx {i} | orig='{orig_char}' vs stack='{result_char}'")
                                break
            except Exception as e:
                print(f"❌ stack 실패: {e}")
                # stack 실패 시 다음 패턴 시도
                continue
    
    # 3. 일치하는 패턴이 없거나 모든 패턴이 실패한 경우 기본 마스크 사용
    if best_output_a is None:
        # 기본적으로 모든 위치를 output_a(마스크 0)에 할당
        for l in range(len(shape.layers)):
            for q in range(4):
                mask[(l, q)] = 0
    else:
        # 성공한 패턴 사용
        output_a = best_output_a
        output_b = best_output_b
    
    # 최종 출력 B의 각 사분면에 대해 0층부터 시작해서 -가 아닌 조각이 나올 때까지 모든 빈 층을 c로 채우기
    if output_b:
        for q in range(4):  # 각 사분면에 대해 반복
            # 위층에서 -가 아닌 조각이 있는지 확인
            has_piece_above = False
            first_non_empty_layer = -1
            
            for l in range(len(output_b.layers)):
                piece = output_b._get_piece(l, q)
                if piece and piece.shape != '-':
                    has_piece_above = True
                    first_non_empty_layer = l
                    break
            
            # 위층에 조각이 있다면 0층부터 그 조각이 있는 층 바로 아래까지 모든 빈 층을 c로 채우기
            if has_piece_above and first_non_empty_layer > 0:
                for l in range(first_non_empty_layer):
                    # 해당 층이 비어있으면 c로 채우기
                    if output_b._get_piece(l, q) is None:
                        # 레이어가 존재하지 않으면 새로 생성
                        while len(output_b.layers) <= l:
                            output_b.layers.append(Layer([None, None, None, None]))
                        
                        output_b.layers[l].quadrants[q] = Quadrant('c', 'w')
                        if DEBUG_HYBRID:
                            print(f"B 채움: L{l} Q{q} <- c")
    
    # 리턴 직전에 원상복구 회전 적용
    if highest_crystal_quadrant == 1:
        if DEBUG_HYBRID:
            print("원상복구 회전: 시계 90도")
        output_a = output_a.rotate(clockwise=True)  # 90도 회전 (시계방향 1번)
        output_b = output_b.rotate(clockwise=True)
    elif highest_crystal_quadrant == 2:
        if DEBUG_HYBRID:
            print("원상복구 회전: 180도")
        output_a = output_a.rotate_180()  # 180도 회전
        output_b = output_b.rotate_180()
    elif highest_crystal_quadrant == 3:
        if DEBUG_HYBRID:
            print("원상복구 회전: 반시계 90도")
        output_a = output_a.rotate(clockwise=False)  # 270도 회전 (반시계방향 3번)
        output_b = output_b.rotate(clockwise=False)
    
    return output_a, output_b