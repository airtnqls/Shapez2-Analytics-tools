from __future__ import annotations
from shape_classifier import analyze_shape, ShapeType
from shape import Shape


def solve_shape(shape: str, shape_obj: Shape = None) -> tuple[str, str, str, str]:
    """
    도형을 분석하고 적절한 처리 방법을 결정하는 메인 함수
    
    Args:
        shape (str): 콜론으로 구분된 레이어 문자열
        shape_obj (Shape): Shape 객체 (선택사항)
    
    Returns:
        tuple[str, str, str, str]: (결과_도형, 건물_작동, 분류_타입, 분류_사유)
    """
    # 도형 분석
    classification_type, classification_reason = analyze_shape(shape, shape_obj)
    
    # Shape 객체가 없으면 생성
    if shape_obj is None:
        shape_obj = Shape.from_string(shape)
    
    # 분류 타입에 따른 처리
    if classification_type == ShapeType.CLAW.value:
        result_shape, building_operation = _handle_claw_type(shape_obj)
        return result_shape, building_operation, classification_type, classification_reason
    elif classification_type == ShapeType.SWAPABLE.value:
        result_shape, building_operation = _handle_swapable_type(shape_obj)
        return result_shape, building_operation, classification_type, classification_reason
    elif "CORNER" in classification_type:
        result_shape, building_operation = _handle_corner_type(shape_obj)
        return result_shape, building_operation, classification_type, classification_reason
    else:
        # 기타 분류 타입의 경우 원본 도형과 기본 작동 반환
        return repr(shape_obj), "기본", classification_type, classification_reason


def _handle_claw_type(shape_obj: Shape) -> tuple[str, str]:
    """
    Claw 타입 도형 처리
    
    Args:
        shape_obj (Shape): Shape 객체
    
    Returns:
        tuple[str, str]: (claw_tracer 적용된 도형, "핀푸쉬")
    """
    try:
        from claw_tracer import claw_process
        original_shape_str = repr(shape_obj)
        processed_shape_str = claw_process(original_shape_str)
        return processed_shape_str, "핀푸쉬"
    except ImportError:
        # claw_tracer 모듈이 없는 경우 원본 반환
        return repr(shape_obj), "핀푸쉬 (claw_tracer 없음)"


def _handle_swapable_type(shape_obj: Shape) -> tuple[str, str]:
    """
    SWAPABLE 타입 도형 처리
    
    Args:
        shape_obj (Shape): Shape 객체
    
    Returns:
        tuple[str, str]: (쿼드 쿼터 적용된 도형들, "스왑")
    """
    try:
        # quad_cutter를 사용하여 4개의 사분면으로 분할
        quad1, quad2, quad3, quad4 = shape_obj.quad_cutter()
        
        # 각 사분면을 문자열로 변환하고 콜론으로 구분
        quad_results = [
            repr(quad1),
            repr(quad2), 
            repr(quad3),
            repr(quad4)
        ]
        
        # 빈 문자열 제거하고 유효한 결과만 결합
        valid_results = [q for q in quad_results if q.strip()]
        result_string = " | ".join(valid_results) if valid_results else repr(shape_obj)
        
        return result_string, "스왑"
    except Exception as e:
        # 오류 발생 시 원본 반환
        return repr(shape_obj), f"스왑 (오류: {e})"


def _handle_corner_type(shape_obj: Shape) -> tuple[str, str]:
    """
    CORNER 타입 도형 처리
    
    Args:
        shape_obj (Shape): Shape 객체
    
    Returns:
        tuple[str, str]: (corner_tracer 적용된 도형, 건물작동)
    """
    try:
        from corner_tracer import corner_process
        original_shape_str = repr(shape_obj)
        processed_shape_str, building_operation = corner_process(original_shape_str)
        return processed_shape_str, building_operation
    except ImportError:
        # corner_tracer 모듈이 없는 경우 원본 반환
        return repr(shape_obj), "건물작동 (corner_tracer 없음)"
    except Exception as e:
        # 오류 발생 시 원본 반환
        return repr(shape_obj), f"건물작동 (오류: {e})"


def solve_shape_simple(shape: str, shape_obj: Shape = None) -> str:
    """
    이전 버전과의 호환성을 위한 함수 - 처리된 도형만 반환
    
    Args:
        shape (str): 콜론으로 구분된 레이어 문자열
        shape_obj (Shape): Shape 객체 (선택사항)
    
    Returns:
        str: 처리된 도형 문자열
    """
    result, _, _, _ = solve_shape(shape, shape_obj)
    return result


if __name__ == "__main__":
    # 테스트 코드
    from i18n import t
    test_shapes = [
        "SSSS:----",  # 단순 기하형
        "SSSS:cccc",  # _("solver.test.claw_possibility")
        "SSSS:----:SSSS",  # 스왑 가능성
        "S---:----:----:----"  # 모서리형
    ]
    
    for test_shape in test_shapes:
        print(f"원본: {test_shape}")
        try:
            shape_obj = Shape.from_string(test_shape)
            result, operation, classification_type, classification_reason = solve_shape(test_shape, shape_obj)
            print(f"결과: {result}")
            print(f"작동: {operation}")
            print(f"분류: {classification_type}")
            print(f"사유: {classification_reason}")
        except Exception as e:
            print(f"오류: {e}")
        print("-" * 50)
