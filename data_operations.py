"""
데이터 연산 관련 함수들을 모아놓은 모듈
GUI에서 데이터 처리 작업을 수행하는 함수들을 포함합니다.
"""

from typing import List, Optional, Tuple
from i18n import t
from shape import Shape
from shape_classifier import analyze_shape, ShapeType


def get_data_directory(filename=None):
    """사용자 데이터 저장 디렉토리 경로를 반환하는 함수
    
    Args:
        filename (str, optional): 파일명이 주어지면 전체 파일 경로를 반환
        
    Returns:
        str: 디렉토리 경로 또는 전체 파일 경로
    """
    import sys
    import os
    
    if hasattr(sys, '_MEIPASS'):
        # --onefile 빌드의 경우 사용자 홈 디렉토리에 data 폴더 생성
        base_dir = os.path.join(os.path.expanduser("~"), "Shapez2Analyzer", "data")
    elif hasattr(sys, 'frozen'):
        # --onedir 빌드의 경우 exe 위치 기준으로 data 폴더 생성
        exe_dir = os.path.dirname(sys.executable)
        base_dir = os.path.join(exe_dir, "data")
    else:
        # 일반 실행의 경우 현재 디렉토리의 data 폴더 사용
        base_dir = "data"
    
    if filename:
        return os.path.join(base_dir, filename)
    return base_dir


def simplify_shape(shape_code: str) -> str:
    """도형을 단순화합니다 - CuCuCuP- 같은 구조를 SSSP로 단순화"""
    try:
        shape = Shape.from_string(shape_code)
        # 각 레이어를 단순화된 형태로 변환
        simplified_layers = []
        for layer in shape.layers:
            simplified_layer = ""
            for quadrant in layer.quadrants:
                if quadrant is None:
                    simplified_layer += "-"
                elif quadrant.shape == 'c':
                    simplified_layer += "c"  # 크리스탈은 c로 유지
                elif quadrant.shape in ['C', 'R', 'W', 'S']:
                    simplified_layer += "S"  # CRWS를 S로 단순화
                elif quadrant.shape == 'P':
                    simplified_layer += "P"  # 핀은 그대로
                else:
                    simplified_layer += quadrant.shape  # 다른 도형은 그대로
            simplified_layers.append(simplified_layer)
        
        return ":".join(simplified_layers)
    except Exception as e:
        raise Exception(f"단순화 실패: {str(e)}")


def detail_shape(shape_code: str) -> str:
    """도형을 구체화합니다 - SSSP를 CuCuCuP-로 구체화 (from_string 논리와 동일)"""
    try:
        # Shape 객체로 변환 후 다시 문자열로 변환 (정규화)
        shape = Shape.from_string(shape_code)
        return repr(shape)
    except Exception as e:
        raise Exception(f"구체화 실패: {str(e)}")


def corner_1q_shape(shape_code: str) -> str:
    """1사분면 코너를 추출합니다 - 1사분면만 가져와서 한줄로 단순화"""
    try:
        shape = Shape.from_string(shape_code)
        # 각 레이어의 1사분면(인덱스 0)만 추출
        corner_chars = []
        for layer in shape.layers:
            if len(layer.quadrants) > 0 and layer.quadrants[0] is not None:
                quadrant = layer.quadrants[0]
                if quadrant.shape == 'c':
                    corner_chars.append("c")
                elif quadrant.shape == 'P':
                    corner_chars.append("P")
                else:
                    corner_chars.append("S")
            else:
                corner_chars.append("-")
        
        result = "".join(corner_chars)
        
        # 길이가 4 이하라면 Cornerize 실행
        if len(result) <= 4:
            return cornerize_shape(result)
        
        return result
    except Exception as e:
        raise Exception(f"1사분면 코너 추출 실패: {str(e)}")


def reverse_shape(shape_code: str) -> str:
    """도형 코드를 역순으로 변환합니다"""
    try:
        return shape_code[::-1]  # 문자열을 역순으로 변환
    except Exception as e:
        raise Exception(f"역순 변환 실패: {str(e)}")


def corner_shape_for_gui(shape_code: str) -> str:
    """Corner 연산을 수행합니다 - corner_tracer.py 기능 수행"""
    try:
        from corner_tracer import corner_process
        shape_obj = Shape.from_string(shape_code)
        result, _ = corner_process(shape_obj)
        return result
    except Exception as e:
        raise Exception(f"Corner 처리 실패: {str(e)}")


def claw_shape_for_gui(shape_code: str, logger=None) -> str:
    """Claw 연산을 수행합니다 - claw_tracer.py 기능 수행"""
    try:
        from claw_tracer import claw_process
        # claw_process 호출 시 logger 인자 전달
        return claw_process(shape_code, logger=logger)
    except Exception as e:
        raise Exception(f"Claw 처리 실패: {str(e)}")


def mirror_shape_for_gui(shape_code: str) -> str:
    """도형을 미러링합니다"""
    try:
        shape = Shape.from_string(shape_code)
        return repr(shape.mirror())
    except Exception as e:
        return f"오류: {str(e)}"


def cornerize_shape(shape_code: str) -> str:
    """도형을 코너화합니다 - 모든 문자 사이에 ':' 추가 (색코드 제외)"""
    try:
        # 색코드 정의
        color_codes = {'r', 'g', 'b', 'm', 'c', 'y', 'u', 'w'}
        
        # 기존 ':'를 제거
        cleaned_code = shape_code.replace(':', '')
        if not cleaned_code:
            return ""
        
        # c를 제외한 색코드 정의
        non_c_color_codes = {'r', 'g', 'b', 'm', 'y', 'u', 'w'}
        
        # c를 제외한 색코드가 하나라도 있는지 확인
        has_non_c_color_codes = any(char in non_c_color_codes for char in cleaned_code)
        
        result = ""
        if has_non_c_color_codes:
            # c를 제외한 색코드가 발견된 경우: 두 글자마다 ':' 배치
            for i, char in enumerate(cleaned_code):
                if i == 0:
                    result += char
                else:
                    # 짝수번째 글자 앞에만 ':' 추가 (0부터 시작하므로 짝수 인덱스가 첫번째 글자)
                    if i % 2 == 0: 
                        result += ':'
                    result += char
        else:
            # c를 제외한 색코드가 발견되지 않은 경우: 한 글자마다 ':' 배치
            result = ':'.join(cleaned_code)
        
        return result
    except Exception as e:
        return f"오류: {str(e)}"


def hybrid_shape(shape_code: str) -> List[str]:
    """도형을 하이브리드로 분리합니다 - 도형을 두 부분으로 분리"""
    try:
        if not shape_code.strip():
            return ["", ""]
        
        from hybrid_tracer import hybrid
        shape = Shape.from_string(shape_code)
        output_a, output_b = hybrid(shape)
        
        # 두 개의 별도 결과 반환
        result_a = repr(output_a) if output_a.layers else ""
        result_b = repr(output_b) if output_b.layers else ""
        
        return [result_a, result_b]
            
    except Exception as e:
        return [f"오류: {str(e)}", ""]


def remove_impossible_shapes(data: List[str], logger=None) -> Tuple[List[str], int]:
    """불가능한 도형들을 제거합니다"""
    valid_data = []
    removed_count = 0
    
    for i, shape_code in enumerate(data):
        try:
            shape = Shape.from_string(shape_code)
            classification, reason = analyze_shape(shape_code, shape)
            if classification != ShapeType.IMPOSSIBLE.value:
                valid_data.append(shape_code)
            else:
                removed_count += 1
                if logger:
                    logger(f"제거됨: {shape_code} ({reason})")
        except Exception as e:
            removed_count += 1
            if logger:
                logger(f"오류로 제거됨: {shape_code} ({str(e)})")
    
    return valid_data, removed_count


def process_batch_operation(shape_code: str, operation_name: str, input_b_text: str = "", paint_color: str = "", crystal_color: str = "") -> Tuple[str, List[str]]:
    """배치 연산을 처리합니다"""
    try:
        shape = Shape.from_string(shape_code)
        result_shape = None
        append_values = []
        
        if operation_name == "destroy_half":
            result_shape = shape.destroy_half()
        elif operation_name == "push_pin":
            result_shape = shape.push_pin()
        elif operation_name == "apply_physics":
            result_shape = shape.apply_physics()
        elif operation_name == "rotate_cw":
            result_shape = shape.rotate(True)
        elif operation_name == "rotate_ccw":
            result_shape = shape.rotate(False)
        elif operation_name == "rotate_180":
            result_shape = shape.rotate_180()
        elif operation_name == "mirror":
            result_shape = shape.mirror()
        elif operation_name == "paint":
            result_shape = shape.paint(paint_color)
        elif operation_name == "crystal_generator":
            result_shape = shape.crystal_generator(crystal_color)
        elif operation_name == "classifier":
            cls_res, cls_reason = shape.classifier()
            return f"{cls_res} ({cls_reason})", []
        elif operation_name == "simple_cutter":
            res_a, res_b = shape.simple_cutter()
            append_values.append(repr(res_b))
            return repr(res_a), append_values
        elif operation_name == "quad_cutter":
            res_a, res_b, res_c, res_d = shape.quad_cutter()
            append_values.extend([repr(res_b), repr(res_c), repr(res_d)])
            return repr(res_a), append_values
        elif operation_name == "half_cutter":
            res_a, res_b = shape.half_cutter()
            append_values.append(repr(res_b))
            return repr(res_a), append_values
        elif operation_name == "stack":
            if not input_b_text:
                return t("error.input.b.empty"), []
            shape_b = Shape.from_string(input_b_text)
            result_shape = Shape.stack(shape, shape_b)
        elif operation_name == "swap":
            if not input_b_text:
                return t("error.input.b.empty"), []
            shape_b = Shape.from_string(input_b_text)
            result_a, result_b = Shape.swap(shape, shape_b)
            append_values.append(repr(result_b))
            return repr(result_a), append_values
        
        return (repr(result_shape) if result_shape is not None else t("ui.table.error", error="no result")), append_values
        
    except Exception as e:
        return f"오류: {str(e)}", []


def calculate_complexity(origin_shape: object) -> int:
    """도형의 복잡도를 계산합니다"""
    try:
        if hasattr(origin_shape, 'layers'):
            total_quadrants = sum(len(layer.quadrants) for layer in origin_shape.layers)
            non_empty_quadrants = sum(
                sum(1 for q in layer.quadrants if q is not None)
                for layer in origin_shape.layers
            )
            return total_quadrants - non_empty_quadrants
        return 0
    except Exception:
        return 0





def parse_shape_or_none(text: str) -> Optional[Shape]:
    """텍스트를 Shape 객체로 파싱하거나 None을 반환합니다"""
    try:
        if text.strip():
            return Shape.from_string(text)
    except Exception:
        pass
    return None



