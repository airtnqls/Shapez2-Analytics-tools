"""
하이브리드 도형 분석 모듈

이 모듈은 Shape 클래스의 하이브리드 분석 로직을 담당합니다.
하이브리드 분석은 도형을 마스크 기반으로 두 부분으로 분리하는 기능을 제공합니다.
"""

from typing import Set, Tuple
from shape import Shape, Layer
from data_operations import simplify_shape
import re

# 하이브리드 패턴 매칭을 위한 정규식 패턴과 마스크 데이터
HYBRID_PATTERNS = {
    "P-PP:PSS[^c]:P-[^c][^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0001:0011:0011:0111",
    "--PP:--[PS]c:SS[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]": "0000:0000:0010:0111:1111", # Symmetry?
    "[P-]-[P-]P:[c-]-[c-][PS]:SSS[^c]:S[^c][^c][^c]:c[^c][^c][^c]": "0000:0000:0001:0111:0111",
    "--PP:PP[PS]c:SS[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]": "0000:0000:0010:0111:0111", # Symmetry?
    "-PPP:SP[^c]S:[S-][PS][^c][^c]:[c-]P[^c][^c]:cS[^c][^c]": "0000:0010:0011:0011:0011",
    "P-PP:PSS[^c]:P.[^c][^c]:[PS]-[^c][^c]:cS[^c][^c]": "0000:0001:0011:0011:0011",
    "P[P-]P[P-]:[^-]-[^c]-:cS[^c]S:[^c][^c][^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:1111:1111", # Symmetry
    ".-PP:.-c[SP]:-SS[^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0000:0001:0011:0111",
    "P-PP:P-[PS]S:PSc[^c]:[^-]-S[^c]:cS[^c][^c]": "0000:0000:0001:0001:0011",
    "P-P[^c]:P-[^-][^c]:PSc[^c]:[^-]-S[^c]:cS[^c][^c]": "0001:0001:0001:0001:0011",
    "..P.:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:0111:1111", # Symmetry
    "..P.:..[PS].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0000:0010:0011:1111",
    "...P:...[^c]:S[Sc]S[^c]:S[^c][^c][^c]:c[^c][^c][^c]": "0000:0001:0001:0111:0111",
    "P.P.:..[^c].:[Sc]S[^c]S:[Sc][^c][^c][^c]:c[^c][^c][^c]": "0000:0010:0010:0111:0111", # Symmetry
    "...P:...[^c]:-[Sc]S[^c]:SS[^c][^c]:c[^c][^c][^c]": "0000:0001:0001:0011:0111",
    "..P.:..[^c].:[Sc]-[^c]S:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0010:0010:0011:1111",
    "..P.:..[PS].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0000:0010:0011:0111",
    "-.PP:-.[^-][^-]:[Sc]-[PS][^-]:cS[^c][^c]:[^c][^c][^c][^c]": "0000:0000:0000:0011:1111",
    "..P.:..[^c].:..[^c].:cS[^c]S:[^c][^c][^c][^c]": "0000:0010:0010:0010:1111", # Symmetry
    "P..[^c]:[^-]..[^c]:[^-][Sc]S[^c]:[^-]-[^c][^c]:cS[^c][^c]": "0001:0001:0001:0011:0011",
    "..P.:..[^c].:[Sc]-[^c]S:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0010:0010:0011:0111",
    "P.P.:..[PS].:..[^c].:cS[^c]S:[^c][^c][^c][^c]": "0000:0000:0010:0010:1111", # Symmetry
    "[P-][P-]PP:[P-].[^-][^-]:[S-][S-][PS][Sc]:[Sc]S[^c][^c]:c[^c][^c][^c]": "0000:0000:0000:0011:0111",
    ".[-]PP:[P-]-[^-][^-]:.SS[^c]:.[P-][^c][^c]:cS[^c][^c]": "0000:0000:0001:0011:0011",
    "P.P.:[^-].[^-].:..[^-].:cS[^c]S:[^c][^c][^c][^c]": "0000:0000:0000:0010:1111", # Symmetry
    "..P.:..[PS].:..[^c]S:..[^c][^c]:cS[^c][^c]": "0000:0000:0010:0011:0011",
    "...P:...[^c]:.[Sc]S[^c]:..[^c][^c]:cS[^c][^c]": "0000:0001:0001:0011:0011",
    "..P.:..[^c].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0010:0010:0010:0111", # Symmetry
    "..P.:..[PS].:..[^c].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0000:0010:0010:0111", # Symmetry
    "[P-]-PP:[P-]-[^-][^-]:[PS][S-]c[Sc]:[^-]-S[^c]:cS[^c][^c]": "0000:0000:0000:0001:0011",
    "..P.:..[^c].:[Sc].[^c]S:..[^c][^c]:cS[^c][^c]": "0000:0010:0010:0011:0011",
    "..P.:..[^-].:..[PS].:[Sc]S[^c]S:c[^c][^c][^c]": "0000:0000:0000:0010:0111", # Symmetry
    "....:....:..[PS][Sc]:[^P][P-][^c][^c]:cS[^c][^c]": "0000:0000:0000:0011:0011",
    "..P.:..[^c].:..[^c].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0010:0010:0010:0011",
    "..P.:..[PS].:..[^c].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0000:0010:0010:0011",
    "..P.:..[^c].:..[^c].:..[^c].:cS[^c]S": "0000:0010:0010:0010:0010", # Symmetry
    "..P.:..[PS].:..[^c].:..[^c].:cS[^c]S": "0000:0000:0010:0010:0010", # Symmetry
    "....:....:..[PS].:[Sc][P-][^c]S:cS[^c][^c]": "0000:0000:0000:0010:0011",
    "....:....:..[^-].:[Sc]-[PS][^-]:cS[^c][^c]": "0000:0000:0000:0000:0011",
    "....:....:..[PS].:..[^c].:cS[^c]S": "0000:0000:0000:0010:0010", # Symmetry
    "....:....:....:..[PS].:cS[^c]S": "0000:0000:0000:0000:0010" # Symmetry
}

def swap_2nd_and_4th(segment: str) -> str:
    """4글자 문자열의 2번째와 4번째 문자를 교체합니다."""
    # 문자열은 불변(immutable)하므로 리스트로 변환하여 처리
    if len(segment) == 4:
        chars = list(segment)
        # 인덱스는 0부터 시작하므로 2번째는 인덱스 1, 4번째는 인덱스 3
        chars[1], chars[3] = chars[3], chars[1]
        return "".join(chars)
    # 만약 4글자가 아니면 원본 그대로 반환
    return segment

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
    mask = {}
    shape_str = repr(shape)
    simplified_str = simplify_shape(shape_str)
    
    # 2. HYBRID_PATTERNS의 각 키에 대해 순차적으로 정규식 패턴 검사
    import re
    matched_mask_str = None
    
    for pattern_key in HYBRID_PATTERNS:
        if re.fullmatch(pattern_key, simplified_str):
            matched_mask_str = HYBRID_PATTERNS[pattern_key]
            break
    
    # 3. 일치하는 패턴이 없으면 기본 마스크 사용 (모든 위치를 0으로)
    if matched_mask_str is None:
        # 기본적으로 모든 위치를 output_a(마스크 0)에 할당
        for l in range(len(shape.layers)):
            for q in range(4):
                mask[(l, q)] = 0
    else:
        # 4. 마스크 문자열을 딕셔너리로 변환
        mask_layers = matched_mask_str.split(':')
        for l, layer_mask in enumerate(mask_layers):
            if l < len(shape.layers):
                for q, bit in enumerate(layer_mask):
                    if q < 4:
                        mask[(l, q)] = int(bit)
    
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