import tkinter as tk
from tkinter import ttk, messagebox
import math

class ShapezVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("Shapez2 모양 시뮬레이터")
        self.root.geometry("800x600")
        
        # 색상 매핑
        self.colors = {
            'u': '#CCCCCC',  # 무색 (회색)
            'r': '#FF0000',  # 빨강
            'g': '#00FF00',  # 초록
            'b': '#0000FF',  # 파랑
            'c': '#00FFFF',  # 시안
            'm': '#FF00FF',  # 마젠타
            'y': '#FFFF00',  # 노랑
            'w': '#FFFFFF'   # 화이트
        }
        
        # 층 표시 관련 변수
        self.current_layers = []
        self.selected_layer = None  # None이면 모든 층 표시
        self.layer_buttons = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 입력 섹션
        input_frame = ttk.LabelFrame(main_frame, text="모양 코드 입력", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(input_frame, text="모양 코드:").grid(row=0, column=0, sticky=tk.W)
        self.shape_entry = ttk.Entry(input_frame, width=50)
        self.shape_entry.grid(row=0, column=1, padx=(10, 0), sticky=(tk.W, tk.E))
        self.shape_entry.bind('<Return>', lambda e: self.visualize_shape())
        
        ttk.Button(input_frame, text="시각화", command=self.visualize_shape).grid(row=0, column=2, padx=(10, 0))
        
        # 오른쪽 컨테이너 프레임 생성
        right_container_frame = ttk.Frame(main_frame, padding="10")
        right_container_frame.grid(row=0, column=1, rowspan=5, sticky=(tk.N, tk.S, tk.E, tk.W), padx=(10, 0))
        
        # 예시 버튼들을 담을 프레임 (오른쪽 컨테이너 내에 배치)
        example_frame = ttk.LabelFrame(right_container_frame, text="예시", padding="10")
        example_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        examples = [
            ("빨간 동그라미", "CrCrCrCr", "CrCrCrCr"),
            ("다양한 모양", "CrRg--Sb", "CrRg--Sb"),
            ("2층 모양", "CrRgSbWy:RuRuRuRu", "CrRgSbWy:RuRuRuRu"),
            ("핀 포함", "P-CrP-Rg", "P-CrP-Rg"),
            ("크리스탈", "cwcrcgcb", "cwcrcgcb")
        ]
        
        for i, (name, code, expected) in enumerate(examples):
            btn = ttk.Button(example_frame, text=name, 
                           command=lambda c=code: self.load_example(c))
            btn.grid(row=0, column=i, padx=(0, 5))
        
        # 중력 테스트 예시들
        gravity_examples = [
            ("중력 테스트 1", "--------:CuCuCuCu", "CuCuCuCu"),
            ("중력 테스트 2", "Cu------:CuCuCuCu", "Cu------:CuCuCuCu"),
            ("핀 중력 테스트", "Cu------:P-P-P-P-", "CuP-P-P-:P-------")
        ]
        
        for i, (name, code, expected) in enumerate(gravity_examples):
            btn = ttk.Button(example_frame, text=name, 
                           command=lambda c=code: self.load_example(c))
            btn.grid(row=1, column=i, padx=(0, 5))
        
        # 크리스탈 테스트 예시들
        crystal_examples = [
            ("크리스탈 낙하", "--------:crcrcrcr", ""),
            ("단순 낙하", "--------:cr------", ""),
            ("디버그 케이스", "cr------:crcrcrcr:--------:cr------", "cr------:crcrcrcr"),
            ("핀 지지 테스트", "P-------:P-------:P-----cr:crcrcrcr", "P-------:P-------:P-----cr:crcrcrcr")
        ]
        
        for i, (name, code, expected) in enumerate(crystal_examples):
            btn = ttk.Button(example_frame, text=name, 
                           command=lambda c=code: self.load_example(c))
            btn.grid(row=2, column=i, padx=(0, 5))
        
        # 추가 복합 테스트 예시들
        complex_examples = [
            ("핀 실패 테스트", "--------:P-----cr:crcrcrcr", "P-------"),
            ("3D 연결 테스트", "cr------:--------:cr------:crcrcrcr", "cr------"),
            ("복잡한 중력", "CrRg----:--------:P-P-P-P-:crcrcrcr", "CrRgP-P-:P-P-----")
        ]
        
        for i, (name, code, expected) in enumerate(complex_examples):
            btn = ttk.Button(example_frame, text=name, 
                           command=lambda c=code: self.load_example(c))
            btn.grid(row=3, column=i, padx=(0, 5))
        
        # 테스트 결과를 저장할 딕셔너리
        self.test_cases = {
            "basic": [
                ("기본 모양 테스트 1", "CrCrCrCr", "CrCrCrCr"),
                ("기본 모양 테스트 2", "CrRg--Sb", "CrRg--Sb")
            ],
            "gravity": [
                ("중력 테스트 0", "crcrcrcr", "crcrcrcr"),
                ("중력 테스트 1", "--------:CuCuCuCu", "CuCuCuCu"),
                ("중력 테스트 2", "Cu------:CuCuCuCu", "Cu------:CuCuCuCu"),
                ("핀 중력 테스트", "Cu------:P-P-P-P-", "CuP-P-P-:P-------")
            ],
            "crystal": [
                ("크리스탈 낙하", "--------:crcrcrcr", ""),
                ("단순 낙하", "--------:cr------", ""),
                ("디버그 케이스", "cr------:crcrcrcr:--------:cr------", "cr------:crcrcrcr"),
                ("핀 지지 테스트", "P-------:P-------:P-----cr:crcrcrcr", "P-------:P-------:P-----cr:crcrcrcr")
            ],
            "complex": [
                ("핀 실패 테스트", "--------:P-----cr:crcrcrcr", "P-------"),
                ("3D 연결 테스트", "cr------:--------:cr------:crcrcrcr", "cr------"),
                ("복잡한 중력", "CrRg----:--------:P-P-P-P-:crcrcrcr", "CrRgP-P-:P-P-----")
            ]
        }
        
        # 작업 버튼 프레임
        operation_frame = ttk.LabelFrame(main_frame, text="작업", padding="10")
        operation_frame.grid(row=2, column=0, columnspan=1, sticky=(tk.W, tk.E), pady=(0, 10))

        # 중력, 핀 푸셔 버튼
        ttk.Button(operation_frame, text="중력 적용", 
                    command=self.apply_gravity_to_current_shape).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(operation_frame, text="핀 푸셔 적용",
                    command=self.apply_pin_pusher).grid(row=0, column=1, padx=(0, 10))

        # 회전 버튼들
        ttk.Button(operation_frame, text="90° 회전", command=lambda: self.rotate_shape(90)).grid(row=0, column=2, padx=(0, 10))
        ttk.Button(operation_frame, text="180° 회전", command=lambda: self.rotate_shape(180)).grid(row=0, column=3, padx=(0, 10))
        ttk.Button(operation_frame, text="270° 회전", command=lambda: self.rotate_shape(270)).grid(row=0, column=4, padx=(0, 10))

        # 절단 버튼 (하프 디스트로이어)
        ttk.Button(operation_frame, text="절단 (하프)",
                    command=self.apply_half_destroyer).grid(row=0, column=5, padx=(0, 10))

        # 테스트 버튼 프레임
        test_control_frame = ttk.LabelFrame(main_frame, text="테스트", padding="10")
        test_control_frame.grid(row=3, column=0, columnspan=1, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(test_control_frame, text="모든 테스트 실행", 
                    command=self.run_all_tests).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(test_control_frame, text="중력 테스트만", 
                    command=self.run_gravity_tests).grid(row=0, column=1, padx=(0, 10))

        # 층 보기 컨트롤 프레임
        self.layer_control_frame = ttk.LabelFrame(main_frame, text="층 보기", padding="10")
        self.layer_control_frame.grid(row=4, column=0, columnspan=1, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 캔버스 프레임
        canvas_frame = ttk.LabelFrame(main_frame, text="모양 미리보기", padding="10")
        # 캔버스 프레임을 main_frame의 5번째 행에 배치하고, 행이 확장되도록 설정
        canvas_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.canvas = tk.Canvas(canvas_frame, width=600, height=400, bg='white')
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 정보 표시
        info_frame = ttk.LabelFrame(main_frame, text="정보", padding="10")
        # 정보 프레임을 main_frame의 6번째 행에 배치
        info_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # 복사 가능한 텍스트 위젯으로 변경
        self.info_text = tk.Text(info_frame, height=3, wrap=tk.WORD, 
                                font=("Arial", 9), bg="#f0f0f0", relief="flat")
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.info_text.insert("1.0", "모양 코드를 입력하고 시각화 버튼을 클릭하세요.")
        self.info_text.config(state=tk.DISABLED)  # 읽기 전용으로 설정
        
        # 스크롤바 추가
        info_scrollbar = ttk.Scrollbar(info_frame, orient="vertical", command=self.info_text.yview)
        info_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.info_text.config(yscrollcommand=info_scrollbar.set)
        
        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        # 그리드 설정
        info_frame.columnconfigure(0, weight=1)
        
        # 오른쪽 컨테이너 프레임 내부의 예시 프레임이 확장 가중치를 갖도록 설정
        right_container_frame.columnconfigure(0, weight=1)
        example_frame.columnconfigure(list(range(5)), weight=1)
        example_frame.rowconfigure(list(range(4)), weight=1) # 예시 버튼들이 있는 row에 weight 적용
        right_container_frame.rowconfigure(0, weight=1)
        
    def load_example(self, code):
        self.shape_entry.delete(0, tk.END)
        self.shape_entry.insert(0, code)
        self.visualize_shape()
        
    def update_layer_buttons(self):
        """층 보기 버튼들을 업데이트"""
        # 기존 버튼들 제거
        for widget in self.layer_control_frame.winfo_children():
            widget.destroy()
        self.layer_buttons.clear()
        
        if not self.current_layers:
            return
        
        # 전체 보기 버튼
        all_btn = ttk.Button(self.layer_control_frame, text="전체 보기", 
                           command=lambda: self.select_layer(None))
        all_btn.grid(row=0, column=0, padx=(0, 5))
        
        # 각 층별 보기 버튼
        for i in range(len(self.current_layers)):
            btn = ttk.Button(self.layer_control_frame, text=f"{i+1}층 보기", 
                           command=lambda layer_idx=i: self.select_layer(layer_idx))
            btn.grid(row=0, column=i+1, padx=(0, 5))
            self.layer_buttons.append(btn)
            
    def select_layer(self, layer_idx):
        """특정 층을 선택하여 표시"""
        self.selected_layer = layer_idx
        self.draw_shape(self.current_layers)
        
    def get_faded_color(self, color):
        """색상을 흐리게 만드는 함수 (투명도 효과)"""
        # stipple 패턴을 사용한 실제 투명도 효과를 위해 원래 색상 반환
        return color
        
    def parse_shape_code(self, code):
        """모양 코드를 파싱하여 층별 데이터로 변환"""
        if not code:
            return []
            
        layers = code.split(':')
        parsed_layers = []
        
        for layer in layers:
            if len(layer) % 2 != 0:
                raise ValueError(f"잘못된 층 형식: {layer}")
                
            parts = []
            for i in range(0, len(layer), 2):
                shape_type = layer[i]
                color = layer[i + 1]
                parts.append((shape_type, color))
                
            if len(parts) != 4:
                raise ValueError(f"각 층은 4개의 부분이 있어야 합니다: {layer}")
                
            parsed_layers.append(parts)
            
        return parsed_layers
        
    def visualize_shape(self):
        """모양을 시각화"""
        try:
            code = self.shape_entry.get().strip()
            if not code:
                return
                
            layers = self.parse_shape_code(code)
            self.current_layers = layers
            self.selected_layer = None  # 초기화
            self.update_layer_buttons()
            self.draw_shape(layers)
            
            layer_count = len(layers)
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete("1.0", tk.END)
            self.info_text.insert("1.0", f"층 개수: {layer_count}, 코드: {code}")
            self.info_text.config(state=tk.DISABLED)
            
        except ValueError as e:
            messagebox.showerror("오류", str(e))
        except Exception as e:
            messagebox.showerror("오류", f"예상치 못한 오류: {str(e)}")
            
    def draw_shape(self, layers):
        """캔버스에 모양 그리기"""
        self.canvas.delete("all")
        
        if not layers:
            return
            
        canvas_width = self.canvas.winfo_width() or 600
        canvas_height = self.canvas.winfo_height() or 400
        
        # 중심점 계산 (더 위쪽으로 이동)
        center_x = canvas_width // 2
        center_y = canvas_height // 2 - 50  # 50픽셀 위로 이동
        
        # 층 간격
        layer_spacing = 60
        base_size = 40
        
        for layer_idx, layer in enumerate(layers):
            # 현재 층이 선택되었는지 확인
            is_selected_layer = (self.selected_layer is None or 
                               self.selected_layer == layer_idx)
            
            # 각 층의 Y 위치 (아래층이 위에 그려짐)
            layer_y = center_y + (len(layers) - 1 - layer_idx) * layer_spacing
            
            # 4방향 위치 계산 (오른쪽위, 오른쪽아래, 왼쪽아래, 왼쪽위)
            positions = [
                (center_x + base_size, layer_y - base_size),  # 오른쪽위
                (center_x + base_size, layer_y + base_size),  # 오른쪽아래  
                (center_x - base_size, layer_y + base_size),  # 왼쪽아래
                (center_x - base_size, layer_y - base_size)   # 왼쪽위
            ]
            
            for part_idx, (shape_type, color) in enumerate(layer):
                if shape_type == '-':  # 빈 공간
                    continue
                    
                x, y = positions[part_idx]
                self.draw_part(x, y, shape_type, color, base_size // 2, is_selected_layer)
                
            # 층 번호 표시
            text_color = "black" if is_selected_layer else "lightgray"
            self.canvas.create_text(center_x - 120, layer_y, 
                                  text=f"층 {layer_idx + 1}", 
                                  anchor="w", font=("Arial", 10), fill=text_color)
                                  
    def draw_part(self, x, y, shape_type, color, size, is_selected=True):
        """개별 부분 그리기"""
        fill_color = self.colors.get(color, '#CCCCCC')
        
        # 선택되지 않은 층은 투명도 효과로 표시
        if not is_selected:
            outline_color = '#CCCCCC'
            # stipple 패턴으로 투명도 효과
            stipple_pattern = "gray25"  # 25% 패턴으로 투명도 효과
        else:
            outline_color = '#000000'
            stipple_pattern = ""
        
        if shape_type == 'C':  # 동그라미
            if is_selected:
                self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                      fill=fill_color, outline=outline_color, width=2)
            else:
                self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                      fill=fill_color, outline=outline_color, width=2,
                                      stipple=stipple_pattern)
                                      
        elif shape_type == 'R':  # 네모
            if is_selected:
                self.canvas.create_rectangle(x - size, y - size, x + size, y + size,
                                           fill=fill_color, outline=outline_color, width=2)
            else:
                self.canvas.create_rectangle(x - size, y - size, x + size, y + size,
                                           fill=fill_color, outline=outline_color, width=2,
                                           stipple=stipple_pattern)
                                           
        elif shape_type == 'S':  # 세모
            points = [
                x, y - size,           # 위쪽 점
                x - size, y + size,    # 왼쪽 아래
                x + size, y + size     # 오른쪽 아래
            ]
            if is_selected:
                self.canvas.create_polygon(points, fill=fill_color, outline=outline_color, width=2)
            else:
                self.canvas.create_polygon(points, fill=fill_color, outline=outline_color, width=2,
                                         stipple=stipple_pattern)
                                         
        elif shape_type == 'W':  # 윈드밀
            # 윈드밀을 다이아몬드 형태로 표현
            points = [
                x, y - size,           # 위
                x + size, y,           # 오른쪽
                x, y + size,           # 아래
                x - size, y            # 왼쪽
            ]
            if is_selected:
                self.canvas.create_polygon(points, fill=fill_color, outline=outline_color, width=2)
            else:
                self.canvas.create_polygon(points, fill=fill_color, outline=outline_color, width=2,
                                         stipple=stipple_pattern)
                                         
        elif shape_type == 'P':  # 핀
            # 핀을 작은 동그라미로 표현
            pin_size = size // 2
            pin_color = '#888888'
            if is_selected:
                self.canvas.create_oval(x - pin_size, y - pin_size, x + pin_size, y + pin_size,
                                      fill=pin_color, outline=outline_color, width=2)
                text_color = "white"
            else:
                self.canvas.create_oval(x - pin_size, y - pin_size, x + pin_size, y + pin_size,
                                      fill=pin_color, outline=outline_color, width=2,
                                      stipple=stipple_pattern)
                text_color = "lightgray"
            
            self.canvas.create_text(x, y, text="P", font=("Arial", 8), fill=text_color)
            
        elif shape_type == 'c':  # 크리스탈 (육각형)
            # 육각형 점 계산
            points = []
            for i in range(6):
                angle = i * math.pi / 3
                px = x + size * 0.8 * math.cos(angle)
                py = y + size * 0.8 * math.sin(angle)
                points.extend([px, py])
            
            if is_selected:
                self.canvas.create_polygon(points, fill=fill_color, outline=outline_color, width=2)
                text_color = "white"
            else:
                self.canvas.create_polygon(points, fill=fill_color, outline=outline_color, width=2,
                                         stipple=stipple_pattern)
                text_color = "lightgray"
            
            # 크리스탈 표시
            self.canvas.create_text(x, y, text="c", font=("Arial", 12), fill=text_color)
        
    def get_metallic_highlight(self, base_color):
        """메탈릭 하이라이트 색상 생성"""
        if base_color.startswith('#'):
            r = int(base_color[1:3], 16)
            g = int(base_color[3:5], 16)
            b = int(base_color[5:7], 16)
            
            # 밝기 증가
            r = min(255, r + 80)
            g = min(255, g + 80)
            b = min(255, b + 80)
            
            return f"#{r:02x}{g:02x}{b:02x}"
        return base_color
        
    def get_metallic_shadow(self, base_color):
        """메탈릭 그림자 색상 생성"""
        if base_color.startswith('#'):
            r = int(base_color[1:3], 16)
            g = int(base_color[3:5], 16)
            b = int(base_color[5:7], 16)
            
            # 밝기 감소
            r = max(0, r - 60)
            g = max(0, g - 60)
            b = max(0, b - 60)
            
            return f"#{r:02x}{g:02x}{b:02x}"
        return base_color

    def apply_gravity_to_current_shape(self):
        """현재 모양에 중력을 적용"""
        if not self.current_layers:
            messagebox.showwarning("경고", "먼저 모양을 시각화해주세요.")
            return
        
        try:
            # 원래 코드 저장
            original_code = self.shape_entry.get().strip()
            
            # 중력 적용 (크리스탈 로직 포함)
            new_layers, crystal_info = self.apply_gravity_with_crystals(self.current_layers)
            
            # 새로운 모양 코드 생성
            new_code = self.layers_to_code(new_layers)
            
            # 변화 여부 확인
            if original_code == new_code:
                # 변화가 없는 경우
                self.info_text.config(state=tk.NORMAL)
                self.info_text.delete("1.0", tk.END)
                self.info_text.insert("1.0", f"중력 적용 결과: 변화없음\n층 개수: {len(new_layers)}, 코드: {new_code}")
                self.info_text.config(state=tk.DISABLED)
            else:
                # 변화가 있는 경우
                # 입력창에 새 코드 설정하고 시각화
                self.shape_entry.delete(0, tk.END)
                self.shape_entry.insert(0, new_code)
                
                # 현재 레이어 업데이트
                self.current_layers = new_layers
                self.selected_layer = None
                self.update_layer_buttons()
                self.draw_shape(new_layers)
                
                # 크리스탈 정보 포함해서 표시
                info_text = f"중력 적용 완료!\n이전: {original_code}\n결과: {new_code}\n층 개수: {len(new_layers)}"
                if crystal_info['moved_crystals'] > 0:
                    info_text += f"\n💥 크리스탈 {crystal_info['moved_crystals']}개 이동으로 인한 파괴!"
                if crystal_info['destroyed_crystals'] > 0:
                    info_text += f"\n🔗 연쇄 파괴: {crystal_info['destroyed_crystals']}개 크리스탈 소멸"
                
                self.info_text.config(state=tk.NORMAL)
                self.info_text.delete("1.0", tk.END)
                self.info_text.insert("1.0", info_text)
                self.info_text.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("오류", f"중력 적용 중 오류 발생: {str(e)}")
    
    def apply_gravity_with_crystals(self, layers):
        """크리스탈 로직을 포함한 중력 적용 (테스트용 조용한 모드 추가)"""
        if not layers:
            return [], {'moved_crystals': 0, 'destroyed_crystals': 0}
        
        # 조용한 모드일 때 로그 출력 안함
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"=== 중력 적용 시작 ===")
            print(f"원본: {self.layers_to_code(layers)}")
        
        # 1. 중력 적용 전 크리스탈 위치와 연결 그룹 기록
        crystals_before = set()
        for layer_idx, layer in enumerate(layers):
            for part_idx, (shape_type, color) in enumerate(layer):
                if shape_type == 'c':
                    crystals_before.add((layer_idx, part_idx, color))
        
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"중력 적용 전 크리스탈: {crystals_before}")
        
        # 중력 적용 전 크리스탈 그룹들 찾기
        crystal_groups_before = self.find_3d_crystal_groups(layers, 
            {(layer_idx, part_idx) for layer_idx, part_idx, color in crystals_before})
        
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"크리스탈 그룹들: {crystal_groups_before}")
        
        # 2. 기본 중력 적용 (크리스탈도 일반 도형처럼 처리)
        result_layers = self.apply_basic_gravity(layers)
        
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"기본 중력 적용 후: {self.layers_to_code(result_layers)}")
        
        # 3. 중력 적용 후 크리스탈 위치 기록
        crystals_after = set()
        for layer_idx, layer in enumerate(result_layers):
            for part_idx, (shape_type, color) in enumerate(layer):
                if shape_type == 'c':
                    crystals_after.add((layer_idx, part_idx, color))
        
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"중력 적용 후 크리스탈: {crystals_after}")
        
        # 4. 위치가 변한 크리스탈 찾기 및 정확한 이동 추적
        moved_crystals = set()
        crystal_movements = {}  # 원래위치 -> 새위치 매핑
        
        # 중력 적용 전후 각 크리스탈 비교하여 정확한 이동 추적
        for before_layer, before_part, color in crystals_before:
            # 같은 위치에 같은 색상의 크리스탈이 여전히 있는지 확인
            if (before_layer, before_part, color) not in crystals_after:
                # 이동한 크리스탈 - 새 위치 찾기
                moved_crystals.add((before_layer, before_part))
                
                # 같은 사분면의 다른 층에서 같은 색상 크리스탈 찾기
                for after_layer, after_part, after_color in crystals_after:
                    if (after_part == before_part and after_color == color and 
                        (after_layer, after_part, after_color) not in 
                        [(bl, bp, bc) for bl, bp, bc in crystals_before if (bl, bp) != (before_layer, before_part)]):
                        # 이 크리스탈이 이동한 새 위치
                        crystal_movements[(before_layer, before_part)] = (after_layer, after_part)
                        break
        
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"이동한 크리스탈: {moved_crystals}")
            print(f"크리스탈 이동 경로: {crystal_movements}")
        
        # 5. 이동한 크리스탈이 속했던 원래 그룹들 찾아서 파괴
        crystal_info = {'moved_crystals': len(moved_crystals), 'destroyed_crystals': 0}
        
        if moved_crystals:
            # 이동한 크리스탈들이 원래 속했던 그룹들 찾기
            affected_groups = []
            groups_to_destroy = set()
            
            for group in crystal_groups_before:
                # 이 그룹에 이동한 크리스탈이 있었는지 확인
                for moved_pos in moved_crystals:
                    if moved_pos in group:
                        affected_groups.append(group)
                        groups_to_destroy.update(group)
                        break
            
            if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                print(f"영향받은 그룹들: {affected_groups}")
                print(f"파괴할 위치들: {groups_to_destroy}")
            
            # 파괴할 그룹에 속한 크리스탈들을 정확히 제거
            for destroy_layer, destroy_part in groups_to_destroy:
                # 이 크리스탈이 이동했는지 확인
                if (destroy_layer, destroy_part) in crystal_movements:
                    # 이동한 크리스탈 - 새 위치에서 제거
                    new_layer, new_part = crystal_movements[(destroy_layer, destroy_part)]
                    if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                        print(f"이동한 크리스탈 제거: 층{new_layer} 위치{new_part} (원래 층{destroy_layer})")
                    result_layers[new_layer][new_part] = ('-', '-')
                    crystal_info['destroyed_crystals'] += 1
                else:
                    # 이동하지 않은 크리스탈 - 원래 위치에서 제거
                    if (destroy_layer < len(result_layers) and 
                        result_layers[destroy_layer][destroy_part][0] == 'c'):
                        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                            print(f"그룹 크리스탈 제거: 층{destroy_layer} 위치{destroy_part}")
                        result_layers[destroy_layer][destroy_part] = ('-', '-')
                        crystal_info['destroyed_crystals'] += 1
        
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"크리스탈 제거 후: {self.layers_to_code(result_layers)}")
        
        # 6. 빈 층 제거
        final_layers = []
        for layer in result_layers:
            if any(part[0] != '-' for part in layer):
                final_layers.append(layer)
        
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"최종 결과: {self.layers_to_code(final_layers)}")
            print(f"=== 중력 적용 완료 ===")
        
        return final_layers if final_layers else [], crystal_info
    
    def apply_basic_gravity(self, layers):
        """기본 중력 적용 (크리스탈 특수 처리 없이) - 반복적 적용"""
        if not layers:
            return []
        
        current_layers = [list(layer) for layer in layers]  # 복사본 생성
        iteration = 0
        
        while True:
            iteration += 1
            if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                print(f"\n=== 중력 반복 {iteration} ===")
                print(f"현재 상태: {self.layers_to_code(current_layers)}")
            
            # 한 번의 중력 적용
            new_layers = self.apply_single_gravity_step(current_layers)
            
            # 변화가 있었는지 확인
            if self.layers_to_code(new_layers) == self.layers_to_code(current_layers):
                if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                    print(f"더 이상 변화 없음. 최종 결과: {self.layers_to_code(new_layers)}")
                break
            
            current_layers = new_layers
            
            # 무한 루프 방지
            if iteration > 10:
                if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                    print("최대 반복 횟수 도달")
                break
        
        return current_layers

    def apply_single_gravity_step(self, layers):
        """한 번의 중력 적용 단계"""
        # 1. 전체 구조에서 3D 크리스탈 그룹들 먼저 찾기
        all_crystal_positions = set()
        for layer_idx, layer in enumerate(layers):
            for part_idx, (shape_type, color) in enumerate(layer):
                if shape_type == 'c':
                    all_crystal_positions.add((layer_idx, part_idx))
        
        crystal_3d_groups = self.find_3d_crystal_groups(layers, all_crystal_positions)
        if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
            print(f"3D 크리스탈 그룹들: {crystal_3d_groups}")
        
        # 2. 지지되는 3D 크리스탈 그룹들 확인
        supported_crystal_positions = set()
        for group in crystal_3d_groups:
            group_supported = False
            for layer_idx, part_idx in group:
                # 이 크리스탈 위치가 지지되는지 확인
                if self.is_crystal_position_supported(layers, layer_idx, part_idx):
                    group_supported = True
                    if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                        print(f"3D 크리스탈 그룹 지지됨: {group} (위치 ({layer_idx}, {part_idx})에서 지지)")
                    break
            
            if group_supported:
                supported_crystal_positions.update(group)
            else:
                if not hasattr(self, 'run_test_silent') or not self.run_test_silent:
                    print(f"3D 크리스탈 그룹 떨어짐: {group}")
        
        # 3. 결과 구조 구성
        result_layers = []
        
        # 아래부터 위로 각 층을 처리
        for layer_idx in range(len(layers)):
            current_layer = list(layers[layer_idx])
            
            if layer_idx == 0:
                # 맨 아래층은 항상 그대로 (단, 지지되지 않는 크리스탈 제외)
                new_layer = []
                for part_idx, part in enumerate(current_layer):
                    if (part[0] == 'c' and 
                        (layer_idx, part_idx) not in supported_crystal_positions):
                        new_layer.append(('-', '-'))  # 지지되지 않는 크리스탈 제거
                    else:
                        new_layer.append(part)
                result_layers.append(new_layer)
            else:
                # 위층들은 중력 적용
                # 크리스탈이 아닌 도형들만 기존 로직으로 처리
                non_crystal_layer = []
                falling_parts = []
                
                for part_idx, (shape_type, color) in enumerate(current_layer):
                    if shape_type == 'c':
                        # 크리스탈은 3D 그룹 지지 여부에 따라 처리
                        if (layer_idx, part_idx) in supported_crystal_positions:
                            non_crystal_layer.append((shape_type, color))
                        else:
                            non_crystal_layer.append(('-', '-'))
                            # 지지되지 않는 크리스탈은 떨어뜨리기
                            falling_parts.append((part_idx, (shape_type, color)))
                    else:
                        non_crystal_layer.append((shape_type, color))
                
                # 비-크리스탈 도형들의 연결 그룹 처리
                temp_layer = [(s, c) if s != 'c' else ('-', '-') for s, c in non_crystal_layer]
                connected_groups = self.find_connected_groups(temp_layer)
                
                new_layer = [('-', '-')] * 4
                
                for group in connected_groups:
                    group_supported = False
                    
                    for part_idx in group:
                        if temp_layer[part_idx][0] != '-' and self.has_support_below(result_layers, part_idx):
                            group_supported = True
                            break
                    
                    if group_supported:
                        # 지지되는 그룹은 현재 위치에 유지
                        for part_idx in group:
                            if temp_layer[part_idx][0] != '-':
                                new_layer[part_idx] = temp_layer[part_idx]
                    else:
                        # 지지되지 않는 그룹은 떨어뜨리기
                        for part_idx in group:
                            if temp_layer[part_idx][0] != '-':
                                falling_parts.append((part_idx, temp_layer[part_idx]))
                
                # 지지되는 크리스탈들 추가
                for part_idx, (shape_type, color) in enumerate(current_layer):
                    if (shape_type == 'c' and 
                        (layer_idx, part_idx) in supported_crystal_positions):
                        new_layer[part_idx] = (shape_type, color)
                
                # 떨어지는 부분들을 아래층들에 배치
                for part_idx, part in falling_parts:
                    target_layer_idx = self.find_landing_layer(result_layers, part_idx)
                    
                    while len(result_layers) <= target_layer_idx:
                        result_layers.append([('-', '-')] * 4)
                    
                    result_layers[target_layer_idx][part_idx] = part
                
                # 빈 층이 아니면 추가
                if any(part[0] != '-' for part in new_layer):
                    result_layers.append(new_layer)
        
        # 빈 층 제거
        final_layers = []
        for layer in result_layers:
            if any(part[0] != '-' for part in layer):
                final_layers.append(layer)
        
        return final_layers
    
    def is_crystal_position_supported(self, layers, crystal_layer_idx, crystal_part_idx):
        """특정 크리스탈 위치가 지지되는지 확인"""
        # 아래층들에서 지지점 찾기
        for check_layer_idx in range(crystal_layer_idx):
            check_layer = layers[check_layer_idx]
            if check_layer[crystal_part_idx][0] != '-':
                # 아래층에 지지점 있음 (핀 포함)
                return True
        return False
    
    def find_connected_groups(self, layer):
        """층에서 연결된 그룹들을 찾기"""
        visited = set()
        groups = []
        
        for part_idx in range(4):
            if part_idx not in visited and layer[part_idx][0] != '-':
                # BFS로 연결된 그룹 찾기
                group = set()
                queue = [part_idx]
                
                while queue:
                    current_idx = queue.pop(0)
                    if current_idx in visited:
                        continue
                    
                    visited.add(current_idx)
                    group.add(current_idx)
                    
                    # 핀이 아닌 경우만 인접한 부분들과 연결
                    if layer[current_idx][0] != 'P':
                        for adj_idx in self.get_adjacent_positions(current_idx):
                            if (adj_idx not in visited and 
                                layer[adj_idx][0] != '-' and 
                                layer[adj_idx][0] != 'P'):  # 인접한 것도 핀이 아니어야 함
                                queue.append(adj_idx)
                
                if group:
                    groups.append(group)
        
        # 핀들은 각각 개별 그룹으로 처리
        for part_idx in range(4):
            if layer[part_idx][0] == 'P' and part_idx not in visited:
                groups.append({part_idx})
        
        return groups
    
    def has_support_below(self, existing_layers, part_idx):
        """특정 사분면 아래에 지지점이 있는지 확인 - 핀도 지지 능력 있음"""
        # 아래층들을 위에서부터 확인
        for layer_idx in range(len(existing_layers) - 1, -1, -1):
            shape_type = existing_layers[layer_idx][part_idx][0]
            if shape_type != '-':
                # 핀(P)도 지지 능력 있음
                return True
        return False
    
    def find_landing_layer(self, existing_layers, part_idx):
        """떨어질 수 있는 층 인덱스 찾기"""
        # 아래부터 위로 확인하여 빈 공간이 있는 가장 아래 층 찾기
        for layer_idx in range(len(existing_layers)):
            if existing_layers[layer_idx][part_idx][0] == '-':
                return layer_idx
        
        # 모든 층이 차있으면 새 층 생성
        return len(existing_layers)
    
    def get_adjacent_positions(self, part_idx):
        """인접한 위치들 반환 (시계방향: 0=오른쪽위, 1=오른쪽아래, 2=왼쪽아래, 3=왼쪽위)"""
        adjacents = {
            0: [1, 3],  # 오른쪽위 -> 오른쪽아래, 왼쪽위
            1: [0, 2],  # 오른쪽아래 -> 오른쪽위, 왼쪽아래
            2: [1, 3],  # 왼쪽아래 -> 오른쪽아래, 왼쪽위
            3: [0, 2]   # 왼쪽위 -> 오른쪽위, 왼쪽아래
        }
        return adjacents.get(part_idx, [])
    
    def layers_to_code(self, layers):
        """층 데이터를 모양 코드로 변환"""
        if not layers:
            return ""
        
        layer_codes = []
        for layer in layers:
            layer_code = ""
            for shape_type, color in layer:
                if shape_type == '-':
                    layer_code += "--"
                else:
                    layer_code += shape_type + color
            layer_codes.append(layer_code)
        
        return ":".join(layer_codes)

    def check_crystal_3d_support(self, layers, current_layer_idx, group, result_layers):
        """크리스탈 그룹이 3D 연결성을 통해 지지되는지 확인"""
        current_layer = layers[current_layer_idx]
        
        # 그룹 내 크리스탈들 확인
        for part_idx in group:
            if current_layer[part_idx][0] == 'c':
                # 같은 사분면의 아래층들에 크리스탈이 있는지 확인
                for check_layer_idx in range(len(result_layers)):
                    if result_layers[check_layer_idx][part_idx][0] == 'c':
                        # 아래층에 연결된 크리스탈이 있으면 지지됨
                        print(f"크리스탈 3D 지지: 층{current_layer_idx} 위치{part_idx} -> 층{check_layer_idx} 지지")
                        return True
                
                # 다른 사분면의 연결된 크리스탈들도 확인
                for adj_part_idx in self.get_adjacent_positions(part_idx):
                    if current_layer[adj_part_idx][0] == 'c':
                        # 인접한 크리스탈이 아래층과 연결되어 있는지 확인
                        for check_layer_idx in range(len(result_layers)):
                            if result_layers[check_layer_idx][adj_part_idx][0] == 'c':
                                print(f"크리스탈 3D 지지: 층{current_layer_idx} 위치{part_idx} -> 인접{adj_part_idx} -> 층{check_layer_idx}")
                                return True
        
        return False

    def find_3d_crystal_groups(self, layers, crystal_positions):
        """3D로 연결된 크리스탈 그룹들 찾기"""
        visited = set()
        groups = []
        
        for crystal_pos in crystal_positions:
            if crystal_pos not in visited:
                # BFS로 3D 연결된 크리스탈 그룹 찾기
                group = set()
                queue = [crystal_pos]
                
                while queue:
                    current_pos = queue.pop(0)
                    if current_pos in visited:
                        continue
                    
                    visited.add(current_pos)
                    group.add(current_pos)
                    
                    # 3D로 인접한 크리스탈들 찾기
                    for neighbor_pos in self.get_3d_crystal_neighbors(layers, current_pos):
                        if neighbor_pos not in visited and neighbor_pos in crystal_positions:
                            queue.append(neighbor_pos)
                
                if group:
                    groups.append(group)
        
        return groups
    
    def get_3d_crystal_neighbors(self, layers, crystal_pos):
        """크리스탈의 3D 인접 위치들 반환 (수평 + 수직)"""
        layer_idx, part_idx = crystal_pos
        neighbors = []
        
        # 1. 수평 인접 (같은 층의 인접한 사분면)
        for adj_part_idx in self.get_adjacent_positions(part_idx):
            neighbors.append((layer_idx, adj_part_idx))
        
        # 2. 수직 인접 (위아래 층의 같은 사분면)
        if layer_idx > 0:  # 아래층
            neighbors.append((layer_idx - 1, part_idx))
        if layer_idx < len(layers) - 1:  # 위층
            neighbors.append((layer_idx + 1, part_idx))
        
        return neighbors

    def run_all_tests(self):
        """모든 테스트를 실행하고 결과를 표시"""
        self.run_test_silent = True  # 조용한 모드 플래그
        
        all_results = []
        total_tests = 0
        passed_tests = 0
        
        print("\n" + "="*60)
        print("자동 테스트 시작")
        print("="*60)
        
        # 기본 테스트 (중력 적용 안함)
        basic_results = self.run_test_category("기본 모양", self.test_cases["basic"], apply_gravity=False)
        all_results.extend(basic_results)
        
        # 중력 테스트 (중력 적용)
        gravity_results = self.run_test_category("중력 테스트", self.test_cases["gravity"], apply_gravity=True)
        all_results.extend(gravity_results)
        
        # 크리스탈 테스트 (중력 적용)
        crystal_results = self.run_test_category("크리스탈 테스트", self.test_cases["crystal"], apply_gravity=True)
        all_results.extend(crystal_results)
        
        # 복합 테스트 (중력 적용)
        complex_results = self.run_test_category("복합 테스트", self.test_cases["complex"], apply_gravity=True)
        all_results.extend(complex_results)
        
        # 결과 통계
        total_tests = len(all_results)
        passed_tests = sum(1 for result in all_results if result['passed'])
        
        print("\n" + "="*60)
        print("테스트 완료")
        print("="*60)
        print(f"총 테스트: {total_tests}")
        print(f"성공: {passed_tests}")
        print(f"실패: {total_tests - passed_tests}")
        print(f"성공률: {passed_tests/total_tests*100:.1f}%")
        
        # 실패한 테스트 목록
        failed_tests = [result for result in all_results if not result['passed']]
        if failed_tests:
            print("\n❌ 실패한 테스트:")
            for test in failed_tests:
                print(f"  - {test['name']}")
                print(f"    입력: {test['input']}")
                print(f"    예상: {test['expected']}")
                print(f"    실제: {test['actual']}")
                print()
        else:
            print("\n✅ 모든 테스트 통과!")
        
        # UI에 결과 표시
        self.display_test_results(all_results, passed_tests, total_tests)
        self.run_test_silent = False
    
    def run_test_category(self, category_name, test_cases, apply_gravity=False):
        """특정 카테고리의 테스트 실행"""
        print(f"\n--- {category_name} ---")
        results = []
        
        for i, (name, code, expected) in enumerate(test_cases):
            print(f"테스트 {i+1}/{len(test_cases)}: {name}")
            
            # 테스트 실행
            self.shape_entry.delete(0, tk.END)
            self.shape_entry.insert(0, code)
            self.visualize_shape()
            
            # 중력 적용 여부 결정
            if apply_gravity:
                # 중력 적용 전 상태 저장
                original_layers = [list(layer) for layer in self.current_layers]
                new_layers, crystal_info = self.apply_gravity_with_crystals(original_layers)
                actual_result = self.layers_to_code(new_layers)
            else:
                actual_result = self.layers_to_code(self.current_layers)
            
            # 결과 비교
            passed = actual_result == expected
            status = "✅ 성공" if passed else "❌ 실패"
            
            print(f"  입력: {code}")
            print(f"  예상: {expected}")
            print(f"  실제: {actual_result}")
            print(f"  결과: {status}")
            
            results.append({
                'name': name,
                'input': code,
                'expected': expected,
                'actual': actual_result,
                'passed': passed,
                'category': category_name
            })
        
        return results
    
    def run_gravity_tests(self):
        """중력 관련 테스트만 실행"""
        self.run_test_silent = True
        
        all_results = []
        
        print("\n" + "="*60)
        print("중력 테스트 시작")
        print("="*60)
        
        # 중력 테스트들만 실행
        gravity_results = self.run_test_category("중력 테스트", self.test_cases["gravity"], apply_gravity=True)
        crystal_results = self.run_test_category("크리스탈 테스트", self.test_cases["crystal"], apply_gravity=True)
        complex_results = self.run_test_category("복합 테스트", self.test_cases["complex"], apply_gravity=True)
        
        all_results.extend(gravity_results)
        all_results.extend(crystal_results)
        all_results.extend(complex_results)
        
        # 결과 통계
        total_tests = len(all_results)
        passed_tests = sum(1 for result in all_results if result['passed'])
        
        print("\n" + "="*60)
        print("중력 테스트 완료")
        print("="*60)
        print(f"총 테스트: {total_tests}")
        print(f"성공: {passed_tests}")
        print(f"실패: {total_tests - passed_tests}")
        print(f"성공률: {passed_tests/total_tests*100:.1f}%")
        
        # 실패한 테스트 목록
        failed_tests = [result for result in all_results if not result['passed']]
        if failed_tests:
            print("\n❌ 실패한 테스트:")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['expected']} ≠ {test['actual']}")
        else:
            print("\n✅ 모든 중력 테스트 통과!")
        
        # UI에 결과 표시
        self.display_test_results(all_results, passed_tests, total_tests)
        self.run_test_silent = False
    
    def display_test_results(self, results, passed, total):
        """UI에 테스트 결과 표시"""
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        
        # 요약 정보
        success_rate = passed/total*100 if total > 0 else 0
        summary = f"테스트 결과: {passed}/{total} 통과 ({success_rate:.1f}%)\n"
        
        # 실패한 테스트 목록
        failed_tests = [r for r in results if not r['passed']]
        if failed_tests:
            summary += f"\n❌ 실패한 테스트 ({len(failed_tests)}개):\n"
            for test in failed_tests:
                summary += f"• {test['name']}\n"
                summary += f"  예상: {test['expected']}\n"
                summary += f"  실제: {test['actual']}\n\n"
        else:
            summary += "\n✅ 모든 테스트 통과!"
        
        self.info_text.insert("1.0", summary)
        self.info_text.config(state=tk.DISABLED)

    def apply_pin_pusher(self):
        """핀 푸셔를 적용"""
        if not self.current_layers:
            messagebox.showwarning("경고", "먼저 모양을 시각화해주세요.")
            return

        try:
            original_code = self.shape_entry.get().strip()
            original_layers = [list(layer) for layer in self.current_layers] # 원본 레이어 복사

            print(f"=== 핀 푸셔 적용 시작 ===")
            print(f"원본: {original_code}")

            # 1. 새로운 맨 아래층 (핀 층) 생성
            new_bottom_layer = []
            if original_layers:
                bottom_layer = original_layers[0] # 원래 맨 아래층
                for shape_type, color in bottom_layer:
                    if shape_type != '-':
                        new_bottom_layer.append(('P', '-')) # 핀 추가
                    else:
                        new_bottom_layer.append(('-', '-')) # 비어있으면 유지
            else:
                 new_bottom_layer = [('-', '-')] * 4 # 원본 레이어가 없으면 빈 핀 층 생성

            # 2. 기존 층을 위로 이동 (새로운 맨 아래층 위에 붙임)
            processed_layers = [new_bottom_layer] + original_layers

            print(f"핀 층 추가 및 이동 후: {self.layers_to_code(processed_layers)}")

            # 3. 층 제한 (4층 초과 시 위에서부터 제거)
            max_layers = 4
            if len(processed_layers) > max_layers:
                while len(processed_layers) > max_layers:
                    # 가장 위층 (리스트의 마지막 요소) 제거
                    removed_layer = processed_layers.pop() 
                    print(f"4층 제한으로 인해 가장 위층 제거됨: {self.layers_to_code([removed_layer])}")
            
            print(f"층 제한 적용 후: {self.layers_to_code(processed_layers)}")

            # 4. 중력 적용 (크리스탈 로직 포함)
            # 핀 푸셔 적용 후 중력은 항상 조용한 모드가 아님
            original_run_test_silent = getattr(self, 'run_test_silent', False)
            self.run_test_silent = False 
            final_layers, crystal_info = self.apply_gravity_with_crystals(processed_layers)
            self.run_test_silent = original_run_test_silent # 원상 복구

            # 빈 층 제거는 apply_gravity_with_crystals에서 이미 처리됨

            new_code = self.layers_to_code(final_layers)

            print(f"중력 적용 후 최종: {new_code}")
            print(f"=== 핀 푸셔 적용 완료 ===")

            # UI 업데이트
            self.shape_entry.delete(0, tk.END)
            self.shape_entry.insert(0, new_code)

            self.current_layers = final_layers
            self.selected_layer = None
            self.update_layer_buttons()
            self.draw_shape(final_layers)

            info_text = f"핀 푸셔 적용 완료!\n이전: {original_code}\n결과: {new_code}\n층 개수: {len(final_layers)}"
            if crystal_info['moved_crystals'] > 0:
                info_text += f"\n💥 크리스탈 {crystal_info['moved_crystals']}개 이동으로 인한 파괴!"
            if crystal_info['destroyed_crystals'] > 0:
                info_text += f"\n🔗 연쇄 파괴: {crystal_info['destroyed_crystals']}개 크리스탈 소멸"
            if len(original_layers) + (1 if original_layers else 0) > max_layers: # 핀 층 추가 후 4층 초과시
                 info_text += f"\n⚠️ {len(original_layers) + (1 if original_layers else 0) - max_layers}개 층이 4층 제한으로 인해 제거되었습니다."


            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete("1.0", tk.END)
            self.info_text.insert("1.0", info_text)
            self.info_text.config(state=tk.DISABLED)


        except Exception as e:
            messagebox.showerror("오류", f"핀 푸셔 적용 중 오류 발생: {str(e)}")

    def rotate_shape(self, degrees):
        """모양을 주어진 각도(90, 180, 270)로 시계 방향 회전"""
        if not self.current_layers:
            messagebox.showwarning("경고", "먼저 모양을 시각화해주세요.")
            return

        if degrees not in [90, 180, 270]:
            messagebox.showerror("오류", "지원되지 않는 회전 각도입니다. 90, 180, 270만 가능합니다.")
            return

        try:
            original_code = self.shape_entry.get().strip()
            rotated_layers = []
            
            # 각 층별로 회전 적용
            for layer in self.current_layers:
                rotated_layer = [None] * 4
                for part_idx in range(4):
                    # 새로운 위치 계산 (시계 방향 회전: 0->1->2->3->0)
                    if degrees == 90:
                        new_part_idx = (part_idx + 1) % 4
                    elif degrees == 180:
                        new_part_idx = (part_idx + 2) % 4
                    elif degrees == 270:
                        new_part_idx = (part_idx + 3) % 4 # (part_idx - 1) % 4 와 동일
                    
                    rotated_layer[new_part_idx] = layer[part_idx]
                    
                rotated_layers.append(rotated_layer)
                
            self.current_layers = rotated_layers
            new_code = self.layers_to_code(self.current_layers)
            
            # UI 업데이트
            self.shape_entry.delete(0, tk.END)
            self.shape_entry.insert(0, new_code)
            self.selected_layer = None
            self.update_layer_buttons()
            self.draw_shape(self.current_layers)
            
            info_text = f"{degrees}° 회전 적용 완료!\n이전: {original_code}\n결과: {new_code}\n층 개수: {len(self.current_layers)}"
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete("1.0", tk.END)
            self.info_text.insert("1.0", info_text)
            self.info_text.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("오류", f"회전 적용 중 오류 발생: {str(e)}")

    def apply_half_destroyer(self):
        """모양의 서쪽 절반 (3,4 사분면)을 파괴하고 중력 적용"""
        if not self.current_layers:
            messagebox.showwarning("경고", "먼저 모양을 시각화해주세요.")
            return

        try:
            original_code = self.shape_entry.get().strip()
            processed_layers = [list(layer) for layer in self.current_layers] # 복사본 생성

            print(f"=== 하프 디스트로이어 적용 시작 ===")
            print(f"원본: {original_code}")

            # 각 층별로 서쪽 절반 (인덱스 2와 3) 파괴
            for layer in processed_layers:
                # 인덱스 2: 왼쪽 아래, 인덱스 3: 왼쪽 위
                layer[2] = ('-', '-')
                layer[3] = ('-', '-')

            print(f"절반 파괴 후: {self.layers_to_code(processed_layers)}")

            # 중력 적용 (크리스탈 로직 포함)
            # 하프 디스트로이어 적용 후 중력은 항상 조용한 모드가 아님
            original_run_test_silent = getattr(self, 'run_test_silent', False)
            self.run_test_silent = False 
            final_layers, crystal_info = self.apply_gravity_with_crystals(processed_layers)
            self.run_test_silent = original_run_test_silent # 원상 복구

            new_code = self.layers_to_code(final_layers)

            print(f"중력 적용 후 최종: {new_code}")
            print(f"=== 하프 디스트로이어 적용 완료 ===")

            # UI 업데이트
            self.shape_entry.delete(0, tk.END)
            self.shape_entry.insert(0, new_code)

            self.current_layers = final_layers
            self.selected_layer = None
            self.update_layer_buttons()
            self.draw_shape(final_layers)

            info_text = f"절단 (하프) 적용 완료!\n이전: {original_code}\n결과: {new_code}\n층 개수: {len(final_layers)}"
            if crystal_info['moved_crystals'] > 0:
                info_text += f"\n💥 크리스탈 {crystal_info['moved_crystals']}개 이동으로 인한 파괴!"
            if crystal_info['destroyed_crystals'] > 0:
                info_text += f"\n🔗 연쇄 파괴: {crystal_info['destroyed_crystals']}개 크리스탈 소멸"

            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete("1.0", tk.END)
            self.info_text.insert("1.0", info_text)
            self.info_text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("오류", f"절단 (하프) 적용 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ShapezVisualizer(root)
    root.mainloop()

