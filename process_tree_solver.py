"""
공정 트리 솔버 - 입력 도형의 제작 공정을 트리 형태로 계산하는 모듈
"""

from typing import List, Dict, Optional, Tuple
from shape import Shape
from shape_analyzer import analyze_shape_simple
from claw_tracer import build_cutable_shape, build_pinable_shape


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
        현재는 임시 구현으로 가능성 검사 + claw_tracer 결과만 반환합니다.
        
        Args:
            target_shape_code: 목표 도형 코드
            
        Returns:
            ProcessNode: 공정 트리의 루트 노드, 실패시 None
        """
        try:
            # 1. 입력 도형의 유효성 검사
            target_shape = Shape.from_string(target_shape_code)
            if not target_shape:
                return None
                
            # 2. 도형 분석 - 불가능한 도형인지 확인
            analysis_result = analyze_shape_simple(target_shape_code, target_shape)
            if "불가능" in analysis_result:
                return None
                
            # 3. 임시 구현: claw_tracer 결과를 사용하여 간단한 트리 생성
            return self._create_simple_tree(target_shape_code, target_shape)
            
        except Exception as e:
            print(f"공정 트리 계산 오류: {e}")
            return None
    
    def _extract_first_layer(self, claw_result: str) -> str:
        """claw tracer 결과에서 첫 번째 층만 추출"""
        try:
            # ":"로 분리된 경우 첫 번째 부분 사용
            if ":" in claw_result:
                layers = claw_result.split(":")
                if layers:
                    return layers[0]
            return claw_result
        except Exception:
            return claw_result
    
    def _create_simple_tree(self, target_shape_code: str, target_shape: Shape) -> ProcessNode:
        """
        임시 구현: claw_tracer를 사용하여 간단한 2단계 트리를 생성합니다.
        """
        # 목표 도형을 루트 노드로 생성
        root_node = ProcessNode(target_shape_code, "목표")
        
        try:
            # claw_tracer를 사용하여 이전 단계 도형 찾기
            # 입력 도형의 첫 번째 문자에 따라 적절한 함수 선택
            if target_shape_code and target_shape_code[0] == 'P':
                claw_result = build_pinable_shape(target_shape_code)
            else:
                claw_result = build_cutable_shape(target_shape_code)
            
            if claw_result and claw_result != target_shape_code:
                # 결과에서 첫 번째 층만 추출
                previous_shape_code = self._extract_first_layer(claw_result)
                
                # claw 이전 단계 노드 생성
                previous_node = ProcessNode(previous_shape_code, "claw")
                root_node.inputs = [previous_node]
                root_node.operation = "claw 적용"
                
                # 더 간단한 기본 도형이 있는지 확인 (임시로 단순화)
                if self._is_simple_shape(previous_shape_code):
                    # 기본 도형으로 간주
                    previous_node.operation = "기본 도형"
                else:
                    # 더 복잡한 경우 추가 분해 (현재는 임시로 기본 도형으로 설정)
                    base_shape = self._get_base_shape(previous_shape_code)
                    if base_shape != previous_shape_code:
                        base_node = ProcessNode(base_shape, "기본 도형")
                        previous_node.inputs = [base_node]
                        previous_node.operation = "조합"
                        
        except Exception as e:
            print(f"claw tracer 처리 오류: {e}")
            # 실패시 단순히 목표 도형만 반환
            root_node.operation = "단일 도형"
            
        return root_node
    
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