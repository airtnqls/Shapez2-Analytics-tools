from __future__ import annotations
from enum import Enum
import re


class ShapeType(Enum):
    """도형 분류 타입"""
    SIMPLE_GEOMETRIC = "단순_기하형"
    PIN_INCLUDED = "핀_포함형"
    CRYSTAL_INCLUDED = "크리스탈_포함형"
    MIXED = "혼합형"
    EMPTY = "빈_도형"
    IMPOSSIBLE = "불가능형"


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


def check_physics_stability(shape_obj) -> bool:
    """물리 적용 전후가 같은지 확인"""
    try:
        original_repr = repr(shape_obj)
        physics_applied = shape_obj.apply_physics()
        physics_repr = repr(physics_applied)
        return original_repr == physics_repr
    except Exception:
        return False


def get_edge_pillars(shape: str) -> list[str]:
    """각 모서리별로 층을 합친 4개의 모서리 기둥을 생성"""
    layers = shape.split(":")
    if not layers:
        return ["", "", "", ""]
    
    # 각 사분면별로 모든 층의 문자를 합침
    pillars = ["", "", "", ""]
    
    for layer in layers:
        # 각 층이 4글자가 아닌 경우 '-'로 패딩
        padded_layer = layer.ljust(4, '-')[:4]
        for i in range(4):
            pillars[i] += padded_layer[i]
    
    return pillars


def check_impossible_patterns(pillars: list[str]) -> bool:
    """불가능한 패턴들을 검사"""
    patterns = [
        r'^P*-+c',      # 2-1: 시작이 P*, 그 다음 -+, 그 다음 c
        r'[^P]P.*c',    # 2-2: P가 아닌 문자 다음에 P, 그 다음 임의 문자들, 그 다음 c
        r'c-.*c',       # 2-3: c 다음에 -, 그 다음 임의 문자들, 그 다음 c
        r'c.-+c'        # 2-4: c 다음에 임의 문자 1개, 그 다음 -+, 그 다음 c
    ]
    
    for pillar in pillars:
        for pattern in patterns:
            if re.search(pattern, pillar):
                return True
    return False


def analyze_shape(shape: str, shape_obj=None) -> tuple[str, str]:
    """
    shape: 콜론으로 구분된 레이어 문자열 (예: "SSSS:----")
    shape_obj: Shape 객체 (물리 안정성 검사용)
    
    Returns:
        tuple[str, str]: (분류_결과, 분류_사유)
    """
    
    # 1. 물리 안정성 검사
    if shape_obj and not check_physics_stability(shape_obj):
        return ShapeType.IMPOSSIBLE.value, "불안정한 도형"
    
    # 2. 모서리 기둥 패턴 검사
    pillars = get_edge_pillars(shape)
    if check_impossible_patterns(pillars):
        # 구체적인 패턴 찾기
        patterns = [
            (r'^P*-+c', "코너 룰1. ^P*-+c"),
            (r'[^P]P.*c', "코너 룰2. [^P]P.*c"),
            (r'c-.*c', "코너 룰3. c-.*c"),
            (r'c.-+c', "코너 룰4. c.-+c")
        ]
        
        for pillar_idx, pillar in enumerate(pillars):
            for pattern, description in patterns:
                if re.search(pattern, pillar):
                    return ShapeType.IMPOSSIBLE.value, f"사분면 {pillar_idx+1}에서 {description} 발견"
    
    # 3. 기존 분류 로직
    if shape.strip() == "" or shape.replace("-", "").replace(":", "") == "":
        return ShapeType.EMPTY.value, "도형이 비어있음"
    elif shape.startswith('S'):
        return ShapeType.SIMPLE_GEOMETRIC.value, "첫 번째 사분면이 단순 기하 도형"
    elif 'P' in shape:
        return ShapeType.PIN_INCLUDED.value, "핀 조각 포함"
    elif 'c' in shape:
        return ShapeType.CRYSTAL_INCLUDED.value, "크리스탈 조각 포함"
    else:
        return ShapeType.MIXED.value, "혼합 도형"


def analyze_shape_simple(shape: str, shape_obj=None) -> str:
    """
    이전 버전과의 호환성을 위한 함수 - 분류 결과만 반환
    """
    result, _ = analyze_shape(shape, shape_obj)
    return result


# 추가 분석 기능들은 여기에 구현 예정 