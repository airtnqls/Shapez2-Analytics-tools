"""
공정 트리 솔버 - 입력 도형의 제작 공정을 트리 형태로 계산하는 모듈
"""

from typing import List, Dict, Optional, Tuple
from shape import Shape
from shape_classifier import analyze_shape_simple
from corner_tracer import build_cutable_shape, build_pinable_shape


class ProcessNode:
    """공정 트리의 단일 노드를 나타내는 클래스"""
    
    def __init__(self, shape_code: str, operation: str = "", node_id: str = None, input_ids: List[str] = None):
        self.shape_code = shape_code
        self.operation = operation  # 이 노드를 만들기 위한 작업 (예: "claw", "stack", "paint" 등)
        self.node_id = node_id or f"node_{id(self)}"  # 고유 ID
        self.input_ids = input_ids or []  # 입력으로 사용된 다른 노드들의 ID
        self.shape_obj = None
        
        # 도형 객체 생성 시도
        try:
            self.shape_obj = Shape.from_string(shape_code)
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
        self.max_depth = 5  # 최대 탐색 깊이
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
            
            # 2. 도형 분석 - 논리적으로 불가능한 도형인지 확인
            analysis_result = analyze_shape_simple(target_shape_code, target_shape_obj)
            if "불가능" in analysis_result:
                # 도형 코드 자체는 유효하지만, 논리적으로 불가능한 도형인 경우
                # 루트 노드 아래에 불가능한 자식 노드를 추가
                impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
                self._add_node_to_map(impossible_child_node)
                root_node.input_ids.append(impossible_child_node.node_id)
                root_node.operation = "불가능"
                return root_node
                
            # 3. 임시 구현: claw_tracer 결과를 사용하여 간단한 트리 생성
            # _create_simple_tree가 반환하는 서브트리를 루트의 자식으로 추가
            simple_tree_root = self._create_simple_tree(target_shape_code, target_shape_obj)
            # _create_simple_tree는 이제 자식 노드만 반환 (또는 루트와 자식 포함된 서브트리)
            # 여기서는 simple_tree_root의 자식들을 가져와서 현재 root_node의 자식으로 설정
            # 그리고 simple_tree_root의 operation을 현재 root_node의 operation으로 설정
            if simple_tree_root:
                root_node.input_ids.extend(simple_tree_root.input_ids)
                if simple_tree_root.operation != "목표": # 목표가 아니면 업데이트
                    root_node.operation = simple_tree_root.operation
                
                # simple_tree_root의 모든 노드들을 nodes_map에 추가
                self._collect_all_nodes(simple_tree_root)
            else:
                # _create_simple_tree가 None을 반환하는 경우 (오류 처리)
                impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
                self._add_node_to_map(impossible_child_node)
                root_node.input_ids.append(impossible_child_node.node_id)
                root_node.operation = "생성 오류"

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
    
    def _create_simple_tree(self, target_shape_code: str, target_shape: Shape) -> ProcessNode:
        """
        임시 구현: corner_tracer를 사용하여 간단한 2단계 트리를 생성합니다.
        이 함수는 목표 도형에 대한 공정 서브트리의 루트 노드를 반환합니다.
        """
        # 여기서 생성되는 루트 노드는 solve_process_tree에서 최종 루트의 자식으로 연결될 것임.
        # 따라서 target_shape_code에 대한 중간 단계의 루트 노드로 생각.
        current_node_for_tracing = ProcessNode(target_shape_code, "코너추적대상", self._generate_node_id())
        current_node_for_tracing.shape_obj = target_shape # shape_obj도 설정
        
        # 현재 노드를 nodes_map에 추가
        self._add_node_to_map(current_node_for_tracing)
        

        
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
                    previous_node = ProcessNode(previous_shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
                else:
                    previous_node = ProcessNode(previous_shape_code, "corner", self._generate_node_id())
                
                # 노드를 nodes_map에 추가
                self._add_node_to_map(previous_node)

                
                current_node_for_tracing.input_ids = [previous_node.node_id]
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
                            base_node = ProcessNode(base_shape, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
                        else:
                            base_node = ProcessNode(base_shape, "기본 도형", self._generate_node_id())
                        
                        # 기본 노드도 nodes_map에 추가
                        self._add_node_to_map(base_node)
                        
                        previous_node.input_ids = [base_node.node_id]
                        previous_node.operation = "조합"
                        
        except Exception as e:
            # corner tracer 처리 중 오류가 발생하면, 하위 노드를 불가능 노드로 설정
            # 루트 노드 자체는 유지하되, 하위에 불가능 노드 추가
            impossible_child_node = ProcessNode(target_shape_code, self.IMPOSSIBLE_OPERATION, self._generate_node_id())
            self._add_node_to_map(impossible_child_node)
            current_node_for_tracing.input_ids = [impossible_child_node.node_id]
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
        
        level_y_positions = self._calculate_dynamic_level_heights(levels, node_sizes, base_gap=80)

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
            horizontal_gap = 40
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
                        "shape_code": "CuCuCuCu:RrRrRrRr:CcCcCcCc:P-P-P-P-",
                        "operation": "최종목표",
                        "input_ids": ["ID1", "ID2"]
                    },
                    "ID1": {
                        "shape_code": "CuCuCuCu:RrRrRrRr:CcCcCcCc",
                        "operation": "2차조합",
                        "input_ids": ["ID3", "ID4"]
                    },
                    "ID2": {
                        "shape_code": "P-P-P-P-:Cu------:Rr------",
                        "operation": "2차조합",
                        "input_ids": ["ID16","ID15","ID5", "ID6"]
                    },
                    "ID3": {
                        "shape_code": "CuCuCuCu:RrRrRrRr",
                        "operation": "1차가공",
                        "input_ids": ["ID7", "ID8"]
                    },
                    "ID4": {
                        "shape_code": "CcCcCcCc:SuSuSuSu",
                        "operation": "1차가공",
                        "input_ids": ["ID8", "ID10"]
                    },
                    "ID5": {
                        "shape_code": "P-P-P-P-:Cu------",
                        "operation": "1차가공",
                        "input_ids": []
                    },
                    "ID15": {
                        "shape_code": "P-P-P-P-:Cu------",
                        "operation": "1차가공",
                        "input_ids": []
                    },
                    "ID16": {
                        "shape_code": "P-P-P-P-:Cu------",
                        "operation": "1차가공",
                        "input_ids": []
                    },
                    "ID6": {
                        "shape_code": "Rr------:CcCcCcCc",
                        "operation": "1차가공",
                        "input_ids": ["ID13", "ID9"]  # ID9 재사용 (자식이 두 부모를 가짐)
                    },
                    "ID7": {"shape_code": "CuCuCuCu", "operation": "원료", "input_ids": []},
                    "ID8": {"shape_code": "RrRrRrRr", "operation": "원료", "input_ids": []},
                    "ID9": {"shape_code": "CcCcCcCr", "operation": "원료", "input_ids": []},
                    "ID10": {"shape_code": "SwSwSySy", "operation": "원료", "input_ids": ["ID14"]},
                    "ID13": {"shape_code": "Rr------", "operation": "원료", "input_ids": []},
                    "ID14": {"shape_code": "Rr------", "operation": "원료", "input_ids": []}
                },
                "root_id": "ID0"
            }
        
        return example_tree_data
    



# 전역 솔버 인스턴스
process_tree_solver = ProcessTreeSolver() 