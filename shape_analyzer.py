from __future__ import annotations
from enum import Enum
import re


class ShapeType(Enum):
    """도형 분류 타입"""
    SIMPLE_GEOMETRIC = "단순_기하형"
    FAT_SHAPE = "Fat_Shape"
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


def _check_impossible_patterns(pillars: list[str]) -> tuple[str | None, str | None]:
    """도형이 불가능형으로 분류되어야 하는 패턴을 확인합니다."""
    impossible_patterns_for_type = [
        (r'^P*-+c', "코너 룰1. ^P*-+c"),
        (r'[^P]P.*c', "코너 룰2. [^P]P.*c"),
        (r'c-.*c', "코너 룰3. c-.*c"),
        (r'c.-+c', "코너 룰4. c.-+c"),
        (r'^c.*-S-+c', "코너 룰5. ^c.*-S-+c")
    ]
    
    for pillar_idx, pillar in enumerate(pillars):
        for pattern, description in impossible_patterns_for_type:
            if re.search(pattern, pillar):
                return ShapeType.IMPOSSIBLE.value, f"사분면 {pillar_idx+1}에서 {description} 위반"
    return None, None


def _get_initial_shape_classification(shape: str) -> tuple[str, str]:
    """도형의 초기 분류를 결정합니다."""
    if shape.strip() == "" or shape.replace("-", "").replace(":", "") == "":
        return ShapeType.EMPTY.value, "도형이 비어있음"
    elif not 'c' in shape:
        return ShapeType.SIMPLE_GEOMETRIC.value, "크리스탈 없음"
    elif 'c' in shape:
        return ShapeType.CRYSTAL_INCLUDED.value, "크리스탈 조각 포함"
    else:
        return ShapeType.MIXED.value, "혼합 도형"


def _check_limitations(pillars: list[str]) -> set[str]:
    """핀, 스왑, 스택과 같은 제한된 동작이 있는지 확인합니다."""
    found_limitations = set()
    limitation_rules = [
        (r'^S*-?S*c', "핀X", "OR"),
        (r'-S-+c', "스왑X", "OR"),
        (r'c$', "스택X", "AND")
    ]

    for pattern, description, logic_type in limitation_rules:
        if logic_type == "OR":
            for pillar in pillars:
                if re.search(pattern, pillar):
                    found_limitations.add(description)
                    break
        elif logic_type == "AND":
            is_and_condition_met = True
            for pillar in pillars:
                if not re.search(pattern, pillar):
                    is_and_condition_met = False
                    break
            if is_and_condition_met:
                found_limitations.add(description)
    return found_limitations


def _check_swap_impossibility(shape_obj) -> str | None:
    """simple_cutter를 이용한 스왑 불가능 여부를 확인합니다."""
    if shape_obj is None:
        return None

    is_12_34_swap_impossible = False
    is_14_23_swap_impossible = False

    # 12/34 스왑 불가능성 확인
    try:
        west_half, east_half = shape_obj.simple_cutter()
        if (repr(west_half) != repr(west_half.apply_physics())) or \
           (repr(east_half) != repr(east_half.apply_physics())):
            is_12_34_swap_impossible = True
    except Exception:
        pass # 오류 발생 시 해당 스왑은 불가능하다고 간주하지 않음

    # 14/23 스왑 불가능성 확인 (90도 회전 후)
    try:
        rotated_shape_obj = shape_obj.rotate(clockwise=True)
        west_half_rotated, east_half_rotated = rotated_shape_obj.simple_cutter()
        if (repr(west_half_rotated) != repr(west_half_rotated.apply_physics())) or \
           (repr(east_half_rotated) != repr(east_half_rotated.apply_physics())):
            is_14_23_swap_impossible = True
    except Exception:
        pass # 오류 발생 시 해당 스왑은 불가능하다고 간주하지 않음

    swap_notes = []
    if is_12_34_swap_impossible:
        swap_notes.append("12/34스왑 불가")
    if is_14_23_swap_impossible:
        swap_notes.append("14/23스왑 불가")

    if is_12_34_swap_impossible and is_14_23_swap_impossible:
        return "Claw"
    elif swap_notes:
        return ", ".join(swap_notes)
    else:
        return None


def analyze_shape(shape: str, shape_obj=None) -> tuple[str, str]:
    """
    shape: 콜론으로 구분된 레이어 문자열 (예: "SSSS:----")
    shape_obj: Shape 객체 (물리 안정성 검사용)
    
    Returns:
        tuple[str, str]: (분류_결과, 분류_사유)
    """
    
    # 1. 물리 안정성 검사
    if shape_obj and not check_physics_stability(shape_obj):
        return ShapeType.IMPOSSIBLE.value, "룰0. Unstable or -P"
    
    pillars = get_edge_pillars(shape)

    # 2. 불가능 패턴 검사
    impossible_type, impossible_reason = _check_impossible_patterns(pillars)
    if impossible_type:
        return impossible_type, impossible_reason

    # 3. 초기 분류
    # `current_type` will be modified based on further conditions.
    # `base_reason` stores the initial classification reason.
    current_type, base_reason = _get_initial_shape_classification(shape)

    # 4. 제한된 동작 여부 추가 분석 (핀X, 스왑X, 스택X)
    found_limitations = _check_limitations(pillars)
    
    # 5. 스왑 불가능성 추가 분석 (12/34, 14/23, Claw)
    swap_impossibility_note = _check_swap_impossibility(shape_obj)

    final_reason_parts = []
    # Start with the base classification reason
    if base_reason:
        final_reason_parts.append(base_reason)

    # Condition 1: Crystal Included but PinX -> Fat_Shape
    if current_type == ShapeType.CRYSTAL_INCLUDED.value and "핀X" in found_limitations and shape_obj and len(shape_obj.layers) >= 2:
        current_type = ShapeType.FAT_SHAPE.value
        # Add "핀X" specifically as a reason for Fat_Shape
        if "핀X" not in final_reason_parts: # Avoid duplication
            final_reason_parts.append("핀X")
        found_limitations.discard("핀X") # Remove it from generic limitations to avoid adding it again

    # Condition 2: Simple Geometric and Claw -> Fat_Shape
    # These two Fat_Shape conditions are mutually exclusive based on `initial_type`
    elif current_type == ShapeType.SIMPLE_GEOMETRIC.value and swap_impossibility_note == "Claw" and shape_obj and len(shape_obj.layers) >= 2:
        current_type = ShapeType.FAT_SHAPE.value
        # Add "Claw" specifically as a reason for Fat_Shape
        if "Claw" not in final_reason_parts: # Avoid duplication
            final_reason_parts.append("Claw")
        swap_impossibility_note = None # Prevent adding it again later

    # Add other general limitations (if any left after Fat_Shape specific handling)
    if found_limitations:
        final_reason_parts.append(", ".join(sorted(list(found_limitations))))

    # Add remaining swap impossibility notes (if not already handled as "Claw" for Fat_Shape)
    if swap_impossibility_note:
        final_reason_parts.append(swap_impossibility_note)

    # Join all reason parts with " | "
    final_reason = " | ".join(filter(None, final_reason_parts))

    return current_type, final_reason


def analyze_shape_simple(shape: str, shape_obj=None) -> str:
    """
    이전 버전과의 호환성을 위한 함수 - 분류 결과만 반환
    """
    result, _ = analyze_shape(shape, shape_obj)
    return result


# 추가 분석 기능들은 여기에 구현 예정 