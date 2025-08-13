from __future__ import annotations
import sys
import json
from typing import List, Tuple, Optional, Set
from PyQt6.QtCore import QThread, pyqtSignal
import itertools
from shape_classifier import analyze_shape

# ==============================================================================
#  1. Shapez 2 시뮬레이터 백엔드
# ==============================================================================
class Quadrant:
    VALID_SHAPES = ['C', 'S', 'R', 'W', 'c', 'P']; VALID_COLORS = ['r', 'g', 'b', 'm', 'c', 'y', 'u', 'w']
    def __init__(self, shape: str, color: str):
        if shape not in self.VALID_SHAPES: raise ValueError(f"잘못된 모양: {shape}")
        if color not in self.VALID_COLORS: raise ValueError(f"잘못된 색상: {color}")
        if shape == 'P' and color != 'u': raise ValueError("핀('P')은 색상이 없을 수만 있습니다('u').")
        self.shape = shape; self.color = color
    def __repr__(self) -> str: return f"{self.shape}{self.color if self.shape != 'P' else '-'}"
    def copy(self): return Quadrant(self.shape, self.color)

class Layer:
    def __init__(self, quadrants: List[Optional[Quadrant]]):
        if len(quadrants) != 4: raise ValueError("레이어는 4개의 사분면을 가져야 합니다.")
        self.quadrants = quadrants
    def __repr__(self) -> str:
        q = self.quadrants; output_order = [q[0], q[1], q[2], q[3]] # TR, BR, BL, TL
        return "".join(repr(p) if p else '--' for p in output_order)
    def is_empty(self) -> bool: return all(q is None for q in self.quadrants)
    def copy(self): return Layer([q.copy() if q else None for q in self.quadrants])

class Shape:
    MAX_LAYERS = 5  # 기본 최대 층 수
    
    def __init__(self, layers_or_code):
        if isinstance(layers_or_code, str):
            # 문자열 입력 시 from_string 사용
            obj = Shape.from_string(layers_or_code)
            self.layers = obj.layers
            self.max_layers = obj.max_layers
        elif isinstance(layers_or_code, list):
            self.layers = layers_or_code
            # 개별 도형의 최대 층 수 설정 (기본값 또는 레이어 수 중 큰 값)
            self.max_layers = max(Shape.MAX_LAYERS, len(layers_or_code))
        else:
            raise ValueError("Shape 초기화는 레이어 리스트 또는 문자열만 허용됩니다.")

    def classifier(self) -> tuple[str, str]:
        # 각 레이어를 4개의 도형 문자로 변환 (색상 생략)
        result = []
        for layer in self.layers:
            # 출력 순서: [0, 1, 2, 3] (TR, BR, BL, TL) - 새로운 인덱스 매핑
            output_order = [layer.quadrants[0], layer.quadrants[1], layer.quadrants[2], layer.quadrants[3]]
            layer_str = ""
            for quad in output_order:
                if quad is None:
                    layer_str += "-"
                elif quad.shape in ['C', 'S', 'R', 'W']:
                    layer_str += "S"
                elif quad.shape == 'c':
                    layer_str += "c"
                elif quad.shape == 'P':
                    layer_str += "P"
                else:
                    layer_str += "-"
            result.append(layer_str)
        
        # 리스트를 콜론으로 구분된 문자열로 변환
        shape_string = ":".join(result)
        return analyze_shape(shape_string, self)

    @classmethod
    def from_string(cls, code: str) -> Shape:
        # 입력 코드에 중괄호가 포함되어 있는지 확인하고, 그렇다면 그 사이의 텍스트를 추출합니다.
        if '{' in code and '}' in code:
            start_index = code.find('{')
            end_index = code.find('}', start_index)
            if start_index != -1 and end_index != -1 and end_index > start_index:
                code = code[start_index + 1:end_index].strip()

        if not code: return Shape([])
        
        # 콜론이 없고 5글자 이상인 경우, 색상코드가 없을 때만 각 글자를 콜론으로 구분하여 처리
        if ':' not in code and len(code) >= 5:
            # 색상코드 확인 (u r b g y m c w)
            color_codes = set('urbgymw')
            has_color_code = any(char in color_codes for char in code)
            
            # P와 -로만 구성되고 8글자이며 짝수번째가 전부 -인 경우는 콜론으로 구분하지 않음
            is_p_dash_pattern = (len(code) == 8 and 
                               set(code) <= {'P', '-'} and 
                               all(code[i] == '-' for i in range(1, 8, 2)))
            
            if not has_color_code and not is_p_dash_pattern:
                code = ':'.join(code)
                # 디버그용 출력 (상세 로그에서만 표시)
        
        def expand_short_code(short_code):
            """4글자 이하 코드를 8글자 코드로 확장"""
            if len(short_code) <= 4:
                # 4글자 이하면 각 글자를 도형으로 처리
                expanded = ""
                for i in range(4):
                    if i < len(short_code):
                        char = short_code[i]
                        if char == 'S':
                            expanded += "Su"  # S는 Cu로 변환
                        elif char.islower() and char == 'c':
                            expanded += char + "w"  # c는 해당 도형 + w 색상
                        elif char == 'P':
                            expanded += "P-"  # P는 P-로 변환
                        elif char == '-':
                            expanded += "--"  # -는 --로 변환
                        else:
                            expanded += char + "u"  # 기본은 u 색상
                    else:
                        expanded += "--"  # 부족한 부분은 --로 채움
                return expanded
            else:
                return short_code  # 8글자면 그대로 사용
        
        def parse_part(part_str):
            s, c = part_str[0], part_str[1]
            if s == '-': return None
            return Quadrant(s, 'u' if s == 'P' else c)
            
        # 콜론으로 분리하여 레이어 개수 확인
        layer_codes = code.split(':')
        required_layers = len(layer_codes)
        
        layers = []
        for l_code in layer_codes:
            # 짧은 코드를 8글자로 확장
            expanded_code = expand_short_code(l_code)
            parts_str = [expanded_code[i:i+2] for i in range(0, 8, 2)]
            quads = [None] * 4
            # 새로운 인덱스 매핑: 0=TR, 1=BR, 2=BL, 3=TL
            quads[0] = parse_part(parts_str[0])  # TR
            quads[1] = parse_part(parts_str[1])  # BR
            quads[2] = parse_part(parts_str[2])  # BL
            quads[3] = parse_part(parts_str[3])  # TL
            layers.append(Layer(quads))
        
        # 새로운 Shape 객체 생성
        shape = cls(layers)
        # 개별 도형의 최대 층 수 설정 (기본값 또는 필요한 레이어 수 중 큰 값)
        shape.max_layers = max(cls.MAX_LAYERS, required_layers)
        return shape

    def copy(self): 
        copied_shape = Shape([layer.copy() for layer in self.layers])
        copied_shape.max_layers = self.max_layers
        return copied_shape

    def pad_layers(self, num_layers: int):
        """지정된 수의 레이어가 있도록 도형을 확장합니다."""
        while len(self.layers) < num_layers:
            self.layers.append(Layer.from_string("----"))

    def __repr__(self) -> str:
        s = self.copy()
        while len(s.layers) > 0 and s.layers[-1].is_empty():
            s.layers.pop()
        if not s.layers: return ""
        return ":".join(repr(layer) for layer in s.layers)

    # --------------------------------------------------------------
    # 패턴 포함 매칭 (옵션: 와일드카드 마스크)
    def contains_pattern(self, pattern: "Shape", wildcard_mask: Optional[list[list[bool]]] = None, treat_empty_as_wildcard: bool = False) -> bool:
        """자신(self) 안에 pattern 도형이 포함되는지 검사합니다.
        - 포함 매칭 (연속 레이어 중 어느 위치든 매칭되면 True)
        - wildcard_mask가 주어지면 True인 사분면은 어떤 도형이든 허용
        - treat_empty_as_wildcard=True이면 패턴의 빈칸(None/"--")도 와일드카드로 허용
        """
        if not isinstance(pattern, Shape):
            return False
        if not pattern.layers:
            return True
        if not self.layers:
            return False

        self_layers = self.layers
        pat_layers = pattern.layers
        if len(self_layers) < len(pat_layers):
            return False

        def layer_match(self_layer: Layer, pat_layer: Layer, mask_for_layer: Optional[list[bool]]) -> bool:
            for q in range(4):
                if mask_for_layer is not None and q < len(mask_for_layer) and mask_for_layer[q]:
                    # 와일드카드: 어떤 값이든 허용
                    continue
                sp = self_layer.quadrants[q]
                pp = pat_layer.quadrants[q]
                if pp is None:
                    if treat_empty_as_wildcard:
                        continue
                    # 패턴이 빈칸인데 와일드카드가 아니면 self도 비어있어야 함
                    if sp is not None:
                        return False
                else:
                    if sp is None:
                        return False
                    # 모양, 색상 모두 일치 필요
                    if sp.shape != pp.shape or sp.color != pp.color:
                        return False
            return True

        max_start = len(self_layers) - len(pat_layers)
        for start in range(max_start + 1):
            ok = True
            for i in range(len(pat_layers)):
                mask_for_layer = None
                if wildcard_mask is not None and i < len(wildcard_mask):
                    mask_for_layer = wildcard_mask[i]
                if not layer_match(self_layers[start + i], pat_layers[i], mask_for_layer):
                    ok = False
                    break
            if ok:
                return True
        return False

    @classmethod
    def parse_pattern_with_wildcard(cls, code: str, wildcard_char: str = '_') -> tuple["Shape", list[list[bool]]]:
        """패턴 문자열을 파싱하여 (도형, 와일드카드마스크)를 반환합니다.
        - wildcard_char 위치는 True로 마크됩니다.
        - '-'는 빈칸으로 처리되며 와일드카드가 아닙니다.
        - 내부 도형 파싱은 '_'를 '-'로 치환한 문자열을 사용합니다.
        """
        # 중괄호 영역 처리 (from_string과 동일)
        if '{' in code and '}' in code:
            start_index = code.find('{')
            end_index = code.find('}', start_index)
            if start_index != -1 and end_index != -1 and end_index > start_index:
                code = code[start_index + 1:end_index].strip()

        original = code
        if not original:
            return Shape([]), []

        # 콜론 자동 삽입 규칙 (from_string과 같은 기준)
        colonized = original
        if ':' not in original and len(original) >= 5:
            color_codes = set('urbgymw')
            has_color_code = any(char in color_codes for char in original)
            is_p_dash_pattern = (len(original) == 8 and set(original) <= {'P', '-'} and all(original[i] == '-' for i in range(1, 8, 2)))
            if not has_color_code and not is_p_dash_pattern:
                colonized = ':'.join(original)

        layer_codes = colonized.split(':')
        wildcard_mask: list[list[bool]] = []

        def layer_wildcards_and_norm(l_code: str) -> tuple[list[bool], str]:
            # 반환: (와일드카드[4], 8글자 정규화 코드)
            if len(l_code) <= 4:
                mask = []
                expanded = ""
                for i in range(4):
                    if i < len(l_code):
                        ch = l_code[i]
                        mask.append(ch == wildcard_char)
                        # 확장 로직은 from_string과 동일하게 근사
                        if ch == 'S':
                            expanded += "Su"
                        elif ch.islower() and ch == 'c':
                            expanded += ch + "w"
                        elif ch == 'P':
                            expanded += "P-"
                        elif ch == '-':
                            expanded += "--"
                        elif ch == wildcard_char:
                            expanded += "--"  # 파서 용도로 빈칸으로 대체
                        else:
                            expanded += ch + "u"
                    else:
                        mask.append(False)
                        expanded += "--"
                return mask, expanded
            else:
                # 8글자 페어 코드로 간주
                # 부족하면 '-'로 채움
                padded = (l_code + ("-" * 8))[:8]
                mask = []
                for i in range(0, 8, 2):
                    ch0 = padded[i]
                    ch1 = padded[i+1]
                    mask.append(ch0 == wildcard_char or ch1 == wildcard_char)
                # 파서용으로 '_'를 '-'로 치환
                normalized = padded.replace(wildcard_char, '-')
                return mask, normalized

        normalized_layers = []
        for l_code in layer_codes:
            mask, norm8 = layer_wildcards_and_norm(l_code)
            wildcard_mask.append(mask)
            normalized_layers.append(norm8)

        normalized_code = ":".join(normalized_layers)
        shape = Shape.from_string(normalized_code)
        return shape, wildcard_mask

    def _get_piece(self, l: int, q: int) -> Optional[Quadrant]:
        return self.layers[l].quadrants[q] if 0 <= l < len(self.layers) and 0 <= q < 4 else None

    def _is_adjacent(self, q1: int, q2: int) -> bool:
        if q1 == q2: return False
        # 새로운 인덱스 매핑: 0=TR(0,1), 1=BR(1,1), 2=BL(1,0), 3=TL(0,0)
        positions = {0: (0, 1), 1: (1, 1), 2: (1, 0), 3: (0, 0)}
        r1, c1 = positions[q1]
        r2, c2 = positions[q2]
        return abs(r1 - r2) + abs(c1 - c2) == 1

    def _find_connected_group(self, start_l: int, start_q: int) -> Set[Tuple[int, int]]:
        start_piece = self._get_piece(start_l, start_q)
        if not start_piece:
            return set()

        if start_piece.shape == 'P':
            return {(start_l, start_q)}

        is_crystal_group = start_piece.shape == 'c'
        q_bfs, visited, group = [(start_l, start_q)], set(), set()
        
        while q_bfs:
            l, q = q_bfs.pop(0)
            if (l, q) in visited:
                continue
            visited.add((l, q))
            group.add((l, q))
            
            for nq in range(4):
                if self._is_adjacent(q, nq):
                    if (neighbor := self._get_piece(l, nq)):
                        if (is_crystal_group and neighbor.shape == 'c') or \
                           (not is_crystal_group and neighbor.shape not in ['c', 'P']):
                            q_bfs.append((l, nq))

            if is_crystal_group:
                for dl in [-1, 1]:
                    if (neighbor := self._get_piece(l + dl, q)) and neighbor.shape == 'c':
                        q_bfs.append((l + dl, q))
        return group
    
    def _calculate_shatter_set(self, initial_destroyed: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        total_shattered = set(initial_destroyed)
        q_propagate = {coord for coord in initial_destroyed if (p := self._get_piece(*coord)) and p.shape == 'c'}

        while q_propagate:
            l, q = q_propagate.pop()
            
            crystal_group = self._find_connected_group(l, q)
            newly_shattered = crystal_group - total_shattered
            if not newly_shattered: continue
            
            total_shattered.update(newly_shattered)
            
            for sl, sq in newly_shattered:
                for dl in [-1, 1]:
                    neighbor_coord = (sl + dl, sq)
                    if (p := self._get_piece(*neighbor_coord)) and p.shape == 'c' and neighbor_coord not in total_shattered:
                        q_propagate.add(neighbor_coord)
                for nq in range(4):
                    if self._is_adjacent(sq, nq):
                        neighbor_coord = (sl, nq)
                        if (p := self._get_piece(*neighbor_coord)) and p.shape == 'c' and neighbor_coord not in total_shattered:
                           q_propagate.add(neighbor_coord)
        return total_shattered

    def apply_physics(self, debug=False) -> Shape | tuple[Shape, str]:
        s = self.copy()
        if not s.layers:
            return (s, "디버그: 빈 모양") if debug else s

        debug_log = []

        while True:
            supported = set()
            for q in range(4):
                if s._get_piece(0, q): supported.add((0, q))

            while True: 
                num_supported_before = len(supported)
                visited_groups = set()
                for l_start in range(len(s.layers)):
                    for q_start in range(4):
                        coord = (l_start, q_start)
                        if coord not in visited_groups and s._get_piece(*coord):
                            group = s._find_connected_group(l_start, q_start)
                            if any(c in supported for c in group):
                                supported.update(group)
                            visited_groups.update(group)
                for l in range(len(s.layers)):
                    for q in range(4):
                        coord = (l, q)
                        if coord in supported or not s._get_piece(*coord): continue
                        piece = s._get_piece(l, q)
                        if l > 0 and (l - 1, q) in supported:
                            supported.add(coord)
                        elif piece and piece.shape != 'P':
                            for nq in range(4):
                                if self._is_adjacent(q, nq):
                                    neighbor_coord = (l, nq)
                                    if neighbor_coord in supported:
                                        supporter = s._get_piece(*neighbor_coord)
                                        if supporter and supporter.shape != 'P':
                                            supported.add(coord); break
                if len(supported) == num_supported_before: break

            all_coords = {(l, q) for l in range(len(s.layers)) for q in range(4) if s._get_piece(l, q)}
            unsupported_coords = all_coords - supported

            if debug:
                debug_log.append(f"--- 물리 스텝 (현재: {repr(s)}) ---")
                debug_log.append(f"1. 지지됨: {sorted(list(supported))}")
                debug_log.append(f"2. 불안정: {sorted(list(unsupported_coords))}")

            falling_crystals = {c for c in unsupported_coords if (p := s._get_piece(*c)) and p.shape == 'c'}
            if falling_crystals:
                shattered_coords = s._calculate_shatter_set(falling_crystals)
                for l, q in shattered_coords:
                    if 0 <= l < len(s.layers): s.layers[l].quadrants[q] = None
                if debug: debug_log.append(f"3. 크리스탈 파괴됨: {sorted(list(shattered_coords))}")
                continue 

            if not unsupported_coords:
                if debug: debug_log.append("상태 안정됨, 루프 종료.")
                break 

            moved_in_this_tick = False
            
            falling_groups = []
            visited_fallers = set()
            for l, q in sorted(list(unsupported_coords), key=lambda x: -x[0]):
                if (l, q) not in visited_fallers:
                    full_group = s._find_connected_group(l, q)
                    falling_group = {coord for coord in full_group if coord in unsupported_coords}
                    if falling_group:
                        falling_groups.append(falling_group)
                        visited_fallers.update(falling_group)
            
            if debug: debug_log.append(f"3. 낙하 그룹: {[sorted(list(g)) for g in falling_groups]}")

            for group in falling_groups:
                # 이 그룹이 한 번에 얼마나 멀리 떨어질 수 있는지 계산합니다.
                fall_distance = 0
                can_fall_further = True
                while can_fall_further:
                    next_fall_dist = fall_distance + 1
                    for l, q in group:
                        target_l = l - next_fall_dist
                        if target_l < 0:  # 바닥에 닿음
                            can_fall_further = False
                            break
                        
                        # 아래에 다른 조각이 있는지 확인 (같은 낙하 그룹에 속한 조각은 제외)
                        piece_below = s._get_piece(target_l, q)
                        if piece_below and (target_l, q) not in group:
                            can_fall_further = False
                            break
                    
                    if can_fall_further:
                        fall_distance += 1
                    else:
                        break

                if fall_distance > 0:
                    moved_in_this_tick = True
                    # 조각을 덮어쓰지 않도록 위에서부터 정렬
                    group_pieces = sorted([(l, q, s._get_piece(l, q)) for l, q in group], key=lambda x: -x[0])
                    
                    # 그룹의 모든 조각을 원래 위치에서 제거
                    for l_old, q_old, _ in group_pieces:
                        if 0 <= l_old < len(s.layers):
                            s.layers[l_old].quadrants[q_old] = None
                    
                    # 그룹의 모든 조각을 새로운 위치에 배치
                    for l_old, q_old, piece in group_pieces:
                        new_l = l_old - fall_distance
                        if 0 <= new_l < len(s.layers):
                            s.layers[new_l].quadrants[q_old] = piece

            if not moved_in_this_tick:
                if debug: debug_log.append("움직임 없음, 안정화 완료.")
                break
            elif debug:
                debug_log.append("그룹 이동 발생, 다음 스텝으로.")
        
        while len(s.layers) > 0 and s.layers[-1].is_empty():
            s.layers.pop()
            
        return (s, "\n".join(debug_log)) if debug else s

    def destroy_half(self) -> Shape:
        s_initial = self.apply_physics()
        # 새로운 인덱스 매핑에서 서쪽 절반: 2=BL, 3=TL
        initial_destroyed = {(l, q) for l in range(len(s_initial.layers)) for q in [2, 3] if s_initial._get_piece(l, q)}
        
        all_to_destroy = s_initial._calculate_shatter_set(initial_destroyed)
        
        s_after = s_initial.copy()
        for l, q in all_to_destroy:
            if 0 <= l < len(s_after.layers):
                s_after.layers[l].quadrants[q] = None
        
        return s_after.apply_physics()
    
    def simple_cutter(self) -> tuple[Shape, Shape]:
        """도형을 서쪽 절반(2,3사분면)과 동쪽 절반(0,1사분면)으로 나눕니다. 물리를 적용하지 않습니다."""
        # 서쪽 절반 (2=BL, 3=TL 사분면)
        west_layers = []
        for layer in self.layers:
            west_quadrants = [None, None, layer.quadrants[2], layer.quadrants[3]]
            west_layers.append(Layer(west_quadrants))
        west_shape = Shape(west_layers)
        west_shape.max_layers = self.max_layers
        
        # 동쪽 절반 (0=BR, 1=TR 사분면)
        east_layers = []
        for layer in self.layers:
            east_quadrants = [layer.quadrants[0], layer.quadrants[1], None, None]
            east_layers.append(Layer(east_quadrants))
        east_shape = Shape(east_layers)
        east_shape.max_layers = self.max_layers
        
        return west_shape, east_shape
    
    def quad_cutter(self) -> tuple[Shape, Shape, Shape, Shape]:
        """도형을 4개의 사분면으로 나누고 각각을 기둥 형태로 출력합니다. 물리를 적용하지 않습니다."""
        # 1사분면 (TR) - 회전 없음
        quad1_layers = []
        for layer in self.layers:
            quad1_quadrants = [layer.quadrants[0], None, None, None]
            quad1_layers.append(Layer(quad1_quadrants))
        quad1_shape = Shape(quad1_layers)
        quad1_shape.max_layers = self.max_layers
        
        # 2사분면 (BR) - 270도 회전 (반시계방향)
        quad2_layers = []
        for layer in self.layers:
            quad2_quadrants = [None, layer.quadrants[1], None, None]
            quad2_layers.append(Layer(quad2_quadrants))
        quad2_shape = Shape(quad2_layers)
        quad2_shape.max_layers = self.max_layers
        quad2_shape = quad2_shape.rotate(clockwise=False)
        # 3사분면 (BL) - 180도 회전 (시계방향 2번)
        quad3_layers = []
        for layer in self.layers:
            quad3_quadrants = [None, None, layer.quadrants[2], None]
            quad3_layers.append(Layer(quad3_quadrants))
        quad3_shape = Shape(quad3_layers)
        quad3_shape.max_layers = self.max_layers
        quad3_shape = quad3_shape.rotate_180()
        
        # 4사분면 (TL) - 90도 회전 (시계방향)
        quad4_layers = []
        for layer in self.layers:
            quad4_quadrants = [None, None, None, layer.quadrants[3]]
            quad4_layers.append(Layer(quad4_quadrants))
        quad4_shape = Shape(quad4_layers)
        quad4_shape.max_layers = self.max_layers
        quad4_shape = quad4_shape.rotate(clockwise=True)
        
        return quad1_shape, quad2_shape, quad3_shape, quad4_shape
    
    def half_cutter(self) -> tuple[Shape, Shape]:
        """도형을 서쪽 절반(2,3사분면)과 동쪽 절반(0,1사분면)으로 나누고 물리를 적용합니다."""
        s_initial = self.apply_physics()
        
        # 서쪽 절반 (2=BL, 3=TL 사분면)
        west_layers = []
        for layer in s_initial.layers:
            west_quadrants = [None, None, layer.quadrants[2], layer.quadrants[3]]
            west_layers.append(Layer(west_quadrants))
        west_shape = Shape(west_layers)
        west_shape.max_layers = self.max_layers
        
        # 동쪽 절반 (0=TR, 1=BR 사분면)
        east_layers = []
        for layer in s_initial.layers:
            east_quadrants = [layer.quadrants[0], layer.quadrants[1], None, None]
            east_layers.append(Layer(east_quadrants))
        east_shape = Shape(east_layers)
        east_shape.max_layers = self.max_layers
        
        # 각각 물리 적용
        return west_shape.apply_physics(), east_shape.apply_physics()

    def push_pin(self) -> Shape:
        s_initial = self.copy()
        if not s_initial.layers or s_initial.layers[0].is_empty():
            return s_initial

        pin_layer_quads = [Quadrant('P', 'u') if quad else None for quad in s_initial.layers[0].quadrants]
        
        # 핀 레이어를 추가하여 잠재적으로 초과 크기 모양을 만듭니다.
        s_oversized = Shape([Layer(pin_layer_quads)] + [l.copy() for l in s_initial.layers])
        # 초과 크기 모양의 max_layers를 원본과 동일하게 설정
        s_oversized.max_layers = self.max_layers

        initial_destroyed = set()
        # 모양이 최대 크기를 초과하면, 최대층을 초과하는 모든 레이어의 조각들이 파괴의 시작점이 됩니다.
        if len(s_oversized.layers) > self.max_layers:
            # 최대층을 초과하는 모든 레이어의 조각들을 파괴 대상으로 설정
            for layer_idx in range(self.max_layers, len(s_oversized.layers)):
                for q in range(4):
                    if s_oversized._get_piece(layer_idx, q) is not None:
                        initial_destroyed.add((layer_idx, q))

        # 이 '초과 크기' 모양을 기준으로 전체 파괴 세트를 계산합니다.
        all_to_destroy = s_oversized._calculate_shatter_set(initial_destroyed)
        
        # 파괴를 적용합니다.
        for l, q in all_to_destroy:
            if 0 <= l < len(s_oversized.layers):
                s_oversized.layers[l].quadrants[q] = None
        
        # 최종 모양은 최대 레이어 수에 맞게 잘라냅니다.
        s_final = Shape(s_oversized.layers[:self.max_layers])
        s_final.max_layers = self.max_layers
                
        return s_final.apply_physics()

    def crystal_generator(self, color_str: str) -> Shape:
        s = self.copy()
        if not s.layers:
            s.layers.append(Layer([None,None,None,None]))
        for layer in s.layers:
            for i in range(4):
                if layer.quadrants[i] is None or layer.quadrants[i].shape == 'P':
                    layer.quadrants[i] = Quadrant('c', color_str)
        return s.apply_physics()
    
    def rotate(self, clockwise: bool = True) -> Shape:
        s = self.copy()
        if not s.layers: return s
        for layer in s.layers: 
            q = layer.quadrants
            # 새로운 인덱스 매핑: 0=TR, 1=BR, 2=BL, 3=TL
            # 시계방향: TR→BR→BL→TL→TR (0→1→2→3→0)
            # 반시계방향: TR→TL→BL→BR→TR (0→3→2→1→0)
            layer.quadrants = [q[3], q[0], q[1], q[2]] if clockwise else [q[1], q[2], q[3], q[0]]
        return s #.apply_physics()
    
    def mirror(self) -> Shape:
        """1234 분면을 1432 분면으로 재배치 (좌우 대칭)"""
        s = self.copy()
        if not s.layers: return s
        for layer in s.layers:
            q = layer.quadrants
            # 새로운 인덱스 매핑: 0=TR, 1=BR, 2=BL, 3=TL
            # 1234 → 1432: 0→0, 1→3, 2→2, 3→1
            layer.quadrants = [q[0], q[3], q[2], q[1]]
        return s
    
    def rotate_180(self) -> Shape:
        """180도 회전 (시계방향 2번)"""
        return self.rotate(True).rotate(True)
    
    @staticmethod
    def stack(bottom: Shape, top: Shape) -> Shape:
        stable_bottom = bottom.apply_physics()
        stable_top = top.apply_physics()

        # 두 도형 중 높은 층을 기준으로 설정
        result_max_layers = max(bottom.max_layers, top.max_layers)

        top_processed = stable_top.copy()
        for layer in top_processed.layers:
            for i, q in enumerate(layer.quadrants):
                if q and q.shape == 'c':
                    layer.quadrants[i] = None
        
        combined_layers = stable_bottom.layers + top_processed.layers
        
        oversized_shape = Shape(combined_layers)
        oversized_shape.max_layers = result_max_layers

        stable_oversized_shape = oversized_shape.apply_physics()
        
        if len(stable_oversized_shape.layers) > result_max_layers:
            stable_oversized_shape.layers = stable_oversized_shape.layers[:result_max_layers]
        
        while len(stable_oversized_shape.layers) > 0 and stable_oversized_shape.layers[-1].is_empty():
            stable_oversized_shape.layers.pop()

        # 결과 도형의 max_layers 설정
        stable_oversized_shape.max_layers = result_max_layers
        return stable_oversized_shape

    @staticmethod
    def _merge_halves(left: Shape, right: Shape) -> Shape:
        max_layers = max(len(left.layers), len(right.layers))
        if max_layers == 0:
            return Shape([])
            
        # 두 도형 중 높은 층을 기준으로 설정
        result_max_layers = max(left.max_layers, right.max_layers)
        
        new_layers = [Layer([None] * 4) for _ in range(max_layers)]
        
        for i in range(max_layers):
            if i < len(left.layers):
                # 새로운 인덱스 매핑에서 서쪽 절반: 2=BL, 3=TL
                if left.layers[i].quadrants[2]: new_layers[i].quadrants[2] = left.layers[i].quadrants[2].copy()
                if left.layers[i].quadrants[3]: new_layers[i].quadrants[3] = left.layers[i].quadrants[3].copy()
            if i < len(right.layers):
                # 새로운 인덱스 매핑에서 동쪽 절반: 0=TR, 1=BR
                if right.layers[i].quadrants[0]: new_layers[i].quadrants[0] = right.layers[i].quadrants[0].copy()
                if right.layers[i].quadrants[1]: new_layers[i].quadrants[1] = right.layers[i].quadrants[1].copy()
        
        final_shape = Shape(new_layers)
        final_shape.max_layers = result_max_layers
        while len(final_shape.layers) > 0 and final_shape.layers[-1].is_empty():
            final_shape.layers.pop()
            
        return final_shape

    @staticmethod
    def swap(shape_a: Shape, shape_b: Shape) -> Tuple[Shape, Shape]:
        halves = {}
        for name, shape_in in [('a', shape_a), ('b', shape_b)]:
            # 새로운 인덱스 매핑에서 서쪽 절반: 2=BL, 3=TL
            destroyed_w = {(l, q) for l in range(len(shape_in.layers)) for q in [2, 3] if shape_in._get_piece(l, q)}
            shattered_w = shape_in._calculate_shatter_set(destroyed_w)
            east_half = shape_in.copy()
            for l, q in shattered_w:
                if 0 <= l < len(east_half.layers): east_half.layers[l].quadrants[q] = None
            
            # 새로운 인덱스 매핑에서 동쪽 절반: 0=TR, 1=BR
            destroyed_e = {(l, q) for l in range(len(shape_in.layers)) for q in [0, 1] if shape_in._get_piece(l, q)}
            shattered_e = shape_in._calculate_shatter_set(destroyed_e)
            west_half = shape_in.copy()
            for l, q in shattered_e:
                if 0 <= l < len(west_half.layers): west_half.layers[l].quadrants[q] = None
            
            halves[name] = (west_half, east_half)

        a_west_stable = halves['a'][0].apply_physics()
        a_east_stable = halves['a'][1].apply_physics()
        b_west_stable = halves['b'][0].apply_physics()
        b_east_stable = halves['b'][1].apply_physics()

        output_a = Shape._merge_halves(b_west_stable, a_east_stable)
        output_b = Shape._merge_halves(a_west_stable, b_east_stable)

        return output_a, output_b

    def paint(self, color_str: str) -> Shape:
        s = self.copy()
        if not s.layers:
            return s
        
        top_layer = s.layers[-1]
        
        for quad in top_layer.quadrants:
            if quad and quad.shape not in ['c', 'P']:
                quad.color = color_str
                
        return s
    
    def normalize(self) -> Shape:
        s = self.copy()
        for layer in s.layers:
            for quad in layer.quadrants:
                if quad:
                    if quad.shape in ['R', 'S', 'W']:
                        quad.shape = 'C'
                    if quad.shape != 'P':
                        quad.color = 'y'
        return s

    def is_stable(self) -> bool:
        return repr(self.apply_physics()) == repr(self)

    def hybrid(self, claw : bool = False) -> tuple[Shape, Shape]:
        """하이브리드 함수: 입력을 마스크 기반으로 두 부분으로 분리합니다."""
        mask = {}
        # 1. 각 셀에 대응되는 (사분면x층) 크기의 임시 마스크를 만듭니다 (1로 초기화)
        for l in range(len(self.layers)):
            for q in range(4):
                mask[(l, q)] = 1
                
        # 2. 0층의 P는 마스크 0으로 설정
        if claw:
            for q in range(4):
                piece = self._get_piece(0, q)
                if piece and (piece.shape == 'P' or piece.shape == 'S'):
                    mask[(0, q)] = 0
               
        # 3. 클로시 크리스탈 주변 마스크 0으로 설정
        if claw:
            # 모든 크리스탈을 찾습니다
            for l in range(len(self.layers)):
                for q in range(4):
                    piece = self._get_piece(l, q)
                    if piece and piece.shape == 'c':
                        # 크리스탈의 상, 좌, 우 (양쪽 사분면, 위 레이어)를 마스크 0으로 만들고 그 아래 모든 영역도 0으로 만듭니다
                        
                        # 상 (위 레이어의 같은 사분면)
                        upper_piece = self._get_piece(l, q)
                        if upper_piece:  # 빈칸이 아닌 경우에만
                            for upper_l in range(l, len(self.layers)):
                                mask[(upper_l, q)] = 0
                        
                        # 좌 사분면 (현재 층과 그 아래)
                        left_q = (q - 1) % 4
                        left_piece = self._get_piece(l, left_q)
                        if left_piece:  # 빈칸이 아닌 경우에만
                            for lower_l in range(l + 1):
                                mask[(lower_l, left_q)] = 0
                        
                        # 우 사분면 (현재 층과 그 아래)
                        right_q = (q + 1) % 4
                        right_piece = self._get_piece(l, right_q)
                        if right_piece:  # 빈칸이 아닌 경우에만
                            for lower_l in range(l + 1):
                                mask[(lower_l, right_q)] = 0
        
        # 4. 각 사분면의 가장 높은 크리스탈을 찾습니다
        for q in range(4):
            highest_crystal_layer = -1
            for l in range(len(self.layers) - 1, -1, -1):  # 위에서부터 탐색
                piece = self._get_piece(l, q)
                if piece and piece.shape == 'c':
                    highest_crystal_layer = l
                    break
            
            # 각 크리스탈과 그 아래는 모두 마스크 영역을 0로 만듭니다
            if highest_crystal_layer >= 0:
                for l in range(highest_crystal_layer + 1):  # 해당 층과 그 아래 모든 층
                    mask[(l, q)] = 0
        
        # 5. 마스크 영역 0인 부분만으로 임시 도형을 만들어 불안정한 도형 검사
        current_layer = 0
        while current_layer < len(self.layers):
            # 현재까지의 마스크 0 부분만으로 임시 도형 생성
            temp_layers = []
            for l in range(len(self.layers)):
                temp_quadrants = [None] * 4
                for q in range(4):
                    if mask.get((l, q), 0) == 0:
                        piece = self._get_piece(l, q)
                        if piece:
                            temp_quadrants[q] = piece.copy()
                temp_layers.append(Layer(temp_quadrants))
            
            temp_shape = Shape(temp_layers)
            
            # 현재 층에서 불안정한 도형 탐색 (마스크 0 영역에서만)
            # 마스크를 리버스하여 전달 (1과 0을 바꿈)
            reversed_mask = {}
            for key, value in mask.items():
                reversed_mask[key] = 1 - value
            unstable_coords = self._find_unstable_at_layer(temp_shape, current_layer, reversed_mask)
            
            # 불안정한 도형이 존재할 때, 원본 도형에서 양쪽 사분면 중 마스크 1이면서 S인 부분 찾기
            mask_changed = False
            if unstable_coords:
                for unstable_l, unstable_q in unstable_coords:
                    # 양쪽 사분면 검사 (불안정한 도형이 있는 사분면과 인접한 사분면들)
                    adjacent_quads = []
                    if unstable_q == 0:
                        adjacent_quads = [1, 3]
                    elif unstable_q == 1:
                        adjacent_quads = [0, 2]
                    elif unstable_q == 2:
                        adjacent_quads = [1, 3]
                    elif unstable_q == 3:
                        adjacent_quads = [0, 2]
                    
                    for check_q in adjacent_quads:
                        if (mask.get((unstable_l, check_q), 0) == 1 and 
                            self._get_piece(unstable_l, check_q) and 
                            self._get_piece(unstable_l, check_q).shape == 'S'):
                            # 해당 부분과 그 아래를 마스크 0으로 변경
                            for below_l in range(unstable_l + 1):
                                mask[(below_l, check_q)] = 0
                            mask_changed = True
                
                # 마스크가 변경되었으면 현재 층부터 다시 검사
                if mask_changed:
                    continue
            
            # 불안정한 도형이 없거나 마스크 변경이 없으면 다음 층으로
            current_layer += 1
        
        # 6. 특별 조건 검사: S 도형이 아래가 비어있고 옆 사분면이 마스크 0이면서 S 또는 c인 경우
        # 아래 레이어부터 위로 검사
        for current_layer in range(len(self.layers)):
            for q in range(4):
                coord = (current_layer, q)
                if mask.get(coord, 0) != 1:
                    continue
                
                piece = self._get_piece(current_layer, q)
                if not piece or piece.shape != 'S':
                    continue
                
                # 아래가 비어있는지 확인
                below_empty = current_layer == 0 or not self._get_piece(current_layer-1, q)
                if not below_empty:
                    continue
                
                # 현재 상태에서 지지되는지 확인
                temp_layers = []
                for l in range(len(self.layers)):
                    temp_quadrants = [None] * 4
                    for tq in range(4):
                        if mask.get((l, tq), 0) == 1:
                            temp_piece = self._get_piece(l, tq)
                            if temp_piece:
                                temp_quadrants[tq] = temp_piece.copy()
                    temp_layers.append(Layer(temp_quadrants))
                
                temp_shape = Shape(temp_layers)
                unstable_coords = self._find_unstable_at_layer(temp_shape, current_layer, mask)
                
                # 현재 좌표가 불안정한 경우에만 특별 조건 적용
                if coord in unstable_coords:
                    # 옆 사분면 검사
                    special_support_found = False
                    for nq in range(4):
                        if self._is_adjacent(q, nq):
                            neighbor_coord = (current_layer, nq)
                            if mask.get(neighbor_coord, 0) == 0:
                                neighbor_piece = self._get_piece(*neighbor_coord)
                                if neighbor_piece and neighbor_piece.shape in ['S', 'c']:
                                    special_support_found = True
                                    break
                    
                    # 특별 조건이 만족되면 해당 좌표와 그 아래 모든 층을 마스크 0으로 변경
                    if special_support_found:
                        for below_l in range(current_layer + 1):
                            mask[(below_l, q)] = 0
        
        # 7. 수정된 물리 적용으로 불안정한 도형 검사 (층별 순차 처리)
        # 맨 위 층부터 순서대로 아래로 진행
        for current_layer in range(len(self.layers) - 1, -1, -1):  # 맨 위부터 아래로
            # 현재 층에서 마스크 1인 부분만 추출하여 임시 도형 생성
            temp_layers = []
            for l in range(len(self.layers)):
                temp_quadrants = [None] * 4
                for q in range(4):
                    if mask.get((l, q), 0) == 1:
                        piece = self._get_piece(l, q)
                        if piece:
                            temp_quadrants[q] = piece.copy()
                temp_layers.append(Layer(temp_quadrants))
            
            temp_shape = Shape(temp_layers)
            
            # 현재 층에서 불안정한 도형 탐색
            unstable_coords = self._find_unstable_at_layer(temp_shape, current_layer, mask)
            
            # 불안정한 도형과 그 아래의 마스크를 0으로 만듭니다
            for l, q in unstable_coords:
                for below_l in range(l + 1):  # 해당 층과 그 아래 모든 층
                    mask[(below_l, q)] = 0
        
        # 8. 출력 A (마스크 0 부분만), 출력 B (마스크 1 부분만)
        output_a_layers = []
        output_b_layers = []
        
        for l in range(len(self.layers)):
            layer_a_quadrants = [None] * 4
            layer_b_quadrants = [None] * 4
            
            for q in range(4):
                piece = self._get_piece(l, q)
                if piece:
                    if mask.get((l, q), 0) == 0:
                        layer_a_quadrants[q] = piece.copy()
                    else:
                        layer_b_quadrants[q] = piece.copy()
            
            output_a_layers.append(Layer(layer_a_quadrants))
            output_b_layers.append(Layer(layer_b_quadrants))
        
        output_a = Shape(output_a_layers)
        output_b = Shape(output_b_layers)
        
        # 빈 레이어 제거
        while len(output_a.layers) > 0 and output_a.layers[-1].is_empty():
            output_a.layers.pop()
        while len(output_b.layers) > 0 and output_b.layers[-1].is_empty():
            output_b.layers.pop()
        
        # B 출력에서 각 레이어별로 ----로 아예 빈 층 제거
        # 모든 빈 레이어를 제거 (위에서부터 순서대로)
        i = len(output_b.layers) - 1
        while i >= 0:
            current_layer = output_b.layers[i]
            is_empty_layer = True
            for q in range(4):
                if current_layer.quadrants[q] is not None:
                    is_empty_layer = False
                    break
            if is_empty_layer:
                output_b.layers.pop(i)
            i -= 1
        
        # max_layers 설정
        output_a.max_layers = self.max_layers
        output_b.max_layers = self.max_layers
        
        return output_a, output_b

    def _find_unstable_at_layer(self, temp_shape: Shape, target_layer: int, mask: dict) -> set:
        """특정 층에서 불안정한 좌표를 찾습니다."""
        # 지지 계산 (마스크 1 부분에서만)
        supported = set()
        
        # 0층은 무조건 지지됨
        for q in range(4):
            if mask.get((0, q), 0) == 1 and temp_shape._get_piece(0, q):
                supported.add((0, q))
        
        # 마스크 0인 부분 아래의 도형들도 지지됨 (절대 지지성)
        for l in range(len(self.layers)):
            for q in range(4):
                if mask.get((l, q), 0) == 1 and temp_shape._get_piece(l, q):
                    # 바로 아래가 마스크 0이면 지지됨
                    if l > 0 and mask.get((l-1, q), 0) == 0:
                        supported.add((l, q))
        
        # 연결성 기반 지지 전파
        while True:
            num_supported_before = len(supported)
            visited_groups = set()
            
            for l_start in range(len(temp_shape.layers)):
                for q_start in range(4):
                    coord = (l_start, q_start)
                    if (coord not in visited_groups and 
                        mask.get(coord, 0) == 1 and 
                        temp_shape._get_piece(*coord)):
                        
                        group = temp_shape._find_connected_group(l_start, q_start)
                        # 마스크 1인 부분만 필터링
                        mask_filtered_group = {c for c in group if mask.get(c, 0) == 1}
                        
                        if any(c in supported for c in mask_filtered_group):
                            supported.update(mask_filtered_group)
                        visited_groups.update(mask_filtered_group)
            
            # 수직 지지 확인
            for l in range(len(temp_shape.layers)):
                for q in range(4):
                    coord = (l, q)
                    if (coord in supported or 
                        mask.get(coord, 0) != 1 or 
                        not temp_shape._get_piece(*coord)):
                        continue
                    
                    piece = temp_shape._get_piece(l, q)
                    if l > 0 and (l - 1, q) in supported:
                        supported.add(coord)
                    elif piece and piece.shape != 'P':
                        # 수평 연결 지지
                        for nq in range(4):
                            if self._is_adjacent(q, nq):
                                neighbor_coord = (l, nq)
                                if neighbor_coord in supported:
                                    supporter = temp_shape._get_piece(*neighbor_coord)
                                    if supporter and supporter.shape != 'P':
                                        supported.add(coord)
                                        break
            
            if len(supported) == num_supported_before:
                break
        
        # 불안정한 좌표 찾기 (마스크 1인 부분 중 지지되지 않은 부분)
        all_mask1_coords = {(l, q) for l in range(len(self.layers)) 
                           for q in range(4) 
                           if mask.get((l, q), 0) == 1 and self._get_piece(l, q)}
        unstable_coords = all_mask1_coords - supported
        
        return unstable_coords

class InterruptedError(Exception):
    """A custom exception for cancelling the worker thread."""
    pass

# ==============================================================================
#  2. 역추적기 (ReverseTracer)
# ==============================================================================
class ReverseTracer:
    MAX_SEARCH_DEPTH = 1

    @staticmethod
    def _get_canonical_key(op_name: str, origin_shape: Shape | Tuple[Shape, Shape]) -> tuple:
        if isinstance(origin_shape, tuple):
            shape_a, shape_b = origin_shape
            pairs = []
            current_a, current_b = shape_a.copy(), shape_b.copy()
            for _ in range(4):
                pairs.append((repr(current_a), repr(current_b)))
                current_a = current_a.rotate()
                current_b = current_b.rotate()
            canonical_pair = min(pairs)
            return (op_name, canonical_pair[0], canonical_pair[1])
        else:
            shape = origin_shape
            reprs = []
            current_s = shape.copy()
            for _ in range(4):
                reprs.append(repr(current_s))
                current_s = current_s.rotate()
            canonical_repr = min(reprs)
            return (op_name, canonical_repr, "")

    @staticmethod
    def _find_unstable_by_adding(target: Shape, search_depth: int, worker: Optional[QThread] = None, allowed_pieces: List[str] = ['C', 'P', 'c'], op_name: str = "") -> List[Shape]:
        candidates = []
        target_repr = repr(target)
        
        empty_slots = [(l, q) for l in range(Shape.MAX_LAYERS) for q in range(4) if target._get_piece(l, q) is None]

        for d in range(1, search_depth + 1):
            if len(empty_slots) < d: break
            
            if worker and hasattr(worker, 'log'):
                worker.log(f"  -> [{op_name}] 불안정 후보 탐색 (조각 {d}개 추가):", verbose=True)

            combinations = itertools.combinations(empty_slots, d)
            for i, slot_combo in enumerate(combinations):
                if worker and i > 0 and i % 500 == 0 and worker.is_cancelled:
                    raise InterruptedError()
                for piece_combo in itertools.product(allowed_pieces, repeat=d):
                    if worker and worker.is_cancelled: raise InterruptedError
                    
                    unstable = target.copy()
                    for i_pc, (l, q) in enumerate(slot_combo):
                        piece_type = piece_combo[i_pc]
                        color = 'y' if piece_type != 'P' else 'u'
                        while len(unstable.layers) <= l: unstable.layers.append(Layer([None]*4))
                        unstable.layers[l].quadrants[q] = Quadrant(piece_type, color)
                    
                    if worker and hasattr(worker, 'log'):
                        worker.log(f"    - 검사: {repr(unstable)}", verbose=True)

                    if repr(unstable.apply_physics()) == target_repr:
                        if repr(unstable) != target_repr:
                            candidates.append(unstable)

        if search_depth >= 1:
            for l in range(Shape.MAX_LAYERS):
                if all(target._get_piece(l, q) is None for q in range(4)):
                    for piece_type in ['C', 'c']:
                        unstable = target.copy()
                        color = 'y'
                        
                        while len(unstable.layers) <= l: unstable.layers.append(Layer([None]*4))
                        unstable.layers[l] = Layer([Quadrant(piece_type, color)]*4)
                        
                        if worker and hasattr(worker, 'log'):
                            worker.log(f"  -> [{op_name}] 전체 레이어 낙하 검사: {l+1}층 ({repr(unstable)})", verbose=True)

                        if repr(unstable.apply_physics()) == target_repr:
                            if repr(unstable) != target_repr:
                                candidates.append(unstable)
        return candidates

    @staticmethod
    def _find_unstable_by_rearranging_pieces(target: Shape, search_depth: int, max_physics_height: int, worker: Optional[QThread] = None) -> List[Shape]:
        candidates = []
        unique_candidates_reprs = set()
        target_repr = repr(target)

        present_pieces = [(l, q, target._get_piece(l, q)) for l in range(len(target.layers)) for q in range(4) if target._get_piece(l, q)]
        if not present_pieces:
            return []
        
        present_pieces.sort(key=lambda x: -x[0])

        if worker and hasattr(worker, 'log'):
            worker.log(f"  -> [apply_physics] 기존 조각 재배치 탐색 (최대 {search_depth}개 이동):", verbose=True)

        for d in range(1, search_depth + 1):
            if len(present_pieces) < d:
                break

            if worker and hasattr(worker, 'log'):
                worker.log(f"    - {d}개 조각 이동 조합 탐색 중...", verbose=True)
            
            log_counter = 0

            for pieces_to_move_info in itertools.combinations(present_pieces, d):
                if worker and worker.is_cancelled: raise InterruptedError()
                
                base_shape = target.copy()
                moved_pieces_coords = set()
                for l, q, _ in pieces_to_move_info:
                    base_shape.layers[l].quadrants[q] = None
                    moved_pieces_coords.add((l,q))

                stationary_pieces_by_q = {q: [] for q in range(4)}
                for l_stat, q_stat, _ in present_pieces:
                    if (l_stat, q_stat) not in moved_pieces_coords:
                        stationary_pieces_by_q[q_stat].append(l_stat)
                
                empty_slots_by_q = {q: [] for q in range(4)}
                for l_slot in range(Shape.MAX_LAYERS):
                    for q_slot in range(4):
                        if base_shape._get_piece(l_slot, q_slot) is None:
                            empty_slots_by_q[q_slot].append(l_slot)

                possible_destinations_per_piece = []
                for p_old_l, p_old_q, _ in pieces_to_move_info:
                    next_blocker_l = Shape.MAX_LAYERS
                    for stat_l in stationary_pieces_by_q[p_old_q]:
                        if stat_l > p_old_l:
                            next_blocker_l = min(next_blocker_l, stat_l)
                    
                    valid_new_layers = [
                        l_new for l_new in empty_slots_by_q[p_old_q]
                        if p_old_l <= l_new < next_blocker_l and (l_new - p_old_l) <= max_physics_height
                    ]
                    possible_destinations_per_piece.append([(l, p_old_q) for l in valid_new_layers])
                
                if not all(possible_destinations_per_piece):
                    continue
                
                for dest_combo in itertools.product(*possible_destinations_per_piece):
                    if worker and worker.is_cancelled: raise InterruptedError()
                    
                    if len(set(dest_combo)) != d: continue
                    
                    is_valid_mapping = True
                    for i in range(d):
                        for j in range(i + 1, d):
                            p1_old_l, p1_old_q, _ = pieces_to_move_info[i]
                            p2_old_l, p2_old_q, _ = pieces_to_move_info[j]
                            if p1_old_q != p2_old_q: continue
                            p1_new_l, _ = dest_combo[i]
                            p2_new_l, _ = dest_combo[j]
                            if (p1_old_l < p2_old_l) and not (p1_new_l < p2_new_l): is_valid_mapping = False; break
                            if (p1_old_l > p2_old_l) and not (p1_new_l > p2_new_l): is_valid_mapping = False; break
                        if not is_valid_mapping: break
                    if not is_valid_mapping: continue

                    candidate = base_shape.copy()
                    pieces_to_place = [info[2] for info in pieces_to_move_info]
                    for i, (l_new, q_new) in enumerate(dest_combo):
                        while len(candidate.layers) <= l_new: candidate.layers.append(Layer([None]*4))
                        candidate.layers[l_new].quadrants[q_new] = pieces_to_place[i].copy()
                    
                    log_counter += 1
                    if worker and hasattr(worker, 'log') and (log_counter < 20 or log_counter % 200 == 0):
                                                  worker.log(f"      - 검사 ({d}개 이동, 유효성 통과): {repr(candidate)}", verbose=True)

                    if repr(candidate.apply_physics()) == target_repr:
                        cand_repr = repr(candidate)
                        if cand_repr != target_repr and cand_repr not in unique_candidates_reprs:
                            if worker and hasattr(worker, 'log'):
                                worker.log(f"      ✅ 재배치 후보 발견: {repr(candidate)}")
                            unique_candidates_reprs.add(cand_repr)
                            candidates.append(candidate)
        
        if worker and hasattr(worker, 'log'):
                             worker.log(f"    - 재배치 탐색 완료. 최종 후보 {len(candidates)}개.", verbose=True)

        return candidates

    @staticmethod
    def _explore_pillar_variations(base_candidate: Shape, pillars_built: List[Tuple[int, int]], target_repr: str, worker: Optional[QThread]) -> List[Shape]:
        """주어진 기둥 후보를 기반으로, 연결된 추가 파괴 구조를 탐색하여 다양한 후보를 생성합니다."""
        candidates = []
        
        # 1. 원본 기둥 후보 자체를 검사합니다.
        if worker and hasattr(worker, 'log'):
                                worker.log(f"      - 검사 (기본 기둥): {repr(base_candidate)}", verbose=True)
        if repr(base_candidate.push_pin()) == target_repr:
            if worker and hasattr(worker, 'log'):
                worker.log(f"      ✅ 천장 기둥 후보 발견: {repr(base_candidate)}")
            candidates.append(base_candidate.copy())

        # 2. 기둥에 연결된 위치에 추가적인 파괴 구조를 만들어봅니다.
        pillar_coords = set()
        for q_col, start_l in pillars_built:
            for l in range(start_l, Shape.MAX_LAYERS):
                pillar_coords.add((l, q_col))

        # 기둥에 인접한 빈 슬롯 찾기
        connected_slots = set()
        for l_p, q_p in pillar_coords:
            # 수평 인접
            for nq in range(4):
                if base_candidate._is_adjacent(q_p, nq):
                    if (l_p, nq) not in pillar_coords and base_candidate._get_piece(l_p, nq) is None:
                        connected_slots.add((l_p, nq))
            # 수직 인접 (아래)
            if l_p > 0 and (l_p - 1, q_p) not in pillar_coords and base_candidate._get_piece(l_p - 1, q_p) is None:
                connected_slots.add((l_p - 1, q_p))
        
        if worker and hasattr(worker, 'log') and connected_slots:
                                    worker.log(f"        -> 기둥에 연결된 추가 파괴 구조물 탐색 (연결점 {len(connected_slots)}개)...", verbose=True)

        for l, q in connected_slots:
            if worker and worker.is_cancelled: raise InterruptedError
            
            # 이 위치 (l,q)에 크리스탈이 있었다고 가정합니다.
            # 이 가설이 성립하려면, 그 바로 위 (l+1, q)에 'S' 또는 'P' 조각이 *이미* 존재해야 합니다.
            # 이 상위 조각이 연쇄 파괴를 유발하는 시나리오를 역추적합니다.
            top_piece = base_candidate._get_piece(l + 1, q)
            if top_piece and top_piece.shape in ['S', 'P']:
                variation = base_candidate.copy()
                
                # (l,q)에 크리스탈을 추가하여 후보를 생성합니다.
                # (l+1, q)의 조각은 base_candidate에 이미 존재하므로 새로 추가하지 않습니다.
                while len(variation.layers) <= l: variation.layers.append(Layer([None]*4))
                variation.layers[l].quadrants[q] = Quadrant('c', 'y')
                
                if worker and hasattr(worker, 'log'):
                                                worker.log(f"          - 검사 (c@({l},{q}), 기존 {top_piece.shape}@({l+1},{q})): {repr(variation)}", verbose=True)

                # push_pin을 적용하여 목표와 일치하는지 확인
                if repr(variation.push_pin()) == target_repr:
                    if worker and hasattr(worker, 'log'):
                        worker.log(f"          ✅ 복합 파괴 후보 발견: {repr(variation)}")
                    candidates.append(variation)

        return candidates

    @staticmethod
    def inverse_apply_physics(target: Shape, search_depth: int, max_physics_height: int, worker: Optional[QThread] = None) -> List[Tuple[str, Shape]]:
        candidates = []
        if not target.is_stable(): return []
        
        target_repr = repr(target)
        
        if worker and hasattr(worker, 'log'): worker.log(f"  -> [apply_physics] 원본 안정성 검사: {repr(target)}", verbose=True)

        for height in range(1, max_physics_height + 1):
            if worker and worker.is_cancelled: raise InterruptedError
            if len(target.layers) + height > Shape.MAX_LAYERS: break
            lifted_layers = [Layer([None] * 4) for _ in range(height)] + [l.copy() for l in target.layers]
            lifted_shape = Shape(lifted_layers)
            
            if worker and hasattr(worker, 'log'): worker.log(f"  -> [apply_physics] {height}칸 인상 검사: {repr(lifted_shape)}", verbose=True)

            if repr(lifted_shape.apply_physics()) == target_repr:
                candidates.append(lifted_shape)

        rearranged_candidates = ReverseTracer._find_unstable_by_rearranging_pieces(target, search_depth, max_physics_height, worker)
        candidates.extend(rearranged_candidates)
        
        # 최종 후보 목록에서 자기 자신과 동일한 모양은 제외하고, 모든 후보를 재검증합니다.
        final_candidates = []
        seen_reprs = set()
        for c in candidates:
            cand_repr = repr(c)
            if cand_repr == target_repr:
                continue
            
            if cand_repr in seen_reprs:
                continue

            if repr(c.apply_physics()) == target_repr:
                final_candidates.append(c)
                seen_reprs.add(cand_repr)
            elif worker and hasattr(worker, 'log'):
                                    worker.log(f"    - ⚠️ 검증 실패: {cand_repr}  -> 물리 적용 후: {repr(c.apply_physics())}", verbose=True)

        return [("apply_physics", c) for c in final_candidates]

    @staticmethod
    def inverse_push_pin(target: Shape, search_depth: int, max_physics_height: int, worker: Optional[QThread] = None) -> List[Tuple[str, Shape]]:
        # push_pin의 결과는 0층에 조각이 있거나, 아예 비어있어야 함
        if not target.layers:
            return []

        # 0층 검사: 핀만 존재해야 하고, 다른 조각이 있으면 안됨
        for q in range(4):
            p = target._get_piece(0, q)
            if p and p.shape != 'P':
                if worker and hasattr(worker, 'log'):
                    worker.log(f"  -> [push_pin] 0층에 핀이 아닌 조각({p.shape})이 있어 건너뜀.", verbose=True)
                return []
    
    
        candidates = []
        target_repr = repr(target)

        # 1. 기본 후보: 파괴가 없었다고 가정한 가장 간단한 케이스
        s_initial_guess = Shape([l.copy() for l in target.layers[1:]])
        if worker and hasattr(worker, 'log'): worker.log(f"  -> [push_pin] 안정된 원형(핀 제거) 검사: {repr(s_initial_guess)}", verbose=True)
        if repr(s_initial_guess.push_pin()) == target_repr:
            candidates.append(s_initial_guess)
            # 이 기본 후보를 기반으로 불안정한 다른 형태들도 탐색
            if worker and hasattr(worker, 'log'): worker.log(f"  -> [push_pin] 기본 원형의 불안정 후보 탐색 (물리 역연산):", verbose=True)
            unstable_origins_tuples = ReverseTracer.inverse_apply_physics(s_initial_guess, search_depth, max_physics_height, worker)
            candidates.extend([shape for _, shape in unstable_origins_tuples])

        # 2. 파괴된 크리스탈 기둥 역추적 (천장에 닿고, 기존 조각을 덮어쓰지 않음)
        if worker and hasattr(worker, 'log'):
            worker.log(f"  -> [push_pin] 파괴된 천장 크리스탈 기둥 역추적 시도:", verbose=True)
        
        s_base = Shape([l.copy() for l in target.layers[1:]])

        # search_depth만큼의 기둥을 세웁니다. 최대 4개.
        for d in range(1, min(search_depth, 4) + 1):
            if worker and hasattr(worker, 'log'): 
                worker.log(f"    - {d}개 천장 기둥 추가 조합 탐색 중...", verbose=True)

            # 기둥을 세울 사분면 조합
            for q_combo in itertools.combinations(range(4), d):
                if worker and worker.is_cancelled: raise InterruptedError
                
                origin_candidate = s_base.copy()
                
                # 후보의 레이어 수가 MAX_LAYERS가 되도록 확장
                while len(origin_candidate.layers) < Shape.MAX_LAYERS:
                    origin_candidate.layers.append(Layer([None]*4))

                can_build_pillars = True
                pillars_to_build = [] # (q_col, start_l)

                for q_col in q_combo:
                    # 이 사분면에서 가장 높은 기존 조각의 위치를 찾습니다.
                    top_piece_l = -1
                    for l in range(Shape.MAX_LAYERS):
                        if origin_candidate._get_piece(l, q_col) is not None:
                            top_piece_l = l
                    
                    pillar_start_l = top_piece_l + 1
                    
                    # 기둥이 세워질 공간(맨 위까지)이 비어있는지 확인합니다. (덮어쓰기 방지)
                    for l_check in range(pillar_start_l, Shape.MAX_LAYERS):
                        if origin_candidate._get_piece(l_check, q_col) is not None:
                            can_build_pillars = False
                            break
                    if not can_build_pillars:
                        break
                    
                    pillars_to_build.append((q_col, pillar_start_l))

                if not can_build_pillars:
                    continue

                # 유효한 위치에만 기둥을 건설합니다.
                new_crystal = Quadrant('c', 'y')
                for q_col, start_l in pillars_to_build:
                    for l_col in range(start_l, Shape.MAX_LAYERS):
                        origin_candidate.layers[l_col].quadrants[q_col] = new_crystal.copy()
                
                pillar_variations = ReverseTracer._explore_pillar_variations(
                    origin_candidate, pillars_to_build, target_repr, worker
                )
                candidates.extend(pillar_variations)

        # 최종 중복 제거
        final_candidates = []
        seen_reprs = set()
        for c in candidates:
            r = repr(c)
            if r not in seen_reprs:
                final_candidates.append(c)
                seen_reprs.add(r)

        return [("push_pin", c) for c in final_candidates]

    @staticmethod
    def inverse_stack(target: Shape, search_depth: int, worker: Optional[QThread] = None) -> List[Tuple[str, Tuple[Shape, Shape]]]:
        candidates = []
        target_repr = repr(target)
        
        for i in range(1, len(target.layers)):
            if worker and worker.is_cancelled: raise InterruptedError
            bottom_candidate = Shape(target.layers[:i])
            top_candidate = Shape(target.layers[i:])
            
            if not bottom_candidate.is_stable(): continue
            if any(q and q.shape == 'c' for l in top_candidate.layers for q in l.quadrants): continue

            if top_candidate.is_stable():
                 if worker and hasattr(worker, 'log'): worker.log(f"  -> [stack] 분할 후 안정성 검사 (B:{repr(bottom_candidate)}, T:{repr(top_candidate)})", verbose=True)
                 if repr(Shape.stack(bottom_candidate, top_candidate)) == target_repr:
                     if repr(bottom_candidate) and repr(top_candidate):
                        candidates.append(("stack", (bottom_candidate, top_candidate)))

            unstable_tops = ReverseTracer._find_unstable_by_adding(top_candidate, search_depth, worker, op_name="stack")
            for unstable_top in unstable_tops:
                if worker and worker.is_cancelled: raise InterruptedError
                if worker and hasattr(worker, 'log'): worker.log(f"  -> [stack] 불안정한 상단 검사 (B:{repr(bottom_candidate)}, T:{repr(unstable_top)})", verbose=True)
                if repr(Shape.stack(bottom_candidate, unstable_top)) == target_repr:
                    if repr(bottom_candidate) and repr(unstable_top):
                        candidates.append(("stack", (bottom_candidate, unstable_top)))
                        
        return candidates

    @staticmethod
    def inverse_destroy_half(target: Shape, rotation_count: int, search_depth: int, worker: Optional[QThread] = None) -> List[Tuple[str, Shape]]:
        # 역연산을 시도하기 전, 이 함수는 목표 도형의 서쪽(좌측) 절반이 비어있다고 가정합니다.
        # 비어있지 않다면, 이 도형은 destroy_half의 직접적인 결과물이 될 수 없으므로 건너뜁니다.
        for l in range(len(target.layers)):
            # 새로운 인덱스 매핑에서 서쪽 절반: 2=BL, 3=TL
            if target._get_piece(l, 2) is not None or target._get_piece(l, 3) is not None:
                if worker and hasattr(worker, 'log'):
                    worker.log(f"  -> [destroy_half] (회전 {rotation_count}) 좌측 절반이 비어있지 않아 건너뜀.", verbose=True)
                return []
                
        candidates = []
        target_repr = repr(target)

        symmetric_candidate = target.copy()
        for l_idx, layer in enumerate(symmetric_candidate.layers):
            # 새로운 인덱스 매핑: 동쪽 절반(0=TR, 1=BR)을 서쪽 절반(3=TL, 2=BL)으로 복사
            if (p := target._get_piece(l_idx, 0)): layer.quadrants[3] = p.copy()  # TR -> TL
            if (p := target._get_piece(l_idx, 1)): layer.quadrants[2] = p.copy()  # BR -> BL
        
        if worker and hasattr(worker, 'log'): worker.log(f"  -> [destroy_half] 대칭 후보 검사: {repr(symmetric_candidate)}", verbose=True)
        if repr(symmetric_candidate.destroy_half()) == target_repr:
            origin = symmetric_candidate
            for _ in range(rotation_count): origin = origin.rotate(clockwise=False)
            candidates.append(origin)
            
        empty_slots = []
        for l in range(Shape.MAX_LAYERS):
            # 새로운 인덱스 매핑에서 서쪽 절반: 2=BL, 3=TL
            for q in [2, 3]:
                if target._get_piece(l, q) is None: empty_slots.append((l, q))
        
        for d in range(1, search_depth + 1):
            if len(empty_slots) < d: break

            if worker and hasattr(worker, 'log'): worker.log(f"  -> [destroy_half] 파괴된 부분 조각 추가 탐색 (조각 {d}개):", verbose=True)

            combinations = itertools.combinations(empty_slots, d)
            for i, slot_combo in enumerate(combinations):
                if worker and i > 0 and i % 500 == 0 and worker.is_cancelled:
                    raise InterruptedError()
                for piece_combo in itertools.product(['C', 'P', 'c'], repeat=d):
                    if worker and worker.is_cancelled: raise InterruptedError()
                    unstable = target.copy()
                    for i_pc, (l, q) in enumerate(slot_combo):
                        piece_type = piece_combo[i_pc]
                        color = 'y' if piece_type != 'P' else 'u'
                        while len(unstable.layers) <= l: unstable.layers.append(Layer([None]*4))
                        unstable.layers[l].quadrants[q] = Quadrant(piece_type, color)
                    
                    if worker and hasattr(worker, 'log'): worker.log(f"    - 검사: {repr(unstable)}", verbose=True)
                    if repr(unstable.destroy_half()) == target_repr:
                        origin = unstable
                        for _ in range(rotation_count): origin = origin.rotate(clockwise=False)
                        candidates.append(origin)

        return [("destroy_half", c) for c in candidates]

    @staticmethod
    def inverse_crystal_generator(target: Shape, search_depth: int, worker: Optional[QThread] = None) -> List[Tuple[str, Shape]]:
        candidates = []
        target_repr = repr(target)
        
        crystal_coords = [(l,q) for l, layer in enumerate(target.layers) for q, quad in enumerate(layer.quadrants) if quad and quad.shape == 'c']
        
        if not crystal_coords and worker and hasattr(worker, 'log'):
            worker.log("  -> [crystal_generator] 목표에 크리스탈이 없어 탐색 종료.", verbose=True)

        for l, q in crystal_coords:
            if worker and worker.is_cancelled: raise InterruptedError
            origin_candidate = target.copy()
            origin_candidate.layers[l].quadrants[q] = None
            
            if worker and hasattr(worker, 'log'): worker.log(f"  -> [crystal_generator] ({l},{q}) 크리스탈 제거 후 검사: {repr(origin_candidate)}", verbose=True)
            
            for color in [c for c in Quadrant.VALID_COLORS if c != 'u']:
                if repr(origin_candidate.crystal_generator(color)) == target_repr:
                    candidates.append(origin_candidate.apply_physics())
                    
                    if worker and hasattr(worker, 'log'):
                        worker.log(f"  -> [crystal_generator] 최상층에 불안정한 크리스탈 추가 탐색...", verbose=True)
                    
                    top_layer_idx = Shape.MAX_LAYERS - 1
                    empty_slots_on_top = []
                    for q_slot in range(4):
                        if origin_candidate._get_piece(top_layer_idx, q_slot) is None:
                            empty_slots_on_top.append((top_layer_idx, q_slot))

                    for d_unstable in range(1, len(empty_slots_on_top) + 1):
                        if d_unstable > search_depth: break
                        for slot_combo in itertools.combinations(empty_slots_on_top, d_unstable):
                            if worker and worker.is_cancelled: raise InterruptedError
                            
                            unstable = origin_candidate.copy()
                            while len(unstable.layers) <= top_layer_idx:
                                unstable.layers.append(Layer([None]*4))

                            for l_unstable, q_unstable in slot_combo:
                                unstable.layers[l_unstable].quadrants[q_unstable] = Quadrant('c', 'y') 

                            if worker and hasattr(worker, 'log'):
                                worker.log(f"    - 천장 검사: {repr(unstable)}", verbose=True)
                            
                            if repr(unstable.crystal_generator(color)) == target_repr:
                                candidates.append(unstable)
                    break 
                    
        return [("crystal_generator", c) for c in candidates]

    @staticmethod
    def inverse_swap(target: Shape, rotation_count: int, search_depth: int, worker: Optional[QThread] = None) -> List[Tuple[str, Tuple[Shape, Shape]]]:
        candidates = []
        target_repr = repr(target)

        left_half = target.copy()
        # 새로운 인덱스 매핑에서 동쪽 절반(0=TR, 1=BR) 제거
        for l in left_half.layers: l.quadrants[0] = l.quadrants[1] = None
        left_half = left_half.apply_physics()

        right_half = target.copy()
        # 새로운 인덱스 매핑에서 서쪽 절반(2=BL, 3=TL) 제거
        for l in right_half.layers: l.quadrants[2] = l.quadrants[3] = None
        right_half = right_half.apply_physics()

        potential_pairs = [(left_half, right_half)]
        if repr(left_half) != repr(right_half):
             potential_pairs.append((right_half, left_half))

        for a_guess, b_guess in potential_pairs:
            if worker and worker.is_cancelled: raise InterruptedError
            
            if worker and hasattr(worker, 'log'): worker.log(f"  -> [swap] 분할/재조합 후보 검사 (A:{repr(a_guess)}, B:{repr(b_guess)})", verbose=True)

            res_a, res_b = Shape.swap(a_guess, b_guess)
            
            if repr(res_a) == target_repr or repr(res_b) == target_repr:
                a_origin, b_origin = a_guess.copy(), b_guess.copy()
                for _ in range(rotation_count):
                    a_origin = a_origin.rotate(clockwise=False)
                    b_origin = b_origin.rotate(clockwise=False)
                
                if repr(a_origin) or repr(b_origin):
                    candidates.append(("swap", (a_origin, b_origin)))

        return candidates


if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    from gui import ShapezGUI
    
    app = QApplication(sys.argv)
    ex = ShapezGUI()
    ex.show()
    sys.exit(app.exec())
