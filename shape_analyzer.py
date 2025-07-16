from __future__ import annotations


def get_piece(shape: str, layer: int, quadrant: int) -> str:
    """
    layer (int): 0부터 시작하는 레이어 인덱스
    quadrant (int): 0부터 시작하는 사분면 인덱스
    """
    layers = shape.split(":")
    if layer < 0 or layer >= len(layers):
        return '-'# raise IndexError("레이어 인덱스가 범위를 벗어났습니다.")
    if quadrant < 0 or quadrant >= len(layers[layer]):
        return '-'#raise IndexError("사분면 인덱스가 범위를 벗어났습니다.")
    return layers[layer][quadrant]


def analyze_shape(shape: str) -> str:
    result = ""
    """
    shape: 콜론으로 구분된 레이어 문자열 (예: "SSSS:----")
    """
    if shape.startswith('S'):
        return "단순_기하형"
    elif 'P' in shape:
        return "핀_포함형"
    elif 'c' in shape:
        return "크리스탈_포함형"
    elif shape.strip() == "" or shape.replace("-", "").replace(":", "") == "":
        return "빈_도형"
    else:
        return "혼합형"
    
    
    
    return result

# 추가 분석 기능들은 여기에 구현 예정 