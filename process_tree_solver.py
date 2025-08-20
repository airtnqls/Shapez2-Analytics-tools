"""
공정 트리 솔버 - 입력 도형의 제작 공정을 트리 형태로 계산하는 모듈
"""

from typing import List, Dict, Optional, Tuple
from shape import Shape
from shape_classifier import analyze_shape, ShapeType
from corner_tracer import corner_process
from i18n import t
# claw_tracer와 같은 다른 트레이서 모듈도 필요에 따라 임포트해야 합니다.
# from claw_tracer import claw_process
# from hybrid_tracer import hybrid_process 
# from quad_cutter import quad_process


class ProcessNode:
    """공정 트리의 단일 노드를 나타내는 클래스"""
    
    def __init__(self, shape_code: str, operation: str = "", node_id: str = None, input_ids: List[str] = None):
        self.shape_code = shape_code
        self.operation = operation  # 이 노드를 만들기 위한 작업 (예: "claw", "stack", "paint" 등)
        self.node_id = node_id or f"node_{id(self)}"  # 고유 ID
        self.input_ids = input_ids or []  # 입력으로 사용된 다른 노드들의 ID
        self.shape_obj = None
        self.classification = ""  # 도형 분류 결과
        self.classification_reason = ""  # 도형 분류 사유
        
        # 도형 객체 생성 시도
        try:
            self.shape_obj = Shape.from_string(shape_code)
            # 도형 분류 수행 (분류와 사유 모두 저장)
            if self.shape_obj:
                self.classification, self.classification_reason = analyze_shape(shape_code, self.shape_obj)
                
        except Exception:
            self.shape_obj = None
    
    def is_valid(self) -> bool:
        """노드의 도형이 유효한지 확인"""
        return self.shape_obj is not None
    



def build_tree_from_data(tree_data: Dict, solver_nodes_map: Dict = None) -> Optional[ProcessNode]:
    """
    딕셔너리 형태의 트리 데이터를 ProcessNode 트리로 변환
    
    트리 데이터 형태:
    {
        "nodes": {
            "ID0": {"shape_code": "도형코드", "operation": "작업명", "input_ids": ["ID1", "ID2"]},
            "ID1": {"shape_code": "자식1_도형코드", "operation": "자식1_작업명", "input_ids": []},
            "ID2": {"shape_code": "자식2_도형코드", "operation": "자식2_작업명", "input_ids": []}
        },
        "root_id": "ID0"
    }
    
    Args:
        tree_data: 딕셔너리 형태의 트리 데이터
        solver_nodes_map: ProcessTreeSolver의 nodes_map (선택사항)
        
    Returns:
        변환된 ProcessNode 트리의 루트 노드
    """
    if not isinstance(tree_data, dict) or "nodes" not in tree_data or "root_id" not in tree_data:
        return None
    
    nodes_data = tree_data["nodes"]
    root_id = tree_data["root_id"]
    
    # 모든 노드 생성 (ID 매핑)
    nodes_map = {}
    for node_id, node_data in nodes_data.items():
        shape_code = node_data.get("shape_code", "")
        operation = node_data.get("operation", "")
        input_ids = node_data.get("input_ids", [])
        
        node = ProcessNode(shape_code, operation, node_id, input_ids)
        nodes_map[node_id] = node
        
        # solver의 nodes_map에도 추가 (제공된 경우)
        if solver_nodes_map is not None:
            solver_nodes_map[node_id] = node
    
    # 루트 노드 반환
    return nodes_map.get(root_id)





class ProcessTreeSolver:
    """공정 트리를 계산하는 솔버 클래스"""
    
    IMPOSSIBLE_OPERATION = "불가능한 도형"

    def __init__(self):
        self.max_depth = 100  # 최대 탐색 깊이
        self.nodes_map = {}  # ID별 노드 매핑
        self.next_node_id = 0  # 다음 노드 ID
    
    def _generate_node_id(self) -> str:
        """고유한 노드 ID 생성"""
        node_id = f"ID{self.next_node_id}"
        self.next_node_id += 1
        return node_id
    
    def _add_node_to_map(self, node: ProcessNode):
        """노드를 매핑에 추가"""
        if node and node.node_id:
            self.nodes_map[node.node_id] = node
    
    def create_tree_from_data(self, tree_data: Dict) -> Optional[ProcessNode]:
        """
        외부 데이터로부터 트리를 생성하는 공개 메서드
        
        Args:
            tree_data: 딕셔너리 형태의 트리 데이터
            
        Returns:
            생성된 ProcessNode 트리
        """
        # 노드 매핑 초기화
        self.nodes_map.clear()
        self.next_node_id = 0
        
        root_node = build_tree_from_data(tree_data, self.nodes_map)
        return root_node
    

    
    def _collect_all_nodes(self, node: ProcessNode, visited: set = None):
        """트리의 모든 노드를 매핑에 수집"""
        if not node or not node.node_id:
            return
        
        if visited is None:
            visited = set()
        
        if node.node_id in visited:
            return
        
        visited.add(node.node_id)
        self._add_node_to_map(node)
        
        # 자식 노드들을 찾아서 수집
        for input_id in node.input_ids:
            if input_id in self.nodes_map:
                self._collect_all_nodes(self.nodes_map[input_id], visited)
            else:
                print(f"경고: 자식 노드 {input_id}를 찾을 수 없습니다.")
    
    def tree_to_data(self, root_node: ProcessNode) -> Dict:
        """
        ProcessNode 트리를 딕셔너리 데이터로 변환
        
        Args:
            root_node: 변환할 트리의 루트 노드
            
        Returns:
            딕셔너리 형태의 트리 데이터
        """
        if not root_node:
            return {}
        
        # 모든 노드를 수집하는 함수
        def collect_nodes(node: ProcessNode, nodes_dict: Dict, visited: set):
            if not node or node.node_id in visited:
                return
            
            visited.add(node.node_id)
            
            # 현재 노드 정보 저장
            nodes_dict[node.node_id] = {
                "shape_code": node.shape_code,
                "operation": node.operation,
                "input_ids": node.input_ids
            }
            
            # 자식 노드들을 재귀적으로 수집
            for input_id in node.input_ids:
                if input_id in self.nodes_map:
                    collect_nodes(self.nodes_map[input_id], nodes_dict, visited)
        
        nodes_dict = {}
        visited = set()
        collect_nodes(root_node, nodes_dict, visited)
        
        return {
            "nodes": nodes_dict,
            "root_id": root_node.node_id
        }
    
    def solve_process_tree(self, target_shape_code: str) -> Optional[ProcessNode]:
        """
        주어진 목표 도형에 대한 공정 트리를 계산합니다.
        
        Args:
            target_shape_code: 목표 도형 코드
            
        Returns:
            ProcessNode: 공정 트리의 루트 노드, 실패시 불가능 노드 포함
        """
        # 노드 매핑 초기화 (새로운 트리 생성 시에만)
        self.nodes_map.clear()
        self.next_node_id = 0
        
        root_node = ProcessNode(target_shape_code, "목표", self._generate_node_id())
        self._add_node_to_map(root_node)
        
        try:
            # 1. 입력 도형의 유효성 검사 (Shape.from_string 성공 여부)
            target_shape_obj = Shape.from_string(target_shape_code)
            root_node.shape_obj = target_shape_obj # 루트 노드에 shape_obj 설정
            
            # 2. 도형 분석 및 재귀적 트리 생성
            self._create_simple_tree(root_node)

            return root_node
            
        except Exception as e:
            # Shape.from_string 실패 (문법 오류) 또는 기타 예외 발생 시

            # 루트 노드 자체는 유지하되, 하위에 불가능 노드 추가
            impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_child_node)
            root_node.input_ids.append(impossible_child_node.node_id)
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
    
    def _compare_first_quadrant(self, shape1: str, shape2: str) -> bool:
        """두 도형의 첫 번째 층에서 1사분면(TR 사분면)만 비교"""
        try:
            # 첫 번째 층만 추출
            layer1 = shape1.split(":")[0] if ":" in shape1 else shape1
            layer2 = shape2.split(":")[0] if ":" in shape2 else shape2
            
            # 4개씩 그룹으로 나누어 1사분면(첫 번째 그룹)만 비교
            if len(layer1) >= 4 and len(layer2) >= 4:
                q1_1 = layer1[:4]  # 첫 번째 도형의 1사분면
                q1_2 = layer2[:4]  # 두 번째 도형의 1사분면
                return q1_1 == q1_2
            
            # 길이가 4 미만인 경우 전체 비교
            return layer1 == layer2
            
        except Exception:
            return False
    
    def _create_simple_tree(self, current_node: ProcessNode, depth: int = 0):
        """
        주어진 노드의 도형을 분석하여 실제 공정 트리를 재귀적으로 생성합니다.
        도형의 종류에 따라 적절한 연산을 수행하고 하위 노드를 생성합니다.
        """
        if not current_node or not current_node.is_valid():
            current_node.operation = self.IMPOSSIBLE_OPERATION
            return

        # 깊이 제한으로 무한루프 방지
        if depth >= self.max_depth:
            current_node.operation = f"최대 깊이 도달 ({depth})"
            return

        target_shape_code = current_node.shape_code
        target_shape = current_node.shape_obj

        try:
            # 분류 정보가 없으면 다시 분석
            if not current_node.classification and target_shape:
                current_node.classification, current_node.classification_reason = analyze_shape(target_shape_code, target_shape)
                print(f"DEBUG: _create_simple_tree에서 분류 재수행 - 분류: {current_node.classification}, 사유: {current_node.classification_reason}")
            
            shape_type = current_node.classification
            
            # 도형 종류에 따른 연산 수행 및 하위 노드 생성
            self._process_shape_by_type(current_node, target_shape_code, target_shape, shape_type, depth)
            
        except Exception as e:
            # 분석 중 오류 발생 시 불가능 노드로 설정
            impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_child_node)
            current_node.input_ids = [impossible_child_node.node_id]
            current_node.operation = "분석 오류"
            
    def _process_shape_by_type(self, current_node: ProcessNode, shape_code: str, shape_obj: Shape, shape_type: str, depth: int = 0):
        """
        도형 종류에 따라 적절한 연산을 수행하고 하위 노드를 생성합니다.
        """
        # 자식이 없는 경우들 (Terminal nodes)
        if shape_type in [
            ShapeType.EMPTY.value,
            ShapeType.BASIC.value
        ]:
            current_node.operation = shape_type
            return
        elif shape_type in [ShapeType.IMPOSSIBLE.value, ShapeType.UNKNOWN.value]:
            # IMPOSSIBLE 타입은 실제 도형 코드를 유지하되 불가능 표시
            current_node.operation = self.IMPOSSIBLE_OPERATION
            # 분류 정보도 전달
            if hasattr(current_node, 'classification'):
                current_node.classification = current_node.classification
            if hasattr(current_node, 'classification_reason'):
                current_node.classification_reason = current_node.classification_reason
            
            # 불가능한 도형의 하위 노드는 물음표로 생성
            question_mark_node = ProcessNode("?", "불가능한 도형의 하위", self._generate_node_id())
            self._add_node_to_map(question_mark_node)
            current_node.input_ids = [question_mark_node.node_id]
            return
        
        # "생략" 자식 노드를 가지는 타입들
        elif shape_type in [
            ShapeType.SIMPLE_CORNER.value,
            ShapeType.STACK_CORNER.value,
            ShapeType.SIMPLE.value
        ]:
            current_node.operation = "생략"
            # "생략" 자식 노드 생성 (shape_code를 "..."으로 설정)
            skip_node = ProcessNode("...", "생략", self._generate_node_id())
            self._add_node_to_map(skip_node)
            current_node.input_ids = [skip_node.node_id]
            return
        
        # 코너 트레이서가 필요한 경우
        elif shape_type in [
            ShapeType.CLAW_CORNER.value, 
            ShapeType.SWAP_CORNER.value
        ]:
            self._apply_corner_tracer(current_node, shape_code, shape_obj, shape_type, depth)
        
        # 쿼드 연산이 필요한 경우 (깊이가 깊으면 기본 도형으로 처리)
        elif shape_type == ShapeType.SWAPABLE.value and depth < 100:
            # 깊이가 100 미만인 경우에만 쿼드 연산 적용
            self._apply_quad_operation(current_node, shape_code, shape_obj, depth)
        
        # 하이브리드 트레이서가 필요한 경우들 (깊이가 깊으면 기본 도형으로 처리)
        elif shape_type in [
            ShapeType.HYBRID.value,
            ShapeType.COMPLEX_HYBRID.value
        ]:
            if depth >= 100:  # 깊이가 100 이상이면 기본 도형으로 처리
                current_node.operation = "기본 도형 (깊이 제한)"
                return
            self._apply_hybrid_tracer(current_node, shape_code, shape_obj, depth)
            
        # 클로 트레이서가 필요한 경우 (깊이가 깊으면 기본 도형으로 처리)
        elif shape_type == ShapeType.CLAW.value:
            if depth >= 100:  # 깊이가 100 이상이면 기본 도형으로 처리
                current_node.operation = "기본 도형 (깊이 제한)"
                return
            self._apply_claw_tracer(current_node, shape_code, shape_obj, depth)

        # 클로 하이브리드 트레이서가 필요한 경우들 (깊이가 깊으면 기본 도형으로 처리)
        elif shape_type in [
            ShapeType.CLAW_HYBRID.value,
            ShapeType.CLAW_COMPLEX_HYBRID.value
        ]:
            if depth >= 100:
                current_node.operation = "기본 도형 (깊이 제한)"
                return
            self._apply_claw_hybrid_tracer(current_node, shape_code, shape_obj, depth)
        
        else:
            # 알 수 없는 타입인 경우
            current_node.operation = f"알 수 없는 타입: {shape_type}"
    
    def _apply_corner_tracer(self, current_node: ProcessNode, shape_code: str, shape_obj: Shape, shape_type: str, depth: int = 0):
        """코너 트레이서를 적용하여 하위 노드를 생성합니다."""
        try:
            from data_operations import corner_shape_for_gui
            result = corner_shape_for_gui(shape_code)
            
            if result and result != shape_code:
                # 결과가 있는 경우 자식 노드 생성
                child_node = ProcessNode(result, t("process_tree.operation.corner_result"), self._generate_node_id())
                self._add_node_to_map(child_node)
                current_node.input_ids = [child_node.node_id]
                current_node.operation = t("process_tree.operation.corner_tracer")
                # 재귀적으로 하위 트리 생성
                self._create_simple_tree(child_node, depth + 1)
            else:
                current_node.operation = t("process_tree.operation.corner_tracer_no_result")
        except Exception as e:
            # 코너 트레이서 처리 중 오류 발생
            print(f"DEBUG: corner_tracer 오류: {str(e)}")
            impossible_node = ProcessNode(shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_node)
            current_node.input_ids = [impossible_node.node_id]
            current_node.operation = t("process_tree.operation.corner_tracer_error")
    

    def _apply_quad_operation(self, current_node: ProcessNode, shape_code: str, shape_obj: Shape, depth: int = 0):
        """쿼드 연산을 적용하여 하위 노드를 생성합니다."""
        try:
            # 실제 쿼드 커터 연산 수행 (Shape.quad_cutter() 사용)
            if shape_obj:
                quad_results = shape_obj.quad_cutter()
                if quad_results and len(quad_results) == 4:
                    current_node.operation = t("process_tree.operation.quad")
                    # 4개의 사분면 결과에 대해 자식 노드 생성
                    for i, quad_shape in enumerate(quad_results):
                        if quad_shape and quad_shape.layers:
                            quad_code = repr(quad_shape)
                            child_node = ProcessNode(quad_code, t("process_tree.operation.quad_result"), self._generate_node_id())
                            self._add_node_to_map(child_node)
                            current_node.input_ids.append(child_node.node_id)
                            # 재귀적으로 하위 트리 생성
                            self._create_simple_tree(child_node, depth + 1)
                    
                    if not current_node.input_ids:
                        current_node.operation = t("process_tree.operation.quad_no_result")
                else:
                    current_node.operation = t("process_tree.operation.quad_no_result")
            else:
                current_node.operation = t("process_tree.operation.quad_no_result")
        except Exception as e:
            # 쿼드 연산 처리 중 오류 발생
            impossible_node = ProcessNode(shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_node)
            current_node.input_ids = [impossible_node.node_id]
            current_node.operation = t("process_tree.operation.quad_error")
    
    def _apply_hybrid_tracer(self, current_node: ProcessNode, shape_code: str, shape_obj: Shape, depth: int = 0):
        """하이브리드 트레이서를 적용하여 하위 노드를 생성합니다."""
        try:
            from data_operations import hybrid_shape
            results = hybrid_shape(shape_code)
            if results and len(results) == 2:
                current_node.operation = t("process_tree.operation.hybrid_tracer")
                # 두 개의 결과에 대해 자식 노드 생성
                for i, result in enumerate(results):
                    if result and result != shape_code:
                        child_node = ProcessNode(result, t("process_tree.operation.hybrid_result"), self._generate_node_id())
                        self._add_node_to_map(child_node)
                        current_node.input_ids.append(child_node.node_id)
                        # 재귀적으로 하위 트리 생성
                        self._create_simple_tree(child_node, depth + 1)
                
                if not current_node.input_ids:
                    current_node.operation = t("process_tree.operation.hybrid_no_result")
            else:
                current_node.operation = t("process_tree.operation.hybrid_no_result")
        except Exception as e:
            # 하이브리드 트레이서 처리 중 오류 발생
            impossible_node = ProcessNode(shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_node)
            current_node.input_ids = [impossible_node.node_id]
            current_node.operation = t("process_tree.operation.hybrid_error")

    def _apply_claw_hybrid_tracer(self, current_node: ProcessNode, shape_code: str, shape_obj: Shape, depth: int = 0):
        """클로 하이브리드 트레이서를 적용하여 하위 노드를 생성합니다."""
        try:
            from data_operations import claw_hybrid_shape
            results = claw_hybrid_shape(shape_code)
            if results and len(results) == 2:
                current_node.operation = t("process_tree.operation.claw_hybrid_tracer")
                for i, result in enumerate(results):
                    if result and result != shape_code:
                        child_node = ProcessNode(result, t("process_tree.operation.claw_hybrid_result"), self._generate_node_id())
                        self._add_node_to_map(child_node)
                        current_node.input_ids.append(child_node.node_id)
                        self._create_simple_tree(child_node, depth + 1)
                if not current_node.input_ids:
                    current_node.operation = t("process_tree.operation.claw_hybrid_no_result")
            else:
                current_node.operation = t("process_tree.operation.claw_hybrid_no_result")
        except Exception as e:
            impossible_node = ProcessNode(shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_node)
            current_node.input_ids = [impossible_node.node_id]
            current_node.operation = t("process_tree.operation.claw_hybrid_error")
    
    def _apply_claw_tracer(self, current_node: ProcessNode, shape_code: str, shape_obj: Shape, depth: int = 0):
        """클로 트레이서를 적용하여 하위 노드를 생성합니다."""
        try:
            from data_operations import claw_shape_for_gui
            result = claw_shape_for_gui(shape_code)
            if result and result != shape_code:
                # 결과가 있는 경우 자식 노드 생성
                child_node = ProcessNode(result, t("process_tree.operation.claw_result"), self._generate_node_id())
                self._add_node_to_map(child_node)
                current_node.input_ids = [child_node.node_id]
                current_node.operation = t("process_tree.operation.claw_tracer")
                # 재귀적으로 하위 트리 생성
                self._create_simple_tree(child_node, depth + 1)
            else:
                current_node.operation = t("process_tree.operation.claw_no_result")
        except Exception as e:
            # 클로 트레이서 처리 중 오류 발생
            print(f"DEBUG: claw_tracer 오류: {str(e)}")
            impossible_node = ProcessNode(shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_node)
            current_node.input_ids = [impossible_node.node_id]
            current_node.operation = t("process_tree.operation.claw_error")
    
    def _decompose_to_base_shapes(self, shape_code: str, shape_obj: Shape) -> List[str]:
        """도형을 기본 도형들로 분해합니다. 임시 구현입니다."""
        try:
            # 임시로 첫 번째 층의 각 사분면을 개별 도형으로 분해
            if not shape_obj or not shape_obj.layers:
                return []
            
            first_layer = shape_obj.layers[0]
            base_shapes = []
            
            for i, quadrant in enumerate(first_layer.quadrants):
                if quadrant and quadrant.shape and quadrant.color:
                    # 단일 조각으로 꽉 찬 레이어 생성 (예: Cu------ -> CuCuCuCu)
                    base_shape_str = f"{quadrant.shape}{quadrant.color}" * 4
                    if base_shape_str not in base_shapes:
                         base_shapes.append(base_shape_str)
            
            return base_shapes if base_shapes else []
            
        except Exception:
            return []
    
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
        각 노드는 가장 적절한 레벨에만 나타납니다.
        
        Args:
            root_node: 트리의 루트 노드
            
        Returns:
            List[List[ProcessNode]]: 각 레벨별 노드들의 리스트
        """
        if not root_node:
            return []
            
        # 1단계: 모든 노드의 최소 깊이 계산 (가장 가까운 루트까지의 거리)
        min_depths = {}
        self._calculate_min_depths(root_node, 0, min_depths)
        
        # 2단계: 각 노드의 최대 깊이 계산 (가장 먼 자식까지의 거리)
        max_depths = {}
        self._calculate_max_depths(root_node, 0, max_depths)
        
        # 3단계: 각 노드의 최적 레벨 결정 (최소 깊이와 최대 깊이의 평균)
        optimal_levels = {}
        for node_id in min_depths:
            min_depth = min_depths[node_id]
            max_depth = max_depths.get(node_id, min_depth)
            # 최소 깊이와 최대 깊이의 중간값을 최적 레벨로 사용
            optimal_levels[node_id] = (min_depth + max_depth) // 2
        
        # 4단계: 최적 레벨별로 노드들을 그룹화
        max_level = max(optimal_levels.values()) if optimal_levels else 0
        levels = [[] for _ in range(max_level + 1)]
        
        for node_id, level in optimal_levels.items():
            node = self.nodes_map.get(node_id)
            if node:
                levels[level].append(node)
        
        # 5단계: 각 레벨에서 중복 노드 제거
        for level in levels:
            seen_ids = set()
            unique_nodes = []
            for node in level:
                if node.node_id not in seen_ids:
                    unique_nodes.append(node)
                    seen_ids.add(node.node_id)
            level[:] = unique_nodes
        
        return levels
    
    def _calculate_min_depths(self, node: ProcessNode, current_depth: int, min_depths: Dict[str, int]):
        """각 노드의 최소 깊이를 계산합니다."""
        if not node:
            return
            
        # 이미 계산된 경우 더 깊은 깊이로 업데이트하지 않음
        if node.node_id in min_depths:
            min_depths[node.node_id] = min(min_depths[node.node_id], current_depth)
        else:
            min_depths[node.node_id] = current_depth
        
        # 자식 노드들의 최소 깊이 계산
        for input_id in node.input_ids:
            if input_id in self.nodes_map:
                child_node = self.nodes_map[input_id]
                self._calculate_min_depths(child_node, current_depth + 1, min_depths)
    
    def _calculate_max_depths(self, node: ProcessNode, current_depth: int, max_depths: Dict[str, int]):
        """각 노드의 최대 깊이를 계산합니다."""
        if not node:
            return
            
        # 이미 계산된 경우 더 얕은 깊이로 업데이트하지 않음
        if node.node_id in max_depths:
            max_depths[node.node_id] = max(max_depths[node.node_id], current_depth)
        else:
            max_depths[node.node_id] = current_depth
        
        # 자식 노드들의 최대 깊이 계산
        for input_id in node.input_ids:
            if input_id in self.nodes_map:
                child_node = self.nodes_map[input_id]
                self._calculate_max_depths(child_node, current_depth + 1, max_depths)
    
    def print_tree(self, root_node: ProcessNode, indent: int = 0):
        """디버깅용 트리 출력 함수"""
        if not root_node:
            return
            
        print("  " * indent + f"- {root_node.shape_code} ({root_node.operation}) [ID: {root_node.node_id}]")
        for input_id in root_node.input_ids:
            if input_id in self.nodes_map:
                self.print_tree(self.nodes_map[input_id], indent + 1)
    
    def get_all_nodes(self) -> Dict[str, ProcessNode]:
        """모든 노드의 ID별 매핑을 반환"""
        return self.nodes_map.copy()
    
    def get_node_by_id(self, node_id: str) -> Optional[ProcessNode]:
        """ID로 노드를 찾아 반환"""
        return self.nodes_map.get(node_id)
    
    def get_children(self, node: ProcessNode) -> List[ProcessNode]:
        """주어진 노드의 자식 노드들을 반환"""
        if not node:
            return []
        
        children = []
        for input_id in node.input_ids:
            if input_id in self.nodes_map:
                children.append(self.nodes_map[input_id])
        
        return children
    
    def _build_parent_map(self) -> Dict[str, List[str]]:
        """모든 노드에 대해 {자식 ID: [부모 ID 리스트]} 형태의 맵을 생성합니다."""
        parent_map = {}
        for node_id, node in self.nodes_map.items():
            for child_id in node.input_ids:
                if child_id not in parent_map:
                    parent_map[child_id] = []
                parent_map[child_id].append(node_id)
        return parent_map

    def _calculate_dynamic_level_heights(self, levels, node_sizes, base_gap):
        """각 레벨의 최대 노드 높이를 고려하여 동적으로 Y 좌표 계산"""
        level_y_positions = {}
        
        # 위 레벨부터 아래로 내려가면서 Y 좌표 계산
        for level_idx in range(len(levels)):
            level_nodes = levels[level_idx]
            
            if level_idx == 0:
                # 최상위 레벨은 Y=0에서 시작
                level_y_positions[level_idx] = 0
            else:
                # 현재 레벨보다 위 레벨의 최대 높이 구하기
                upper_level_idx = level_idx - 1
                upper_level_nodes = levels[upper_level_idx]
                
                # 위 레벨에서 가장 높은 노드의 높이 찾기
                max_height_above = 0
                for node in upper_level_nodes:
                    if node in node_sizes:
                        _, height = node_sizes[node]
                        max_height_above = max(max_height_above, height)
                
                # 현재 레벨의 Y 좌표 = 위 레벨 Y + (위 레벨 최대 높이 + 간격)
                current_y = level_y_positions[upper_level_idx] + max_height_above + base_gap
                level_y_positions[level_idx] = current_y
        
        return level_y_positions

    def calculate_tree_positions(self, root_node: ProcessNode, node_sizes: Dict) -> Dict[ProcessNode, Tuple[float, float]]:
        """
        '덩어리(Clump)' 기반의 계층적 레이아웃 알고리즘.
        이상적인 위치가 비슷한 노드들을 그룹화하여 대칭적으로 배치하고 겹침을 해결합니다.
        """
        if not root_node:
            return {}

        positions = {}
        parent_map = self._build_parent_map()
        levels = self.get_tree_levels(root_node)
        
        level_y_positions = self._calculate_dynamic_level_heights(levels, node_sizes, base_gap=40)

        for level_idx, level_nodes in enumerate(levels):
            y_pos = level_y_positions.get(level_idx, 0)
            
            # 1. 각 노드의 이상적인 X 위치 계산
            nodes_with_ideal_x = []
            for node in level_nodes:
                parent_ids = parent_map.get(node.node_id, [])
                positioned_parents = [self.get_node_by_id(pid) for pid in parent_ids if self.get_node_by_id(pid) in positions]
                
                if positioned_parents:
                    parent_avg_x = sum(positions[p][0] + node_sizes.get(p, (0,0))[0] / 2 for p in positioned_parents) / len(positioned_parents)
                    nodes_with_ideal_x.append((node, parent_avg_x))
                else:
                    nodes_with_ideal_x.append((node, 0))

            # 2. 이상적인 X 위치를 기준으로 노드들을 '덩어리'로 그룹화
            sorted_by_ideal_x = sorted(nodes_with_ideal_x, key=lambda item: item[1])
            clumps = []
            if sorted_by_ideal_x:
                current_clump = [sorted_by_ideal_x[0][0]]
                for i in range(len(sorted_by_ideal_x) - 1):
                    node1_data = sorted_by_ideal_x[i]
                    node2_data = sorted_by_ideal_x[i+1]
                    # 이상적인 위치가 매우 가까우면 같은 덩어리로 취급
                    if abs(node1_data[1] - node2_data[1]) < 1.0:
                        current_clump.append(node2_data[0])
                    else:
                        clumps.append(current_clump)
                        current_clump = [node2_data[0]]
                clumps.append(current_clump)

            # 3. 덩어리들을 하나의 단위로 간주하여 배치
            horizontal_gap = 0
            last_clump_edge = -float('inf')
            clump_positions = {}
            ideal_x_map = dict(nodes_with_ideal_x)
            
            for clump in clumps:
                clump_width = sum(node_sizes.get(n, (120,0))[0] for n in clump) + horizontal_gap * (len(clump) - 1)
                clump_ideal_center = sum(ideal_x_map.get(n, 0) for n in clump) / len(clump)
                
                ideal_clump_start_x = clump_ideal_center - clump_width / 2
                min_clump_start_x = last_clump_edge + horizontal_gap if last_clump_edge != -float('inf') else -float('inf')
                
                clump_start_x = max(ideal_clump_start_x, min_clump_start_x)
                clump_positions[tuple(clump)] = clump_start_x
                last_clump_edge = clump_start_x + clump_width

            # 4. 덩어리 내에서 각 노드의 위치를 최종 결정
            temp_positions = {}
            for clump in clumps:
                clump_start_x = clump_positions[tuple(clump)]
                current_x_in_clump = clump_start_x
                for node in clump:
                    temp_positions[node] = (current_x_in_clump, y_pos)
                    node_width, _ = node_sizes.get(node, (120, 0))
                    current_x_in_clump += node_width + horizontal_gap

            # 5. 레벨 전체를 화면 중앙으로 이동
            if level_nodes:
                all_nodes_in_level = [node for clump in clumps for node in clump]
                first_node_pos = temp_positions[all_nodes_in_level[0]][0]
                last_node = all_nodes_in_level[-1]
                last_node_pos = temp_positions[last_node][0]
                last_node_width = node_sizes.get(last_node, (120, 0))[0]
                
                level_width = (last_node_pos + last_node_width) - first_node_pos
                level_center_offset = -(first_node_pos + level_width / 2)

                for node in level_nodes:
                    px, py = temp_positions[node]
                    positions[node] = (px + level_center_offset, py)
        
        return positions
    
    
    def create_example_tree_data(self) -> Dict:
        """
        복잡한 예시 트리 데이터를 생성합니다.
        - 자식이 여러 부모를 가진 경우
        - 한 단계를 뛰어넘은 관계 (skipped level)
        - 복잡한 4단계 구조
        """
        example_tree_data = {
                "nodes": {
                    "ID0": {
                        "shape_code": "c---:cS--:cSSS",
                        "operation": "A",
                        "input_ids": ["ID1", "ID2"]
                    },
                    "ID1": {
                        "shape_code": "c---:cS--:c--",
                        "operation": "B",
                        "input_ids": ["ID3", "ID4"]
                    },
                    "ID2": {
                        "shape_code": "-SSS",
                        "operation": "C",
                        "input_ids": ["ID16","ID15","ID5", "ID6"]
                    }
                },
                "root_id": "ID0"
            }
        
        return example_tree_data
    



# 전역 솔버 인스턴스
process_tree_solver = ProcessTreeSolver()