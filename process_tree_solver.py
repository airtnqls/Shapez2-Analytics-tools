"""
공정 트리 솔버 - 입력 도형의 제작 공정을 트리 형태로 계산하는 모듈
"""

from typing import List, Dict, Optional, Tuple
from shape import Shape
from shape_classifier import analyze_shape_simple
from corner_tracer import build_cutable_shape, build_pinable_shape


class ProcessNode:
    """공정 트리의 단일 노드를 나타내는 클래스"""
    
    def __init__(self, shape_code: str, operation: str = "", inputs: List['ProcessNode'] = None):
        self.shape_code = shape_code
        self.operation = operation  # 이 노드를 만들기 위한 작업 (예: "claw", "stack", "paint" 등)
        self.inputs = inputs or []  # 입력으로 사용된 다른 노드들
        self.shape_obj = None
        
        # 도형 객체 생성 시도
        try:
            self.shape_obj = Shape.from_string(shape_code)
        except Exception:
            self.shape_obj = None
    
    def is_valid(self) -> bool:
        """노드의 도형이 유효한지 확인"""
        return self.shape_obj is not None
    
    def get_complexity(self) -> int:
        """노드의 복잡도 계산 (층수 기준)"""
        if not self.shape_obj:
            return 0
        return len(self.shape_obj.layers)


def build_tree_from_data(tree_data: Dict) -> Optional[ProcessNode]:
    """
    딕셔너리 형태의 트리 데이터를 ProcessNode 트리로 변환
    
    트리 데이터 형태:
    {
        "shape_code": "도형코드",
        "operation": "작업명", 
        "inputs": [
            {
                "shape_code": "자식1_도형코드",
                "operation": "자식1_작업명",
                "inputs": []
            },
            {
                "shape_code": "자식2_도형코드", 
                "operation": "자식2_작업명",
                "inputs": []
            }
        ]
    }
    
    Args:
        tree_data: 딕셔너리 형태의 트리 데이터
        
    Returns:
        변환된 ProcessNode 트리의 루트 노드
    """
    if not isinstance(tree_data, dict):
        return None
    
    # 현재 노드 생성
    shape_code = tree_data.get("shape_code", "")
    operation = tree_data.get("operation", "")
    node = ProcessNode(shape_code, operation)
    
    # 입력(자식) 노드들 재귀적으로 생성
    inputs_data = tree_data.get("inputs", [])
    node.inputs = []
    for input_data in inputs_data:
        child_node = build_tree_from_data(input_data)
        if child_node:
            node.inputs.append(child_node)
    
    return node


def tree_to_data(root_node: ProcessNode) -> Dict:
    """
    ProcessNode 트리를 딕셔너리 데이터로 변환
    
    Args:
        root_node: 변환할 트리의 루트 노드
        
    Returns:
        딕셔너리 형태의 트리 데이터
    """
    if not root_node:
        return {}
    
    # 자식 노드들을 재귀적으로 변환
    inputs_data = []
    for child in root_node.inputs:
        child_data = tree_to_data(child)
        if child_data:
            inputs_data.append(child_data)
    
    return {
        "shape_code": root_node.shape_code,
        "operation": root_node.operation,
        "inputs": inputs_data
    }


class ProcessTreeSolver:
    """공정 트리를 계산하는 솔버 클래스"""
    
    IMPOSSIBLE_OPERATION = "불가능한 도형"

    def __init__(self):
        self.max_depth = 5  # 최대 탐색 깊이
    
    def create_tree_from_data(self, tree_data: Dict) -> Optional[ProcessNode]:
        """
        외부 데이터로부터 트리를 생성하는 공개 메서드
        
        Args:
            tree_data: 딕셔너리 형태의 트리 데이터
            
        Returns:
            생성된 ProcessNode 트리
        """
        return build_tree_from_data(tree_data)
        
    def solve_process_tree(self, target_shape_code: str) -> Optional[ProcessNode]:
        """
        주어진 목표 도형에 대한 공정 트리를 계산합니다.
        
        Args:
            target_shape_code: 목표 도형 코드
            
        Returns:
            ProcessNode: 공정 트리의 루트 노드, 실패시 불가능 노드 포함
        """
        root_node = ProcessNode(target_shape_code, "목표") # 항상 목표 도형으로 시작
        
        try:
            # 1. 입력 도형의 유효성 검사 (Shape.from_string 성공 여부)
            target_shape_obj = Shape.from_string(target_shape_code)
            root_node.shape_obj = target_shape_obj # 루트 노드에 shape_obj 설정
            
            # 2. 도형 분석 - 논리적으로 불가능한 도형인지 확인
            analysis_result = analyze_shape_simple(target_shape_code, target_shape_obj)
            if "불가능" in analysis_result:
                # 도형 코드 자체는 유효하지만, 논리적으로 불가능한 도형인 경우
                # 루트 노드 아래에 불가능한 자식 노드를 추가
                impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION)
                root_node.inputs.append(impossible_child_node)
                root_node.operation = "불가능"
                return root_node
                
            # 3. 임시 구현: claw_tracer 결과를 사용하여 간단한 트리 생성
            # _create_simple_tree가 반환하는 서브트리를 루트의 자식으로 추가
            simple_tree_root = self._create_simple_tree(target_shape_code, target_shape_obj)
            # _create_simple_tree는 이제 자식 노드만 반환 (또는 루트와 자식 포함된 서브트리)
            # 여기서는 simple_tree_root의 자식들을 가져와서 현재 root_node의 자식으로 설정
            # 그리고 simple_tree_root의 operation을 현재 root_node의 operation으로 설정
            if simple_tree_root:
                root_node.inputs.extend(simple_tree_root.inputs)
                if simple_tree_root.operation != "목표": # 목표가 아니면 업데이트
                    root_node.operation = simple_tree_root.operation
            else:
                # _create_simple_tree가 None을 반환하는 경우 (오류 처리)
                impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION)
                root_node.inputs.append(impossible_child_node)
                root_node.operation = "생성 오류"

            return root_node
            
        except Exception as e:
            # Shape.from_string 실패 (문법 오류) 또는 기타 예외 발생 시
            print(f"공정 트리 계산 오류: {e}")
            # 루트 노드 자체는 유지하되, 하위에 불가능 노드 추가
            impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION)
            root_node.inputs.append(impossible_child_node)
            root_node.operation = "문법 오류/생성 오류"
            return root_node
    
    def _extract_first_layer(self, corner_result: str) -> str:
        """corner tracer 결과에서 첫 번째 층만 추출"""
        try:
            # ":"로 분리된 경우 첫 번째 부분 사용
            if ":" in corner_result:
                layers = corner_result.split(":")
                if layers:
                    return layers[0]
            return corner_result
        except Exception:
            return corner_result
    
    def _create_simple_tree(self, target_shape_code: str, target_shape: Shape) -> ProcessNode:
        """
        임시 구현: corner_tracer를 사용하여 간단한 2단계 트리를 생성합니다.
        이 함수는 목표 도형에 대한 공정 서브트리의 루트 노드를 반환합니다.
        """
        # 여기서 생성되는 루트 노드는 solve_process_tree에서 최종 루트의 자식으로 연결될 것임.
        # 따라서 target_shape_code에 대한 중간 단계의 루트 노드로 생각.
        current_node_for_tracing = ProcessNode(target_shape_code, "코너추적대상")
        current_node_for_tracing.shape_obj = target_shape # shape_obj도 설정
        
        try:
            # corner_tracer를 사용하여 이전 단계 도형 찾기
            if target_shape_code and target_shape_code[0] == 'P':
                corner_result = build_pinable_shape(target_shape_code)
            else:
                corner_result = build_cutable_shape(target_shape_code)
            
            if corner_result and corner_result != target_shape_code:
                previous_shape_code = self._extract_first_layer(corner_result)
                
                # 이전 단계 도형이 유효한지 다시 확인
                prev_shape_obj = Shape.from_string(previous_shape_code)
                if not prev_shape_obj: # 유효하지 않으면 불가능 노드로 표시
                    previous_node = ProcessNode(previous_shape_code, self.IMPOSSIBLE_OPERATION)
                else:
                    previous_node = ProcessNode(previous_shape_code, "corner")
                
                current_node_for_tracing.inputs = [previous_node]
                current_node_for_tracing.operation = "corner 적용"
                
                # 더 간단한 기본 도형이 있는지 확인 (임시로 단순화)
                if previous_node.operation != self.IMPOSSIBLE_OPERATION and self._is_simple_shape(previous_shape_code):
                    # 기본 도형으로 간주
                    previous_node.operation = "기본 도형"
                elif previous_node.operation != self.IMPOSSIBLE_OPERATION: # 불가능 노드가 아닐 때만 분해 시도
                    base_shape = self._get_base_shape(previous_shape_code)
                    if base_shape != previous_shape_code:
                        # 기본 도형이 유효한지 확인
                        base_shape_obj = Shape.from_string(base_shape)
                        if not base_shape_obj:
                            base_node = ProcessNode(base_shape, self.IMPOSSIBLE_OPERATION)
                        else:
                            base_node = ProcessNode(base_shape, "기본 도형")
                        previous_node.inputs = [base_node]
                        previous_node.operation = "조합"
                        
        except Exception as e:
            print(f"_create_simple_tree 내부 오류: {e}")
            # corner tracer 처리 중 오류가 발생하면, 하위 노드를 불가능 노드로 설정
            # 루트 노드 자체는 유지하되, 하위에 불가능 노드 추가
            impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION)
            current_node_for_tracing.inputs = [impossible_child_node]
            current_node_for_tracing.operation = "코너추적실패"
            
        return current_node_for_tracing
    
    def _is_simple_shape(self, shape_code: str) -> bool:
        """도형이 단순한 기본 도형인지 확인"""
        # 단일 층이고 단순한 패턴인지 확인
        try:
            shape = Shape.from_string(shape_code)
            if not shape or len(shape.layers) > 1:
                return False
                
            # 첫 번째 층만 확인
            layer = shape.layers[0]
            unique_quadrants = set()
            for quadrant in layer.quadrants:
                if quadrant and quadrant.shape and quadrant.color:
                    unique_quadrants.add(f"{quadrant.shape}{quadrant.color}")
                    
            # 고유한 조각이 2개 이하면 단순한 것으로 간주
            return len(unique_quadrants) <= 2
            
        except Exception:
            return False
    
    def _get_base_shape(self, shape_code: str) -> str:
        """복잡한 도형을 더 단순한 기본 도형으로 변환"""
        # 임시 구현: 첫 번째 층의 첫 번째 사분면만 사용하여 기본 도형 생성
        try:
            shape = Shape.from_string(shape_code)
            if not shape or not shape.layers:
                return shape_code
                
            first_layer = shape.layers[0]
            first_quadrant = first_layer.quadrants[0]
            
            if first_quadrant and first_quadrant.shape and first_quadrant.color:
                # 단일 사분면으로 구성된 기본 도형 생성
                base_shape = f"{first_quadrant.shape}{first_quadrant.color}" * 4
                return base_shape
                
        except Exception:
            pass
            
        return shape_code
    
    def get_tree_levels(self, root_node: ProcessNode) -> List[List[ProcessNode]]:
        """
        트리를 레벨별로 분류하여 반환합니다.
        
        Args:
            root_node: 트리의 루트 노드
            
        Returns:
            List[List[ProcessNode]]: 각 레벨별 노드들의 리스트
        """
        if not root_node:
            return []
            
        levels = []
        current_level = [root_node]
        
        while current_level:
            levels.append(current_level[:])  # 현재 레벨 복사
            next_level = []
            
            for node in current_level:
                next_level.extend(node.inputs)
                
            current_level = next_level
            
        return levels
    
    def print_tree(self, root_node: ProcessNode, indent: int = 0):
        """디버깅용 트리 출력 함수"""
        if not root_node:
            return
            
        print("  " * indent + f"- {root_node.shape_code} ({root_node.operation})")
        for input_node in root_node.inputs:
            self.print_tree(input_node, indent + 1)


# 전역 솔버 인스턴스
process_tree_solver = ProcessTreeSolver() 