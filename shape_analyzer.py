from __future__ import annotations
from enum import Enum
import re
from claw_tracer import verify_claw_process # verify_claw_process 함수 임포트


class ShapeType(Enum):
    """도형 분류 타입"""
    IMPOSSIBLE = "불가능형"
    EMPTY = "빈_도형"
    SIMPLE_GEOMETRIC = "단순_기하형"
    PIN_INCLUDED = "핀_포함형"
    CLAW_INCLUDED = "클로"
    HYBRID = "하이브리드"
    SWAPABLE = "스왑가능형"


def get_piece(shape: str, layer: int, quadrant: int) -> str:
    """
    특정 레이어의 특정 사분면에 있는 조각을 반환
    
    Args:
        shape (str): 콜론으로 구분된 레이어 문자열
        layer (int): 0부터 시작하는 레이어 인덱스
        quadrant (int): 0부터 시작하는 사분면 인덱스
    
    Returns:
        str: 해당 위치의 조각 문자, 범위를 벗어나면 '-' 반환
    """
    layers = shape.split(":")
    if layer < 0 or layer >= len(layers):
        return '-'
    if quadrant < 0 or quadrant >= len(layers[layer]):
        return '-'
    return layers[layer][quadrant]


def check_physics_stability(shape_obj) -> bool:
    """
    도형의 물리 안정성을 확인 (물리 적용 전후가 같은지 검사)
    
    Args:
        shape_obj: Shape 객체
    
    Returns:
        bool: 물리적으로 안정한 경우 True
    """
    try:
        original_repr = repr(shape_obj)
        physics_applied = shape_obj.apply_physics()
        physics_repr = repr(physics_applied)
        return original_repr == physics_repr
    except Exception:
        return False


def get_edge_pillars(shape: str) -> list[str]:
    """
    각 사분면별로 모든 레이어의 조각을 세로로 연결한 4개의 기둥 생성
    
    Args:
        shape (str): 콜론으로 구분된 레이어 문자열
    
    Returns:
        list[str]: 4개 사분면의 기둥 문자열 리스트
    """
    layers = shape.split(":")
    if not layers:
        return ["", "", "", ""]
    
    # 각 사분면별로 모든 층의 문자를 세로로 합침
    pillars = ["", "", "", ""]
    
    for layer in layers:
        # 각 층이 4글자가 아닌 경우 '-'로 패딩
        padded_layer = layer.ljust(4, '-')[:4]
        for i in range(4):
            pillars[i] += padded_layer[i]
    
    return pillars


def _check_impossible_patterns(pillars: list[str]) -> tuple[str | None, str | None]:
    """
    불가능형 패턴을 검사하여 해당하는 경우 분류와 사유를 반환
    
    Args:
        pillars (list[str]): 4개 사분면의 기둥 문자열
    
    Returns:
        tuple[str | None, str | None]: (분류_결과, 분류_사유)
    """
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
    """
    도형의 초기 분류를 결정 (빈 도형, 크리스탈 유무에 따른 기본 분류)
    
    Args:
        shape (str): 도형 문자열
    
    Returns:
        tuple[str, str]: (분류_결과, 분류_사유)
    """
    if shape.strip() == "" or shape.replace("-", "").replace(":", "") == "":
        return ShapeType.EMPTY.value, "도형이 비어있음"
    elif 'c' not in shape:  # 크리스탈이 없는 경우 최우선 단순기하형
        return ShapeType.SIMPLE_GEOMETRIC.value, "크리스탈 없음"
    else:  # 크리스탈이 포함된 경우, 추가 분류가 필요함을 알림
        return ShapeType.SIMPLE_GEOMETRIC.value, ""


def _check_limitations(pillars: list[str]) -> set[str]:
    """
    핀, 스왑, 스택과 같은 제한된 동작이 있는지 확인
    
    Args:
        pillars (list[str]): 4개 사분면의 기둥 문자열
    
    Returns:
        set[str]: 발견된 제한사항들의 집합
    """
    found_limitations = set()
    limitation_rules = [
        (r'^S*-?S*c', "핀푸쉬X", "OR"),      # 하나라도 해당하면 제한
        (r'-S-+c', "스왑X", "OR"),        # 하나라도 해당하면 제한
        (r'c$', "스택X", "AND")          # 모두 해당해야 제한
    ]

    for pattern, description, logic_type in limitation_rules:
        if logic_type == "OR":
            # OR 조건: 하나의 기둥이라도 패턴에 맞으면 제한사항 추가
            for pillar in pillars:
                if re.search(pattern, pillar):
                    found_limitations.add(description)
                    break
        elif logic_type == "AND":
            # AND 조건: 모든 기둥이 패턴에 맞아야 제한사항 추가
            is_and_condition_met = True
            for pillar in pillars:
                if not re.search(pattern, pillar):
                    is_and_condition_met = False
                    break
            if is_and_condition_met:
                found_limitations.add(description)
    
    return found_limitations


def _check_swap_impossibility(shape_obj) -> str | None:
    """
    simple_cutter를 이용한 스왑 불가능 여부를 확인
    
    Args:
        shape_obj: Shape 객체
    
    Returns:
        str | None: 스왑 불가능 상태 ("Claw", "12/34스왑 불가", "14/23스왑 불가", 조합) 또는 None
    """
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
        is_12_34_swap_impossible = True  # 오류 발생 시 해당 스왑은 불가능하다고 간주

    # 14/23 스왑 불가능성 확인 (90도 회전 후)
    try:
        rotated_shape_obj = shape_obj.rotate(clockwise=True)
        west_half_rotated, east_half_rotated = rotated_shape_obj.simple_cutter()
        if (repr(west_half_rotated) != repr(west_half_rotated.apply_physics())) or \
           (repr(east_half_rotated) != repr(east_half_rotated.apply_physics())):
            is_14_23_swap_impossible = True
    except Exception:
        is_14_23_swap_impossible = True  # 오류 발생 시 해당 스왑은 불가능하다고 간주

    # 스왑 불가능 상태 판별
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


def _remove_top_non_empty_layer(shape_obj):
    """
    도형에서 최상위 비어있지 않은 레이어를 제거
    
    Args:
        shape_obj: Shape 객체
    
    Returns:
        tuple: (새로운_Shape_객체, 제거된_레이어) 또는 (None, None)
    """
    if not shape_obj or not shape_obj.layers:
        return None, None

    new_layers = list(shape_obj.layers)
    removed_layer_content = None

    # 최상위부터 역순으로 탐색하여 비어있지 않은 층을 찾고 제거
    for i in range(len(new_layers) - 1, -1, -1):
        if repr(new_layers[i]).strip('-') != '':
            removed_layer_content = new_layers.pop(i)
            break
            
    if removed_layer_content is None:  # 모든 층이 비어있는 경우
        return None, None

    from shape import Shape  # 순환 참조 방지를 위한 지역 임포트
    return Shape(":".join(repr(layer) for layer in new_layers)), removed_layer_content


def _handle_crystal_free_classification(initial_swap_diagnosis: str | None, found_limitations: set[str]) -> tuple[str, list[str]]:
    """
    크리스탈이 없는 도형의 분류 처리
    
    Args:
        initial_swap_diagnosis (str | None): 초기 스왑 진단 결과
        found_limitations (set[str]): 발견된 제한사항들
    
    Returns:
        tuple[str, list[str]]: (분류_타입, 사유_리스트)
    """
    classification_type = ShapeType.SIMPLE_GEOMETRIC.value
    reasons = ["크리스탈 없음"]
    
    # 스왑 상태를 사유에 추가
    if initial_swap_diagnosis is not None:
        reasons.append(initial_swap_diagnosis)
    
    # 기타 제한사항 추가
    if found_limitations:
        reasons.append(", ".join(sorted(list(found_limitations))))
    
    return classification_type, reasons


def _perform_layer_removal_loop(current_working_shape_obj):
    """
    Claw 상태 해결을 위한 레이어 제거 루프 수행
    
    Args:
        current_working_shape_obj: 작업용 Shape 객체
    
    Returns:
        tuple: (제거된_레이어_내용들, 제거된_레이어_수, 최종_스왑_상태, 최종_Shape_객체)
    """
    removed_hybrid_layers_content = []
    layers_removed_count = 0
    final_swap_status_after_loop = None
    
    while current_working_shape_obj:
        loop_swap_check_result = _check_swap_impossibility(current_working_shape_obj)
        
        if loop_swap_check_result == "Claw":
            # 여전히 Claw인 경우, 레이어 제거 시도
            old_shape_obj_for_removal_check = current_working_shape_obj.copy()
            current_working_shape_obj, removed_layer_part = _remove_top_non_empty_layer(current_working_shape_obj)
            
            if removed_layer_part is None:  # 더 이상 제거할 비어있지 않은 레이어가 없음
                final_swap_status_after_loop = _check_swap_impossibility(old_shape_obj_for_removal_check)
                break
            
            removed_hybrid_layers_content.append(repr(removed_layer_part))
            layers_removed_count += 1
            
            if layers_removed_count > 100:  # 안전장치
                final_swap_status_after_loop = _check_swap_impossibility(current_working_shape_obj)
                break
        else:
            # 더 이상 "Claw"가 아님 (None 또는 특정 불가능성)
            final_swap_status_after_loop = loop_swap_check_result
            break
    
    return removed_hybrid_layers_content, layers_removed_count, final_swap_status_after_loop, current_working_shape_obj


def _classify_no_layer_removal_case(current_type: str, base_reason: str, initial_swap_diagnosis: str | None) -> tuple[str, list[str]]:
    """
    레이어 제거가 없었던 경우의 분류 처리
    
    Args:
        current_type (str): 현재 분류 타입
        base_reason (str): 기본 분류 사유
        initial_swap_diagnosis (str | None): 초기 스왑 진단 결과
    
    Returns:
        tuple[str, list[str]]: (최종_분류_타입, 사유_리스트)
    """
    reasons = []
    
    if initial_swap_diagnosis is None or "Claw" not in initial_swap_diagnosis:
        classification_type = ShapeType.SWAPABLE.value
        if base_reason and base_reason not in [ShapeType.IMPOSSIBLE.value, ShapeType.EMPTY.value]:
            reasons.append(base_reason)
        if initial_swap_diagnosis is not None:
            reasons.append(initial_swap_diagnosis)
    else:  # initial_swap_diagnosis is "Claw"
        classification_type = current_type
        reasons.append(initial_swap_diagnosis)
    
    return classification_type, reasons


def _classify_layer_removal_case(base_reason: str, removed_hybrid_layers_content: list[str], 
                                current_working_shape_obj, final_swap_status_after_loop: str | None) -> tuple[str, list[str]]:
    """
    레이어가 제거된 경우의 분류 처리
    
    Args:
        base_reason (str): 기본 분류 사유
        removed_hybrid_layers_content (list[str]): 제거된 레이어들의 내용
        current_working_shape_obj: 최종 작업 Shape 객체
        final_swap_status_after_loop (str | None): 루프 후 최종 스왑 상태
    
    Returns:
        tuple[str, list[str]]: (최종_분류_타입, 사유_리스트)
    """
    reasons = []
    
    # CLAW_INCLUDED 또는 HYBRID로 분류
    if any('c' in layer_content for layer_content in removed_hybrid_layers_content):
        classification_type = ShapeType.CLAW_INCLUDED.value
        if base_reason and base_reason not in reasons and not (base_reason == ""):
            reasons.insert(0, base_reason)
        reasons.append("Claw")
    else:
        classification_type = ShapeType.HYBRID.value
        if base_reason and base_reason not in reasons and base_reason != ShapeType.SIMPLE_GEOMETRIC.value:
            reasons.insert(0, base_reason)
        reasons.append("Hybrid")
    
    # 남은 층 수 추가
    remaining_layers_count = len(current_working_shape_obj.layers) if current_working_shape_obj else 0
    reasons.append(f"남은 층 수: {remaining_layers_count}")
    
    # 최종 스왑 상태 추가
    if final_swap_status_after_loop is not None:
        reasons.append(final_swap_status_after_loop)
    
    return classification_type, reasons


def _finalize_reasons(reasons: list[str]) -> str:
    """
    최종 사유 리스트를 중복 제거하고 문자열로 변환
    
    Args:
        reasons (list[str]): 사유 리스트
    
    Returns:
        str: 최종 사유 문자열
    """
    deduplicated_reasons = []
    seen_reasons = set()
    for reason in reasons:
        if reason and reason not in seen_reasons:
            deduplicated_reasons.append(reason)
            seen_reasons.add(reason)
    
    return " | ".join(filter(None, deduplicated_reasons))


def analyze_shape(shape: str, shape_obj=None) -> tuple[str, str]:
    """
    도형을 분석하여 분류와 사유를 반환하는 메인 함수
    
    Args:
        shape (str): 콜론으로 구분된 레이어 문자열 (예: "SSSS:----")
        shape_obj: Shape 객체 (물리 안정성 검사용)
    
    Returns:
        tuple[str, str]: (분류_결과, 분류_사유)
    """
    
    # ========== 1단계: 물리 안정성 검사 ==========
    if shape_obj and not check_physics_stability(shape_obj):
        return ShapeType.IMPOSSIBLE.value, "룰0. Unstable or -P"
    
    # ========== 2단계: 기본 분석 ==========
    pillars = get_edge_pillars(shape)
    
    # 불가능 패턴 검사
    impossible_type, impossible_reason = _check_impossible_patterns(pillars)
    if impossible_type:
        return impossible_type, impossible_reason

    # 초기 분류 및 제한사항 분석
    current_type, base_reason = _get_initial_shape_classification(shape)
    found_limitations = _check_limitations(pillars)
    initial_swap_diagnosis = _check_swap_impossibility(shape_obj)

    # ========== 3단계: 분류 로직 분기 ==========
    if base_reason == "크리스탈 없음":
        # 크리스탈 없는 단순 기하형 처리
        final_classification_type, final_reasons = _handle_crystal_free_classification(
            initial_swap_diagnosis, found_limitations
        )
    else:
        # 크리스탈이 포함된 경우 처리
        final_reasons = []
        if base_reason and base_reason not in [ShapeType.IMPOSSIBLE.value, ShapeType.EMPTY.value]:
            final_reasons.append(base_reason)

        # ========== 4단계: 레이어 제거 루프 수행 ==========
        current_working_shape_obj = shape_obj.copy() if shape_obj else None
        removed_hybrid_layers_content, layers_removed_count, final_swap_status_after_loop, current_working_shape_obj = _perform_layer_removal_loop(
            current_working_shape_obj
        )

        # ========== 5단계: 최종 분류 결정 ==========
        if layers_removed_count == 0:
            # 레이어 제거가 없었던 경우
            final_classification_type, classification_reasons = _classify_no_layer_removal_case(
                current_type, base_reason, initial_swap_diagnosis
            )
            final_reasons.extend(classification_reasons)
        else:
            # 레이어가 제거된 경우
            final_classification_type, classification_reasons = _classify_layer_removal_case(
                base_reason, removed_hybrid_layers_content, current_working_shape_obj, final_swap_status_after_loop
            )
            final_reasons.extend(classification_reasons)

        # ========== 6단계: 기타 제한사항 추가 ==========
        if found_limitations:
            final_reasons.append(", ".join(sorted(list(found_limitations))))

    # ========== 7단계: 최종 결과 반환 ==========
    # 클로 추가 검사
    if final_classification_type == ShapeType.CLAW_INCLUDED.value:
        # claw_process 검증 수행
        claw_verified = False
        if shape_obj:
            try:
                claw_verified = verify_claw_process(shape, repr(shape_obj))
            except Exception as e:
                final_reasons.append(f"클로 검증 오류: {e}")
                claw_verified = False

        if claw_verified:
            final_reasons.append("클로가능")
        else:
            final_reasons.append("클로불가능")
            # 클로 불가능으로 판명되면, 분류 타입을 Impossible로 변경할지 여부 결정
            # 현재는 Impossible로 변경하지 않고, 이유만 추가하여 자세한 정보 제공
            # final_classification_type = ShapeType.IMPOSSIBLE.value # 필요시 주석 해제

        first_layer = shape.split(':')[0] if shape else ''
        pin_count = first_layer.count('P')
        crystal_in_first_layer = 'c' in first_layer

        if pin_count <= 1:
            final_classification_type = ShapeType.IMPOSSIBLE.value
            final_reasons.clear()
            final_reasons.append("클로 룰1. 1F: P<2")
        elif crystal_in_first_layer:
            final_classification_type = ShapeType.IMPOSSIBLE.value
            final_reasons.clear()
            final_reasons.append("클로 룰2. 1F: c>0")

    final_reason_string = _finalize_reasons(final_reasons)
    return final_classification_type, final_reason_string


def analyze_shape_simple(shape: str, shape_obj=None) -> str:
    """
    이전 버전과의 호환성을 위한 함수 - 분류 결과만 반환
    
    Args:
        shape (str): 콜론으로 구분된 레이어 문자열
        shape_obj: Shape 객체 (선택사항)
    
    Returns:
        str: 분류 결과
    """
    result, _ = analyze_shape(shape, shape_obj)
    return result

