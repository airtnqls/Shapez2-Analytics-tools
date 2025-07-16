import sys
import json
from typing import List, Tuple, Optional
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QFrame, QGridLayout, QTextEdit, QComboBox, QScrollArea,
    QGroupBox, QListWidget, QListWidgetItem, QProgressDialog, QCheckBox,
    QTabWidget, QMainWindow, QProgressBar, QSizePolicy, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QMenu, QTabBar
)
from PyQt6.QtGui import QFont, QColor, QIntValidator, QKeySequence, QShortcut, QDrag
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QMimeData
import numpy as np

# pyqtgraph 임포트
try:
    import pyqtgraph as pg
except ImportError:
    print("PyQtGraph가 설치되지 않았습니다. 'pip install pyqtgraph'를 실행해주세요.")
    pg = None

# shape.py에서 백엔드 클래스를 임포트합니다.
from shape import Quadrant, Shape, ReverseTracer, InterruptedError

# ==============================================================================
#  GUI 프론트엔드
# ==============================================================================

class OriginFinderThread(QThread):
    """기원 찾기 연산을 백그라운드에서 수행하는 스레드"""
    progress = pyqtSignal(int, int, str)
    candidate_found = pyqtSignal()
    finished = pyqtSignal(list)
    log_message = pyqtSignal(str)
    
    LOG_BUFFER_SIZE = 50

    def __init__(self, target_shape, search_depth, max_physics_height, log_enabled=False):
        super().__init__()
        self.target_shape = target_shape
        self.search_depth = search_depth
        self.max_physics_height = max_physics_height
        self.is_cancelled = False
        self.log_enabled = log_enabled
        self.candidates = []
        self.log_buffer = []

    def log(self, msg: str):
        if self.log_enabled:
            self.log_buffer.append(msg)
            if len(self.log_buffer) >= self.LOG_BUFFER_SIZE:
                self._flush_log_buffer()

    def _flush_log_buffer(self):
        if self.log_buffer:
            self.log_message.emit("\n".join(self.log_buffer))
            self.log_buffer.clear()

    def run(self):
        total_steps = 4 + (4 * 2) + 1
        step = 0

        def update_progress(message):
            nonlocal step
            step += 1
            if self.is_cancelled: raise InterruptedError
            self.progress.emit(step, total_steps, message)

        def add_candidates(new_cands):
            if new_cands:
                self._flush_log_buffer()
                is_first_candidate = not self.candidates
                self.candidates.extend(new_cands)
                if is_first_candidate:
                    self.candidate_found.emit()

        try:
            update_progress("물리 적용 역연산 중...")
            self.log("\n--- 물리 적용 역연산 탐색 ---")
            cands = ReverseTracer.inverse_apply_physics(self.target_shape, self.search_depth, self.max_physics_height, self)
            add_candidates(cands)
            if self.is_cancelled: raise InterruptedError
            
            update_progress("핀 푸셔 역연산 중...")
            self.log("\n--- 핀 푸셔 역연산 탐색 ---")
            cands = ReverseTracer.inverse_push_pin(self.target_shape, self.search_depth, self.max_physics_height, self)
            add_candidates(cands)
            if self.is_cancelled: raise InterruptedError

            update_progress("크리스탈 생성기 역연산 중...")
            self.log("\n--- 크리스탈 생성기 역연산 탐색 ---")
            cands = ReverseTracer.inverse_crystal_generator(self.target_shape, self.search_depth, self)
            add_candidates(cands)
            if self.is_cancelled: raise InterruptedError
            
            update_progress("스태커 역연산 중...")
            self.log("\n--- 스태커 역연산 탐색 ---")
            cands = ReverseTracer.inverse_stack(self.target_shape, self.search_depth, self)
            add_candidates(cands)
            if self.is_cancelled: raise InterruptedError

            for i in range(4):
                rotated_target = self.target_shape.copy()
                for _ in range(i): rotated_target = rotated_target.rotate(clockwise=True)
                
                update_progress(f"{i+1}/4 회전: 절반 파괴기 역연산")
                self.log(f"\n--- {i+1}/4 회전: 절반 파괴기 역연산 탐색 ---")
                cands_dh = ReverseTracer.inverse_destroy_half(rotated_target, i, self.search_depth, self)
                add_candidates(cands_dh)
                if self.is_cancelled: raise InterruptedError
                
                update_progress(f"{i+1}/4 회전: 스와퍼 역연산")
                self.log(f"\n--- {i+1}/4 회전: 스와퍼 역연산 탐색 ---")
                cands_sw = ReverseTracer.inverse_swap(rotated_target, i, self.search_depth, self)
                add_candidates(cands_sw)
                if self.is_cancelled: raise InterruptedError

            update_progress("중복 후보 제거 중...")
            self.log("\n--- 중복 후보 제거 ---")
            unique_candidates = []
            seen_canonical_keys = set()
            for op_name, origin_shape in self.candidates:
                if self.is_cancelled: raise InterruptedError
                key = ReverseTracer._get_canonical_key(op_name, origin_shape)
                if key not in seen_canonical_keys:
                    seen_canonical_keys.add(key)
                    unique_candidates.append((op_name, origin_shape))
            
            if not self.is_cancelled:
                self.finished.emit(unique_candidates)

        except InterruptedError:
            self.log("\n--- 탐색 중단 ---")
            unique_candidates = []
            seen_canonical_keys = set()
            for op_name, origin_shape in self.candidates:
                key = ReverseTracer._get_canonical_key(op_name, origin_shape)
                if key not in seen_canonical_keys:
                    seen_canonical_keys.add(key)
                    unique_candidates.append((op_name, origin_shape))
            self.finished.emit(unique_candidates)
        finally:
            self._flush_log_buffer()

    def cancel(self):
        self.is_cancelled = True

COLOR_MAP = {'r':'#E33','g':'#3E3','b':'#33E','m':'#E3E','c':'#3EE','y':'#EE3','u':'#BBB','w':'#FFF','C':'#CDD'}

class QuadrantWidget(QLabel):
    def __init__(self, quadrant: Optional[Quadrant]):
        super().__init__(); self.setFixedSize(30, 30); self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("맑은 고딕", 12)
        font.setBold(True)
        self.setFont(font)
        if quadrant:
            color_code = QColor(COLOR_MAP.get(quadrant.color, '#FFF'))
            if quadrant.shape == 'c':
                 base_color = QColor(COLOR_MAP['C'])
                 paint_color = QColor(COLOR_MAP.get(quadrant.color, '#FFF'))
                 self.setStyleSheet(f"""
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0.2, y2:0.6, 
                        stop:0 {base_color.name()}, stop:0.5 {base_color.name()}, stop:0.51 {paint_color.name()}, stop:1 {paint_color.name()});
                    color: black; border: 1px solid #555;
                 """)
                 self.setText('◆')
            else:
                 self.setStyleSheet(f"background-color: {color_code.name()}; color: black; border: 1px solid #555;")
                 self.setText(quadrant.shape.upper())
        else: self.setStyleSheet("background-color: #333; border: 1px solid #555;")

class ShapeWidget(QFrame):
    def __init__(self, shape: Shape):
        super().__init__(); self.setFrameShape(QFrame.Shape.StyledPanel); layout = QVBoxLayout(self)
        layout.setSpacing(1); layout.setContentsMargins(3, 3, 3, 3)
        layout.setAlignment(Qt.AlignmentFlag.AlignBottom)  # 아래 정렬
        
        clean_shape = shape.copy()
        while len(clean_shape.layers) > 0 and clean_shape.layers[-1].is_empty():
            clean_shape.layers.pop()

        if not clean_shape.layers:
            layout.addWidget(QLabel("완전히 파괴됨"))
            return

        # 층을 위에서 아래로 표시하기 위해 역순으로 처리
        for i in reversed(range(len(clean_shape.layers))):
            layer = clean_shape.layers[i]
            
            # 층 번호와 사분면을 가로로 배치하기 위한 컨테이너
            layer_row = QHBoxLayout()
            layer_row.setSpacing(2)
            
            # 층 번호 라벨 (왼쪽에 표시)
            layer_label = QLabel(f"<b>{i+1}F</b>")
            layer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layer_label.setFixedWidth(30)  # 고정 너비 설정
            layer_row.addWidget(layer_label)
            
            # 각 층의 사분면을 담는 박스 컨테이너
            layer_container = QFrame()
            layer_container.setFrameShape(QFrame.Shape.NoFrame)
            layer_container.setLineWidth(0)
            layer_layout = QVBoxLayout(layer_container)
            layer_layout.setSpacing(0)
            layer_layout.setContentsMargins(1, 1, 1, 1)
            
            # 1x4 가로 배치로 사분면 배치 (1사분면부터 4사분면까지)
            quad_layout = QHBoxLayout()
            quad_layout.setSpacing(0)
            # 사분면 순서: 1=TR, 2=TL, 3=BR, 4=BL (시계방향)
            quad_layout.addWidget(QuadrantWidget(layer.quadrants[0]))  # 1사분면 (TR)
            quad_layout.addWidget(QuadrantWidget(layer.quadrants[1]))  # 2사분면 (BR)
            quad_layout.addWidget(QuadrantWidget(layer.quadrants[2]))  # 3사분면 (BL)
            quad_layout.addWidget(QuadrantWidget(layer.quadrants[3]))  # 4사분면 (TL)
            
            layer_layout.addLayout(quad_layout)
            layer_row.addWidget(layer_container)
            
            layout.addLayout(layer_row)

class InputHistory:
    """입력 필드의 히스토리를 관리하는 클래스 (A, B 통합)"""
    def __init__(self, max_size=100):
        self.max_size = max_size
        self.history = []
        self.current_index = -1
        
    def add_entry(self, input_a, input_b):
        """새로운 항목을 히스토리에 추가"""
        entry = (input_a, input_b)
        
        # 현재 항목과 동일하면 추가하지 않음
        if self.history and self.current_index >= 0 and self.history[self.current_index] == entry:
            return
            
        # 현재 위치 이후의 히스토리 삭제 (새로운 분기 생성)
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
            
        self.history.append(entry)
        self.current_index = len(self.history) - 1
        
        # 최대 크기 초과 시 오래된 항목 제거
        if len(self.history) > self.max_size:
            self.history.pop(0)
            self.current_index -= 1
            
    def can_undo(self):
        """Undo 가능 여부 확인"""
        return self.current_index > 0
        
    def can_redo(self):
        """Redo 가능 여부 확인"""
        return self.current_index < len(self.history) - 1
        
    def undo(self):
        """이전 항목으로 이동"""
        if self.can_undo():
            self.current_index -= 1
            return self.history[self.current_index]
        return None
        
    def redo(self):
        """다음 항목으로 이동"""
        if self.can_redo():
            self.current_index += 1
            return self.history[self.current_index]
        return None
        
    def get_current(self):
        """현재 항목 반환"""
        if 0 <= self.current_index < len(self.history):
            return self.history[self.current_index]
        return ("", "")

class DataHistory:
    """데이터 탭의 히스토리를 관리하는 클래스"""
    def __init__(self, max_size=50):
        self.max_size = max_size
        self.history = []
        self.current_index = -1
        
    def add_entry(self, data, operation_name=""):
        """새로운 데이터 상태를 히스토리에 추가"""
        # 데이터를 복사하여 저장 (참조 문제 방지)
        entry = (data.copy(), operation_name)
        
        # 현재 항목과 동일하면 추가하지 않음
        if self.history and self.current_index >= 0 and self.history[self.current_index][0] == data:
            return
            
        # 현재 위치 이후의 히스토리 삭제 (새로운 분기 생성)
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
            
        self.history.append(entry)
        self.current_index = len(self.history) - 1
        
        # 최대 크기 초과 시 오래된 항목 제거
        if len(self.history) > self.max_size:
            self.history.pop(0)
            self.current_index -= 1
            
    def can_undo(self):
        """Undo 가능 여부 확인"""
        return self.current_index > 0
        
    def can_redo(self):
        """Redo 가능 여부 확인"""
        return self.current_index < len(self.history) - 1
        
    def undo(self):
        """이전 항목으로 이동"""
        if self.can_undo():
            self.current_index -= 1
            return self.history[self.current_index]
        return None
        
    def redo(self):
        """다음 항목으로 이동"""
        if self.can_redo():
            self.current_index += 1
            return self.history[self.current_index]
        return None
        
    def get_current(self):
        """현재 항목 반환"""
        if 0 <= self.current_index < len(self.history):
            return self.history[self.current_index]
        return ([], "")

class ShapezGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shapez 2 분석 도구")
        self.setGeometry(100, 100, 1400, 800)
        self.setMinimumSize(1200, 700)
        
        # 기본 폰트를 맑은 고딕으로 설정
        default_font = QFont("맑은 고딕", 9)
        QApplication.instance().setFont(default_font)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 히스토리 관리 객체 생성 (A, B 통합)
        self.input_history = InputHistory(100)
        self.history_update_in_progress = False  # 히스토리 업데이트 중 플래그
        
        self.initUI()
        self.origin_finder_thread = None
        self.total_training_episodes = 0
        
        # 출력 결과 추적 변수
        self.current_outputs = []  # [(title, shape), ...] 형태로 저장

    def initUI(self):
        main_layout = QVBoxLayout(self.central_widget)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("맑은 고딕", 9))
        self.log_output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # 전체 창의 상단 부분을 위한 메인 가로 레이아웃
        main_content_hbox = QHBoxLayout()
        
        # 왼쪽 패널 (모드 설정, 입력, 건물 작동)
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        
        mode_group = QGroupBox("모드 설정")
        mode_layout = QGridLayout(mode_group)
        
        self.max_layers_combo = QComboBox()
        self.max_layers_combo.addItems(["5 (광기 모드)", "4 (일반 모드)"])
        self.max_layers_combo.currentTextChanged.connect(self.on_max_layers_changed)
        mode_layout.addWidget(QLabel("최대 층수:"), 0, 0)
        mode_layout.addWidget(self.max_layers_combo, 0, 1)
        
        self.max_depth_input = QLineEdit("4")
        self.max_depth_input.editingFinished.connect(self.on_max_depth_changed)
        mode_layout.addWidget(QLabel("최대 탐색 깊이:"), 1, 0)
        mode_layout.addWidget(self.max_depth_input, 1, 1)

        self.max_physics_height_input = QLineEdit("2")
        mode_layout.addWidget(QLabel("최대 역 물리 높이:"), 2, 0)
        mode_layout.addWidget(self.max_physics_height_input, 2, 1)

        self.log_checkbox = QCheckBox("상세 로그 보기")
        self.log_checkbox.setChecked(True)
        mode_layout.addWidget(self.log_checkbox, 3, 0, 1, 2)

        left_panel.addWidget(mode_group)

        self.on_max_layers_changed()
        self.on_max_depth_changed()

        input_group = QGroupBox("입력"); input_layout = QGridLayout(input_group)
        self.input_a = QLineEdit("crcrcrcr"); self.input_a.setObjectName("입력 A")
        self.input_b = QLineEdit(); self.input_b.setObjectName("입력 B")
        
        # 실시간 출력 업데이트를 위한 텍스트 변경 이벤트 연결
        self.input_a.textChanged.connect(self.on_input_a_changed)
        self.input_b.textChanged.connect(self.on_input_b_changed)
        
        # 입력 A 행
        input_layout.addWidget(QLabel("입력 A:"), 0, 0)
        input_layout.addWidget(self.input_a, 0, 1)
        
        # 입력 B 행
        input_layout.addWidget(QLabel("입력 B:"), 1, 0)
        input_layout.addWidget(self.input_b, 1, 1)
        
        # 통합 Undo/Redo 버튼 (입력 A 행에 배치)
        self.undo_button = QPushButton("↶")
        self.undo_button.setMaximumWidth(30)
        self.undo_button.setToolTip("Undo (Ctrl+Z)")
        self.undo_button.clicked.connect(self.on_undo)
        self.undo_button.setEnabled(False)
        input_layout.addWidget(self.undo_button, 0, 2)
        
        self.redo_button = QPushButton("↷")
        self.redo_button.setMaximumWidth(30)
        self.redo_button.setToolTip("Redo (Ctrl+Y)")
        self.redo_button.clicked.connect(self.on_redo)
        self.redo_button.setEnabled(False)
        input_layout.addWidget(self.redo_button, 0, 3)
        
        left_panel.addWidget(input_group)
        
        # 초기 히스토리 항목 추가
        self.input_history.add_entry("crcrcrcr", "")
        
        # 키보드 단축키 설정
        self.setup_shortcuts()
        
        # 초기 히스토리 버튼 상태 업데이트
        self.update_history_buttons()
        
        # 엔터키로 적용 버튼 활성화
        self.setup_enter_key_for_apply()
        
        control_group = QGroupBox("건물 작동"); control_layout = QGridLayout(control_group)
        
        # 건물 작동 버튼들을 저장
        self.destroy_half_btn = QPushButton("절반 파괴기 (A)")
        self.destroy_half_btn.clicked.connect(self.on_destroy_half)
        control_layout.addWidget(self.destroy_half_btn, 0, 0)
        
        self.stack_btn = QPushButton("스태커 (A가 아래)")
        self.stack_btn.clicked.connect(self.on_stack)
        control_layout.addWidget(self.stack_btn, 0, 1)
        
        self.push_pin_btn = QPushButton("핀 푸셔 (A)")
        self.push_pin_btn.clicked.connect(self.on_push_pin)
        control_layout.addWidget(self.push_pin_btn, 1, 0)
        
        self.apply_physics_btn = QPushButton("물리 적용 (A)")
        self.apply_physics_btn.clicked.connect(self.on_apply_physics)
        control_layout.addWidget(self.apply_physics_btn, 1, 1)
        
        self.swap_btn = QPushButton("스와퍼 (A, B)")
        self.swap_btn.clicked.connect(self.on_swap)
        control_layout.addWidget(self.swap_btn, 2, 0)
        
        rotate_hbox = QHBoxLayout()
        self.rotate_cw_btn = QPushButton("90 회전")
        self.rotate_cw_btn.clicked.connect(lambda: self.on_rotate(True))
        rotate_hbox.addWidget(self.rotate_cw_btn)
        
        self.rotate_ccw_btn = QPushButton("270 회전")
        self.rotate_ccw_btn.clicked.connect(lambda: self.on_rotate(False))
        rotate_hbox.addWidget(self.rotate_ccw_btn)
        
        control_layout.addLayout(rotate_hbox, 2, 1)
        
        paint_hbox = QHBoxLayout()
        paint_hbox.addWidget(QLabel("페인터:"))
        self.paint_color = QComboBox()
        self.paint_color.addItems(Quadrant.VALID_COLORS)
        paint_hbox.addWidget(self.paint_color)
        self.paint_btn = QPushButton("칠하기")
        self.paint_btn.clicked.connect(self.on_paint)
        paint_hbox.addWidget(self.paint_btn)
        control_layout.addLayout(paint_hbox, 3, 0, 1, 2)
        
        crystal_hbox = QHBoxLayout()
        crystal_hbox.addWidget(QLabel("크리스탈 생성:"))
        self.crystal_color = QComboBox()
        self.crystal_color.addItems([c for c in Quadrant.VALID_COLORS if c != 'u'])
        crystal_hbox.addWidget(self.crystal_color)
        self.crystal_btn = QPushButton("생성")
        self.crystal_btn.clicked.connect(self.on_crystal_gen)
        crystal_hbox.addWidget(self.crystal_btn)
        control_layout.addLayout(crystal_hbox, 4, 0, 1, 2)
        
        self.classifier_btn = QPushButton("분류기 (A)")
        self.classifier_btn.clicked.connect(self.on_classifier)
        control_layout.addWidget(self.classifier_btn, 5, 0)
        
        # 적용 버튼 추가
        self.apply_button = QPushButton("적용 (출력→입력)")
        self.apply_button.clicked.connect(self.on_apply_outputs)
        self.apply_button.setEnabled(False)  # 초기에는 비활성화
        control_layout.addWidget(self.apply_button, 5, 1)
        
        left_panel.addWidget(control_group)
        
        left_panel.addStretch(1); 
        main_content_hbox.addLayout(left_panel)
        
        # 중앙 탭 위젯 (분석 도구, AI 훈련)
        right_tabs = QTabWidget()
        analysis_tab_widget = QWidget()
        right_panel = QVBoxLayout(analysis_tab_widget)
        
        reverse_group = QGroupBox("기원 역추적")
        reverse_group.setMinimumHeight(150)
        reverse_group.setMaximumHeight(250)
        reverse_layout = QVBoxLayout(reverse_group)
        self.reverse_input = QLineEdit("P-P-P-P-:CuCuCuCu")
        self.reverse_input.setObjectName("역추적 입력")
        reverse_layout.addWidget(QLabel("목표 도형:"))
        reverse_layout.addWidget(self.reverse_input)

        find_origin_hbox = QHBoxLayout()
        find_origin_hbox.addWidget(QPushButton("기원 찾기 (규칙)", clicked=self.on_find_origin))
        copy_button = QPushButton("전체 복사")
        copy_button.clicked.connect(self.on_copy_origins)
        find_origin_hbox.addWidget(copy_button)
        reverse_layout.addLayout(find_origin_hbox)
        
        self.origin_list = QListWidget()
        self.origin_list.itemClicked.connect(self.on_origin_selected)
        reverse_layout.addWidget(QLabel("발견된 모든 후보:"))
        reverse_layout.addWidget(self.origin_list)
        right_panel.addWidget(reverse_group)
        
        test_group = QGroupBox("자동 테스트"); test_layout = QVBoxLayout(test_group)
        test_layout.addWidget(QPushButton("전체 테스트 실행", clicked=self.run_forward_tests))
        test_layout.addWidget(QPushButton("역연산 테스트 실행", clicked=self.run_reverse_tests))
        self.test_results_label = QLabel("테스트를 실행하세요.")
        test_layout.addWidget(self.test_results_label)
        right_panel.addWidget(test_group)
        
        # 출력 (분석도구 탭 하단)
        output_group = QGroupBox("출력")
        output_vbox = QVBoxLayout(output_group)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.output_widget = QWidget()
        self.output_layout = QHBoxLayout(self.output_widget)
        self.output_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.output_widget)
        output_vbox.addWidget(self.scroll_area)
        right_panel.addWidget(output_group)
        
        right_tabs.addTab(analysis_tab_widget, "분석 도구")
        
        # 대량처리 탭 추가
        batch_tab_widget = QWidget()
        batch_layout = QVBoxLayout(batch_tab_widget)
        
        # 파일 선택 그룹
        file_group = QGroupBox("파일 선택")
        file_layout = QVBoxLayout(file_group)
        
        # 파일 선택 행
        file_select_layout = QHBoxLayout()
        self.file_path_label = QLabel("선택된 파일 없음")
        self.file_path_label.setStyleSheet("color: #666; font-style: italic;")
        file_select_layout.addWidget(QLabel("파일:"))
        file_select_layout.addWidget(self.file_path_label, 1)
        
        self.browse_button = QPushButton("찾아보기")
        self.browse_button.clicked.connect(self.on_browse_file)
        file_select_layout.addWidget(self.browse_button)
        
        self.load_button = QPushButton("불러오기")
        self.load_button.clicked.connect(self.on_load_file)
        self.load_button.setEnabled(False)
        file_select_layout.addWidget(self.load_button)
        
        file_layout.addLayout(file_select_layout)
        batch_layout.addWidget(file_group)
        
        # 데이터 탭 위젯
        data_group = QGroupBox("데이터")
        data_layout = QVBoxLayout(data_group)
        
        # 커스텀 탭 위젯 생성
        self.data_tabs = CustomTabWidget()
        self.data_tabs.tab_close_requested.connect(self.on_data_tab_close)
        data_layout.addWidget(self.data_tabs)
        
        # 새 탭 추가 버튼
        new_tab_button = QPushButton("+ 새 탭")
        new_tab_button.clicked.connect(self.on_add_new_data_tab)
        data_layout.addWidget(new_tab_button)
        
        batch_layout.addWidget(data_group)
        
        # 초기 탭 생성
        self.add_data_tab("샘플", ["CuCuCuCu", "RrRrRrRr", "P-P-P-P-"])
        
        # 대량처리 변수 초기화
        self.selected_file_path = None
        
        right_tabs.addTab(batch_tab_widget, "대량처리")
        
        # 탭 변경 이벤트 연결
        right_tabs.currentChanged.connect(self.on_main_tab_changed)
        self.main_tabs = right_tabs  # 메인 탭 위젯 저장
        
        main_content_hbox.addWidget(right_tabs, 2) # 중앙 컨텐츠 영역

        # 로그 창 (맨 오른쪽, 세로로 길게)
        log_vbox = QVBoxLayout()
        
        # 로그 헤더와 클리어 버튼
        log_header_layout = QHBoxLayout()
        log_header_layout.addWidget(QLabel("<b>로그</b>"))
        log_header_layout.addStretch()
        
        log_clear_button = QPushButton("지우기")
        log_clear_button.setMaximumWidth(60)
        log_clear_button.clicked.connect(self.on_clear_log)
        log_header_layout.addWidget(log_clear_button)
        
        log_vbox.addLayout(log_header_layout)
        log_vbox.addWidget(self.log_output, 1)
        main_content_hbox.addLayout(log_vbox, 1) # 로그 영역

        main_layout.addLayout(main_content_hbox, 1)

        self.log(f"시뮬레이터 준비 완료. 자동 테스트는 tests.json 파일을 사용합니다.")
        
        # 초기 입력 표시
        self.update_input_display()

    def closeEvent(self, event):
        self.log("애플리케이션 종료 중... 백그라운드 스레드를 정리합니다.")
        
        if self.origin_finder_thread and self.origin_finder_thread.isRunning():
            self.origin_finder_thread.cancel()
            self.origin_finder_thread.wait()

        event.accept()

    def log(self, message): self.log_output.append(message)
    
    def _calculate_complexity(self, origin_shape: object) -> int:
        """복잡도를 계산합니다 (총 조각 수 기준)."""
        total_pieces = 0
        if isinstance(origin_shape, tuple):
            # 스태커/스와퍼의 경우, 두 도형의 조각 수를 합산
            for shape in origin_shape:
                if shape:
                    for layer in shape.layers:
                        total_pieces += sum(1 for q in layer.quadrants if q is not None)
        elif origin_shape:
            # 단일 기원 연산의 경우
            for layer in origin_shape.layers:
                total_pieces += sum(1 for q in layer.quadrants if q is not None)
        return total_pieces

    def _get_input_shape(self, input_widget: QLineEdit) -> Optional[Shape]:
        try: return Shape.from_string(input_widget.text())
        except Exception as e: self.log(f"🔥 입력 오류 ({input_widget.objectName()}): {e}"); return None
    
    def update_input_display(self):
        """입력 필드의 텍스트가 변경될 때마다 출력 영역을 업데이트합니다."""
        # 기존 출력 영역 클리어
        while self.output_layout.count():
            if (child := self.output_layout.takeAt(0)) and child.widget():
                child.widget().deleteLater()
        
        # 입력 A 표시
        input_a_shape = self._get_input_shape(self.input_a)
        if input_a_shape:
            container = QFrame()
            layout = QVBoxLayout(container)
            layout.addWidget(QLabel("<b>입력 A</b>"))
            layout.addWidget(ShapeWidget(input_a_shape))
            self.output_layout.addWidget(container)
        
        # 입력 B 표시 (비어있지 않은 경우만)
        if self.input_b.text().strip():
            input_b_shape = self._get_input_shape(self.input_b)
            if input_b_shape:
                container = QFrame()
                layout = QVBoxLayout(container)
                layout.addWidget(QLabel("<b>입력 B</b>"))
                layout.addWidget(ShapeWidget(input_b_shape))
                self.output_layout.addWidget(container)
        
        # 입력만 표시할 때는 출력 결과 초기화 및 적용 버튼 비활성화
        self.current_outputs = []
        self.apply_button.setEnabled(False)

    def display_outputs(self, shapes: List[Tuple[str, Optional[Shape]]], result_text: Optional[str] = None):
        while self.output_layout.count():
            if (child := self.output_layout.takeAt(0)) and child.widget():
                child.widget().deleteLater()
        
        log_msg = result_text if result_text else "결과: "

        # "연산 불가능" 특별 처리
        if result_text and "연산: 불가능" in result_text:
            container = QFrame()
            layout = QVBoxLayout(container)
            layout.addWidget(QLabel("<b>결과</b>"))
            layout.addWidget(QLabel(result_text))
            self.output_layout.addWidget(container)
            self.log(log_msg)
            
            # 출력 결과 초기화 및 적용 버튼 비활성화
            self.current_outputs = []
            self.apply_button.setEnabled(False)
            return

        # 입력 A 표시
        input_a_shape = self._get_input_shape(self.input_a)
        if input_a_shape:
            container = QFrame()
            layout = QVBoxLayout(container)
            layout.addWidget(QLabel("<b>입력 A</b>"))
            layout.addWidget(ShapeWidget(input_a_shape))
            self.output_layout.addWidget(container)
        
        # 입력 B 표시 (비어있지 않은 경우만)
        if self.input_b.text().strip():
            input_b_shape = self._get_input_shape(self.input_b)
            if input_b_shape:
                container = QFrame()
                layout = QVBoxLayout(container)
                layout.addWidget(QLabel("<b>입력 B</b>"))
                layout.addWidget(ShapeWidget(input_b_shape))
                self.output_layout.addWidget(container)

        # 결과 표시 및 추적
        self.current_outputs = []
        for title, shape in shapes:
            container = QFrame()
            layout = QVBoxLayout(container)
            layout.addWidget(QLabel(f"<b>{title}</b>"))
            if shape:
                layout.addWidget(ShapeWidget(shape))
                # 출력 결과 추적 (입력이 아닌 결과만)
                if not title.startswith("입력"):
                    self.current_outputs.append((title, shape))
            else:
                layout.addWidget(QLabel("N/A"))
            self.output_layout.addWidget(container)
            if not result_text:
                log_msg += f"[{title}: {repr(shape) if shape else 'None'}] "
        
        # 적용 버튼 활성화/비활성화
        self.apply_button.setEnabled(len(self.current_outputs) > 0)
        
        self.log(log_msg)

    def on_destroy_half(self):
        if s := self._get_input_shape(self.input_a): self.display_outputs([("파괴 후", s.destroy_half())])
    
    def on_crystal_gen(self):
        if s := self._get_input_shape(self.input_a): self.display_outputs([("생성 후", s.crystal_generator(self.crystal_color.currentText()))])
    
    def on_apply_physics(self):
        if s := self._get_input_shape(self.input_a): self.display_outputs([("안정화 후", s.apply_physics())])
    
    def on_stack(self):
        s_a = self._get_input_shape(self.input_a)
        s_b = self._get_input_shape(self.input_b)
        if s_a is not None and s_b is not None:
            self.display_outputs([("스택 후", Shape.stack(s_a, s_b))])
    
    def on_swap(self):
        s_a = self._get_input_shape(self.input_a)
        s_b = self._get_input_shape(self.input_b)
        if s_a is not None and s_b is not None:
            res_a, res_b = Shape.swap(s_a, s_b)
            self.display_outputs([("출력 A", res_a), ("출력 B", res_b)])
    
    def on_paint(self):
        if s := self._get_input_shape(self.input_a): self.display_outputs([("페인트 후", s.paint(self.paint_color.currentText()))])
    
    def on_push_pin(self):
        if s := self._get_input_shape(self.input_a): self.display_outputs([("푸셔 후", s.push_pin())])
    
    def on_rotate(self, clockwise: bool):
        if s := self._get_input_shape(self.input_a): self.display_outputs([("회전 후", s.rotate(clockwise))])
    
    def on_classifier(self):
        if s := self._get_input_shape(self.input_a):
            try:
                classification_result, classification_reason = s.classifier()
                
                # 분류 결과와 사유를 함께 표시
                result_text = f"분류: {classification_result} (사유: {classification_reason})"
                
                # 분류 결과를 출력 영역에 텍스트로 표시 (로그는 display_outputs 내부에서 처리)
                self.display_outputs([], result_text)
                
            except Exception as e:
                self.log(f"🔥 분류 오류: {e}")
    
    def on_apply_outputs(self):
        """출력 결과를 입력 필드에 적용합니다."""
        if not self.current_outputs:
            self.log("적용할 출력이 없습니다.")
            return
        
        # 출력 결과에서 Shape 객체들을 추출
        output_shapes = [shape for title, shape in self.current_outputs if shape is not None]
        
        if len(output_shapes) == 0:
            self.log("유효한 출력이 없습니다.")
            return
        elif len(output_shapes) == 1:
            # 단일 출력: 입력 A에 적용하고 입력 B는 비움
            self.input_a.setText(repr(output_shapes[0]))
            self.input_b.clear()
            self.log(f"출력을 입력 A에 적용: {repr(output_shapes[0])}")
        elif len(output_shapes) == 2:
            # 이중 출력: 첫 번째는 입력 A, 두 번째는 입력 B에 적용
            self.input_a.setText(repr(output_shapes[0]))
            self.input_b.setText(repr(output_shapes[1]))
            self.log(f"출력을 입력에 적용: A={repr(output_shapes[0])}, B={repr(output_shapes[1])}")
        else:
            # 3개 이상의 출력: 처음 두 개만 사용
            self.input_a.setText(repr(output_shapes[0]))
            self.input_b.setText(repr(output_shapes[1]))
            self.log(f"출력 중 처음 2개를 입력에 적용: A={repr(output_shapes[0])}, B={repr(output_shapes[1])}")
    
    def on_find_origin(self):
        self.origin_list.clear()
        self.log("기원 역추적 시작...")
        
        target_shape = self._get_input_shape(self.reverse_input)
        if target_shape is None:
            self.log("🔥 역추적 오류: 목표 도형 코드를 확인하세요.")
            return

        if self.origin_finder_thread and self.origin_finder_thread.isRunning():
            self.log("이전 탐색을 중단하고 새로 시작합니다.")
            self.origin_finder_thread.cancel()
            self.origin_finder_thread.wait()

        total_steps = 4 + (4 * 2) + 1
        self.progress_dialog = QProgressDialog("기원 탐색 중...", "취소", 0, total_steps, self)
        self.progress_dialog.setWindowTitle("탐색 진행률")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        
        try:
            max_physics_height = int(self.max_physics_height_input.text())
            if max_physics_height < 0: max_physics_height = 0
        except ValueError:
            max_physics_height = 2
            self.max_physics_height_input.setText("2")

        log_enabled = self.log_checkbox.isChecked()
        self.origin_finder_thread = OriginFinderThread(target_shape, ReverseTracer.MAX_SEARCH_DEPTH, max_physics_height, log_enabled)
        self.origin_finder_thread.progress.connect(self.update_progress_dialog)
        self.origin_finder_thread.finished.connect(self.on_find_origin_finished)
        self.origin_finder_thread.log_message.connect(self.log)
        self.origin_finder_thread.candidate_found.connect(self.on_candidate_found)
        self.progress_dialog.canceled.connect(self.origin_finder_thread.cancel)
        
        self.origin_finder_thread.start()
        self.progress_dialog.show()

    def on_candidate_found(self):
        if self.progress_dialog and not hasattr(self, 'complete_button'):
            self.progress_dialog.setLabelText("후보 발견! 계속 탐색 중...")
            self.complete_button = QPushButton("현재까지의 결과로 보기")
            self.complete_button.clicked.connect(self.finish_search_early)
            self.progress_dialog.setCancelButton(self.complete_button)
            self.progress_dialog.canceled.disconnect(self.origin_finder_thread.cancel)
            self.progress_dialog.canceled.connect(self.finish_search_early)

    def finish_search_early(self):
        if self.origin_finder_thread and self.origin_finder_thread.isRunning():
            self.origin_finder_thread.cancel()
            
    def update_progress_dialog(self, step, total_steps, message):
        if self.progress_dialog.wasCanceled():
            if self.origin_finder_thread and self.origin_finder_thread.isRunning():
                self.origin_finder_thread.cancel()
            return
        self.progress_dialog.setMaximum(total_steps)
        self.progress_dialog.setValue(step)
        self.progress_dialog.setLabelText(message)

    def on_find_origin_finished(self, candidates):
        was_cancelled_by_user = self.progress_dialog.wasCanceled()
        self.progress_dialog.close()
        
        if hasattr(self, 'complete_button'):
            del self.complete_button

        self.origin_list.clear()

        if was_cancelled_by_user and not candidates:
            self.log("탐색이 사용자에 의해 중단되었습니다.")
            return

        if not candidates:
            self.log(f"결과: 최대 깊이({ReverseTracer.MAX_SEARCH_DEPTH})까지 탐색했으나 후보가 없습니다.")
            self.display_outputs([], "연산: 불가능")
            return
        
        self.log(f"결과: {len(candidates)}개의 후보를 발견했습니다. (탐색 완료 또는 조기 중단)")
        
        # 복잡도 기준으로 최적 후보 선택
        best_candidate = min(candidates, key=lambda c: self._calculate_complexity(c[1]))
        op_name, origin_shape = best_candidate
        
        result_text = ""
        display_shapes = []
        if isinstance(origin_shape, tuple):
            shape_a, shape_b = origin_shape
            result_text = f"연산: {op_name}. 기원 A: {repr(shape_a)}, 기원 B: {repr(shape_b)}"
            display_shapes = [("기원 A", shape_a), ("기원 B", shape_b)]
        else:
            result_text = f"연산: {op_name}. 기원: {repr(origin_shape)}"
            display_shapes = [("기원", origin_shape)]

        self.display_outputs(display_shapes, result_text)
        self.log(f"-> 복잡도가 가장 낮은 최적 후보: {result_text}")

        # 전체 후보 목록은 리스트에 표시
        for op, shp in sorted(candidates, key=lambda c: self._calculate_complexity(c[1])):
            item_text = ""
            if isinstance(shp, tuple):
                shape_a, shape_b = shp
                item_text = f"{op}: (A: {repr(shape_a)}, B: {repr(shape_b)})"
            else:
                item_text = f"{op}: {repr(shp)}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, (op, shp))
            self.origin_list.addItem(item)
            
    def on_copy_origins(self):
        if self.origin_list.count() == 0:
            self.log("복사할 후보가 없습니다.")
            return
        
        all_origins_text = []
        for i in range(self.origin_list.count()):
            all_origins_text.append(self.origin_list.item(i).text())
        
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(all_origins_text))
        self.log(f"{self.origin_list.count()}개의 후보를 클립보드에 복사했습니다.")

    def on_origin_selected(self, item):
        op_name, origin_shape = item.data(Qt.ItemDataRole.UserRole)
        
        self.log(f"선택된 후보 로드: [{op_name}]")
        
        if isinstance(origin_shape, tuple):
            shape_a, shape_b = origin_shape
            self.input_a.setText(repr(shape_a))
            self.input_b.setText(repr(shape_b))
            self.log(f"  -> 입력 A: {repr(shape_a)}")
            self.log(f"  -> 입력 B: {repr(shape_b)}")
            
            self.display_outputs([("선택된 후보 A", shape_a), ("선택된 후보 B", shape_b)])

        else:
            self.input_a.setText(repr(origin_shape))
            self.input_b.clear()
            self.log(f"  -> 입력 A: {repr(origin_shape)}")

            self.display_outputs([("선택된 후보", origin_shape)])
        
    def on_max_depth_changed(self):
        try:
            text = self.max_depth_input.text()
            new_depth = int(text)
            if new_depth < 1:
                self.log("🔥 오류: 최대 탐색 깊이는 1 이상이어야 합니다. 1로 설정합니다.")
                new_depth = 1
                self.max_depth_input.setText(str(new_depth))
            
            ReverseTracer.MAX_SEARCH_DEPTH = new_depth
            self.log(f"최대 탐색 깊이가 {new_depth}로 설정되었습니다.")
        except ValueError:
            self.log("🔥 오류: 최대 탐색 깊이는 숫자로 입력해야 합니다. 1로 설정합니다.")
            ReverseTracer.MAX_SEARCH_DEPTH = 1
            self.max_depth_input.setText("1")

    def on_max_layers_changed(self):
        text = self.max_layers_combo.currentText()
        new_max = int(text.split(" ")[0])
        Shape.MAX_LAYERS = new_max
        self.log(f"최대 층수가 {new_max}층으로 설정되었습니다.") 

    
    def run_forward_tests(self):
        self.log_output.clear(); self.log("=== 전체 정방향 테스트 시작 (tests.json) ===")
        try:
            with open('tests.json', 'r', encoding='utf-8') as f: test_suites = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e: self.log(f"🔥 테스트 파일 오류: {e}"); return
        
        passed_count, total_count = 0, 0
        for category, test_cases in test_suites.items():
            if category == "역연산":
                continue 

            self.log(f"\n--- {category} 카테고리 ---")
            for test in test_cases:
                total_count += 1
                name, operation = test['name'], test['operation']
                input_a_str, input_b_str = test.get('input_a', ""), test.get('input_b')
                params = test.get('params', {})
                try:
                    shape_a = Shape.from_string(input_a_str)
                    
                    if operation == "swap":
                        if not input_b_str: raise ValueError("'swap'은 'input_b'가 필요합니다.")
                        shape_b = Shape.from_string(input_b_str)
                        actual_a, actual_b = Shape.swap(shape_a, shape_b)
                        actual_a_code, actual_b_code = repr(actual_a), repr(actual_b)
                        
                        expected_a_shape = Shape.from_string(test.get('expected_a', ""))
                        expected_b_shape = Shape.from_string(test.get('expected_b', ""))
                        expected_a_code, expected_b_code = repr(expected_a_shape), repr(expected_b_shape)

                        if actual_a_code == expected_a_code and actual_b_code == expected_b_code:
                            passed_count += 1; self.log(f"✅ 통과: {name}")
                        else: self.log(f"❌ 실패: {name}\n  - 입력A: {input_a_str}\n  - 입력B: {input_b_str}\n  - 예상A: {expected_a_code}\n  - 실제A: {actual_a_code}\n  - 예상B: {expected_b_code}\n  - 실제B: {actual_b_code}")
                        continue
                    
                    actual_shape = None
                    if input_b_str:
                        shape_b = Shape.from_string(input_b_str)
                        if operation == "stack": actual_shape = Shape.stack(shape_a, shape_b)
                        else: raise ValueError(f"연산 '{operation}'은 입력 B를 지원하지 않습니다.")
                    else:
                        if operation == "apply_physics": actual_shape = shape_a.apply_physics()
                        elif operation == "destroy_half": actual_shape = shape_a.destroy_half()
                        elif operation == "push_pin": actual_shape = shape_a.push_pin()
                        elif operation == "paint": actual_shape = shape_a.paint(params['color'])
                        elif operation == "crystal_generator": actual_shape = shape_a.crystal_generator(params['color'])
                        elif operation == "rotate": actual_shape = shape_a.rotate(params.get('clockwise', True))
                        elif operation == "classifier":
                            # classifier 연산은 이제 (분류결과, 사유) 튜플을 반환함
                            result_string, reason = shape_a.classifier()
                            expected = test.get('expected', "")
                            
                            # 예상 문자열이 결과 문자열에 포함되어 있는지 검사
                            if expected in result_string:
                                passed_count += 1
                                self.log(f"✅ 통과: {name}")
                            else:
                                self.log(f"❌ 실패: {name}\n  - 입력A: {input_a_str}\n  - 예상: {expected}\n  - 실제: {result_string} (사유: {reason})")
                            continue
                        else: raise ValueError(f"연산 '{operation}'은 입력 A만으로는 수행할 수 없습니다.")
                    
                    actual_code = repr(actual_shape)
                    expected_shape = Shape.from_string(test.get('expected', ""))
                    expected_code = repr(expected_shape)

                    if actual_code == expected_code:
                        passed_count += 1; self.log(f"✅ 통과: {name}")
                    else: self.log(f"❌ 실패: {name}\n  - 입력A: {input_a_str}\n  - 예상: {expected_code}\n  - 실제: {actual_code}")
                except Exception as e:
                    self.log(f"🔥 오류: {name} - {e.__class__.__name__}: {e}")
                    import traceback; self.log(traceback.format_exc())
        summary = f"정방향 테스트 종료: {total_count}개 중 {passed_count}개 통과 ({passed_count/total_count if total_count > 0 else 0:.1%})"
        self.log(f"\n=== {summary} ==="); self.test_results_label.setText(summary)

    def run_reverse_tests(self):
        self.log_output.clear()
        self.log("=== 전체 역연산 테스트 시작 (tests.json) ===")
        try:
            with open('tests.json', 'r', encoding='utf-8') as f:
                test_suites = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.log(f"🔥 테스트 파일('tests.json')을 불러오는 중 오류 발생: {e}")
            return

        if "역연산" not in test_suites:
            self.log("테스트 파일에 '역연산' 카테고리가 없습니다.")
            return

        passed_count, total_count = 0, 0
        test_cases = test_suites["역연산"]
        
        self.log(f"\n--- 역연산 카테고리 ---")
        for test in test_cases:
            total_count += 1
            test_name = test['name']
            target_shape_str = test['input_a']
            
            expected_op = test.get('operation')
            expected_shape_str = test.get('expected')
            expected_a_str = test.get('expected_a')
            expected_b_str = test.get('expected_b')
            
            target_shape = Shape.from_string(target_shape_str)
            
            found_candidates = []
            try:
                search_depth = 1
                max_physics_height = 2

                all_cands = []
                all_cands.extend(ReverseTracer.inverse_apply_physics(target_shape, search_depth, max_physics_height))
                all_cands.extend(ReverseTracer.inverse_push_pin(target_shape, search_depth, max_physics_height))
                all_cands.extend(ReverseTracer.inverse_crystal_generator(target_shape, search_depth))
                all_cands.extend(ReverseTracer.inverse_stack(target_shape, search_depth))
                for i in range(4):
                    rotated_target = target_shape.copy()
                    for _ in range(i): rotated_target = rotated_target.rotate(clockwise=True)
                    all_cands.extend(ReverseTracer.inverse_destroy_half(rotated_target, i, search_depth))
                    all_cands.extend(ReverseTracer.inverse_swap(rotated_target, i, search_depth))
                
                unique_candidates = []
                seen_canonical_keys = set()
                for op_name, origin_shape in all_cands:
                    key = ReverseTracer._get_canonical_key(op_name, origin_shape)
                    if key not in seen_canonical_keys:
                        seen_canonical_keys.add(key)
                        unique_candidates.append((op_name, origin_shape))
                found_candidates = unique_candidates
            except Exception as e:
                self.log(f"🔥 오류: '{test_name}' 실행 중 예외 발생 - {e}")
                import traceback; self.log(traceback.format_exc())
                continue

            found_match = False
            if expected_op == 'exist':
                if len(found_candidates) > 0:
                    found_match = True
            elif expected_a_str is not None and expected_b_str is not None:
                expected_a_normalized_str = repr(Shape.from_string(expected_a_str).normalize())
                expected_b_normalized_str = repr(Shape.from_string(expected_b_str).normalize())

                for found_op, found_shape in found_candidates:
                    if isinstance(found_shape, tuple):
                        found_a_normalized_str = repr(found_shape[0].normalize())
                        found_b_normalized_str = repr(found_shape[1].normalize())
                        
                        if found_a_normalized_str == expected_a_normalized_str and \
                           found_b_normalized_str == expected_b_normalized_str:
                            found_match = True
                            break
            else:
                if not expected_shape_str:
                    self.log(f"🔥 오류: '{test_name}'의 'expected' 키가 없습니다.")
                    continue
                
                expected_shape_normalized_str = repr(Shape.from_string(expected_shape_str).normalize())
                
                for found_op, found_shape in found_candidates:
                    if isinstance(found_shape, tuple):
                        continue
                    
                    found_shape_normalized_str = repr(found_shape.normalize())
                    
                    if found_shape_normalized_str == expected_shape_normalized_str:
                        found_match = True
                        break
            
            if found_match:
                passed_count += 1
                self.log(f"✅ 통과: {test_name}")
            else:
                self.log(f"❌ 실패: {test_name}")
                self.log(f"  - 목표: {target_shape_str}")
                if expected_op == 'exist':
                    self.log(f"  - 예상: 기원이 하나 이상 존재해야 함")
                elif expected_a_str is not None and expected_b_str is not None:
                    expected_a_normalized_str = repr(Shape.from_string(expected_a_str).normalize())
                    expected_b_normalized_str = repr(Shape.from_string(expected_b_str).normalize())
                    self.log(f"  - 예상 기원 (A:{expected_a_str}, B:{expected_b_str}) (정규화: A:{expected_a_normalized_str}, B:{expected_b_normalized_str})")
                else:
                    expected_shape_normalized_str = repr(Shape.from_string(expected_shape_str).normalize())
                    self.log(f"  - 예상 기원 ({expected_op if expected_op else '모든 연산'}): {expected_shape_str} (정규화: {expected_shape_normalized_str})")
                
                if found_candidates:
                    self.log("  - 발견된 후보들:")
                    for op, shp in found_candidates:
                        if isinstance(shp, tuple):
                            self.log(f"    - {op}: (A:{repr(shp[0])}, B:{repr(shp[1])})")
                        else:
                            self.log(f"    - {op}: {repr(shp)}")
                else:
                    self.log("  - 발견된 후보 없음")

        summary = f"역연산 테스트 종료: {total_count}개 중 {passed_count}개 통과 ({passed_count/total_count if total_count > 0 else 0:.1%})"
        self.log(f"\n=== {summary} ===\n"); self.test_results_label.setText(summary)

    # =================== 키보드 단축키 설정 ===================
    
    def setup_shortcuts(self):
        """키보드 단축키 설정"""
        # 통합 Undo/Redo 단축키
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.on_undo)
        
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.on_redo)
    
    def setup_enter_key_for_apply(self):
        """엔터키로 적용 버튼 실행"""
        self.shortcut_apply = QShortcut(QKeySequence("Return"), self)
        self.shortcut_apply.activated.connect(self.on_apply_if_enabled)
        
        # Enter 키 (넘패드)
        self.shortcut_apply_enter = QShortcut(QKeySequence("Enter"), self)
        self.shortcut_apply_enter.activated.connect(self.on_apply_if_enabled)
    
    def on_apply_if_enabled(self):
        """적용 버튼이 활성화되어 있을 때만 실행"""
        if self.apply_button.isEnabled():
            self.on_apply_outputs()
    
    # =================== 히스토리 관리 메서드들 ===================
    
    def on_input_a_changed(self):
        """입력 A 텍스트 변경 시 호출"""
        if not self.history_update_in_progress:
            self.add_to_history()
        self.update_input_display()
    
    def on_input_b_changed(self):
        """입력 B 텍스트 변경 시 호출"""
        if not self.history_update_in_progress:
            self.add_to_history()
        self.update_input_display()
    
    def add_to_history(self):
        """현재 입력 상태를 히스토리에 추가"""
        input_a_text = self.input_a.text()
        input_b_text = self.input_b.text()
        self.input_history.add_entry(input_a_text, input_b_text)
        self.update_history_buttons()
    
    def update_history_buttons(self):
        """히스토리 버튼 상태 업데이트"""
        self.undo_button.setEnabled(self.input_history.can_undo())
        self.redo_button.setEnabled(self.input_history.can_redo())
    
    def on_undo(self):
        """Undo 실행"""
        entry = self.input_history.undo()
        if entry is not None:
            input_a_text, input_b_text = entry
            self.history_update_in_progress = True
            self.input_a.setText(input_a_text)
            self.input_b.setText(input_b_text)
            self.history_update_in_progress = False
            self.update_history_buttons()
    
    def on_redo(self):
        """Redo 실행"""
        entry = self.input_history.redo()
        if entry is not None:
            input_a_text, input_b_text = entry
            self.history_update_in_progress = True
            self.input_a.setText(input_a_text)
            self.input_b.setText(input_b_text)
            self.history_update_in_progress = False
            self.update_history_buttons()

    # =================== 대량처리 관련 메서드들 ===================
    
    def add_data_tab(self, tab_name: str, data: list):
        """새로운 데이터 탭 추가"""
        tab_widget = DataTabWidget(tab_name, data)
        self.data_tabs.addTab(tab_widget, tab_name)
        self.data_tabs.setCurrentWidget(tab_widget)
        return tab_widget
    
    def get_current_data_tab(self):
        """현재 활성 데이터 탭 반환"""
        return self.data_tabs.currentWidget()
    
    def on_data_tab_close(self, index):
        """데이터 탭 닫기"""
        if self.data_tabs.count() <= 1:
            QMessageBox.warning(self, "경고", "마지막 탭은 닫을 수 없습니다.")
            return
        
        tab_name = self.data_tabs.tabText(index)
        self.data_tabs.removeTab(index)
        self.log(f"데이터 탭 '{tab_name}' 닫힘")
    
    def on_add_new_data_tab(self):
        """새로운 데이터 탭 추가"""
        new_tab_name = f"데이터 {self.data_tabs.count() + 1}"
        self.add_data_tab(new_tab_name, [])
        self.log(f"새 데이터 탭 '{new_tab_name}' 추가")
    
    def on_batch_operation(self, operation_name: str):
        """현재 탭의 모든 데이터에 대해 건물 작동 연산 수행"""
        current_tab = self.get_current_data_tab()
        if not current_tab or not current_tab.data:
            QMessageBox.information(self, "알림", "처리할 데이터가 없습니다.")
            return
        
        # 작업 전 현재 상태를 히스토리에 저장
        current_tab.add_to_data_history(f"작업 전 ({operation_name})")
        
        self.log(f"'{current_tab.tab_name}' 탭의 {len(current_tab.data)}개 항목에 대해 {operation_name} 연산 수행")
        
        # 결과 데이터 저장
        result_data = []
        error_count = 0
        
        for i, shape_code in enumerate(current_tab.data):
            try:
                shape = Shape.from_string(shape_code)
                result_shape = None
                
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
                elif operation_name == "paint":
                    result_shape = shape.paint(self.paint_color.currentText())
                elif operation_name == "crystal_generator":
                    result_shape = shape.crystal_generator(self.crystal_color.currentText())
                elif operation_name == "classifier":
                    classification_result, classification_reason = shape.classifier()
                    result_data.append(f"{classification_result} ({classification_reason})")
                    continue
                elif operation_name == "stack":
                    # 입력 B에 있는 도형과 스택
                    input_b_text = self.input_b.text().strip()
                    if not input_b_text:
                        result_data.append("오류: 입력 B가 비어있음")
                        error_count += 1
                        continue
                    try:
                        shape_b = Shape.from_string(input_b_text)
                        result_shape = Shape.stack(shape, shape_b)
                    except Exception as e:
                        result_data.append(f"오류: 입력 B 파싱 실패 - {str(e)}")
                        error_count += 1
                        continue
                elif operation_name == "swap":
                    # 입력 B에 있는 도형과 스왑
                    input_b_text = self.input_b.text().strip()
                    if not input_b_text:
                        result_data.append("오류: 입력 B가 비어있음")
                        error_count += 1
                        continue
                    try:
                        shape_b = Shape.from_string(input_b_text)
                        result_a, result_b = Shape.swap(shape, shape_b)
                        # 스왑은 두 개의 결과를 생성하므로 둘 다 추가
                        result_data.append(f"A: {repr(result_a)}")
                        result_data.append(f"B: {repr(result_b)}")
                        continue
                    except Exception as e:
                        result_data.append(f"오류: 입력 B 파싱 실패 - {str(e)}")
                        error_count += 1
                        continue
                
                if result_shape is not None:
                    result_data.append(repr(result_shape))
                else:
                    result_data.append("오류: 결과 없음")
                    error_count += 1
                    
            except Exception as e:
                result_data.append(f"오류: {str(e)}")
                error_count += 1
        
        # 현재 탭의 데이터를 결과로 교체
        current_tab.data = result_data
        current_tab.update_table()
        
        # 작업 완료 후 히스토리에 추가
        current_tab.add_to_data_history(f"{operation_name} 완료")
        
        self.log(f"대량처리 완료: {len(result_data)}개 결과 생성, {error_count}개 오류")
        if error_count > 0:
            QMessageBox.warning(self, "경고", f"{error_count}개 항목에서 오류가 발생했습니다.")
    
    def on_browse_file(self):
        """파일 찾아보기 대화상자 열기"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "도형 데이터 파일 선택",
            "data/",  # 기본 경로를 data 폴더로 설정
            "텍스트 파일 (*.txt);;모든 파일 (*.*)"
        )
        
        if file_path:
            self.selected_file_path = file_path
            self.file_path_label.setText(file_path)
            self.file_path_label.setStyleSheet("color: black;")
            self.load_button.setEnabled(True)
            self.log(f"파일 선택됨: {file_path}")
    
    def on_load_file(self):
        """선택된 파일 로드"""
        if not self.selected_file_path:
            return
            
        try:
            with open(self.selected_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 빈 줄과 주석(#으로 시작) 제거
            shape_codes = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    shape_codes.append(line)
            
            if not shape_codes:
                QMessageBox.warning(self, "경고", "파일에 유효한 도형 코드가 없습니다.")
                return
            
            # 새 탭에 데이터 로드
            import os
            tab_name = os.path.splitext(os.path.basename(self.selected_file_path))[0]
            self.add_data_tab(tab_name, shape_codes)
            
            self.log(f"파일 로드 완료: {len(shape_codes)}개의 도형 코드를 새 탭 '{tab_name}'에 불러왔습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 로드 중 오류 발생:\n{str(e)}")
            self.log(f"파일 로드 오류: {str(e)}")
    
    def on_table_context_menu(self, position: QPoint):
        """테이블에 우클릭 메뉴 추가 (기존 메서드 유지)"""
        current_tab = self.get_current_data_tab()
        if current_tab:
            current_tab.on_table_context_menu(position)
    
    def on_copy_shape_code_to_input_a(self):
        """선택된 행의 도형 코드를 입력 A에 복사 (기존 메서드 유지)"""
        current_tab = self.get_current_data_tab()
        if current_tab:
            current_tab.on_copy_to_input_a()
    
    def update_data_table(self):
        """데이터 테이블 업데이트 (기존 메서드 - 호환성 유지)"""
        current_tab = self.get_current_data_tab()
        if current_tab:
            current_tab.update_table()
    
    def on_clear_data(self):
        """데이터 지우기 (기존 메서드 - 호환성 유지)"""
        current_tab = self.get_current_data_tab()
        if current_tab:
            current_tab.on_clear_data()
    
    def on_clear_log(self):
        """로그 창 클리어"""
        self.log_output.clear()
        self.log("로그가 지워졌습니다.")

    def on_main_tab_changed(self, index):
        """메인 탭 변경 시 호출"""
        tab_name = self.main_tabs.tabText(index)
        
        if tab_name == "대량처리":
            self.switch_to_batch_mode()
        else:
            self.switch_to_single_mode()
        
        # self.log(f"메인 탭이 {tab_name}로 변경되었습니다.")
    
    def switch_to_batch_mode(self):
        """대량처리 모드로 전환"""
        # 버튼 텍스트 변경
        self.destroy_half_btn.setText("절반 파괴기 (∀)")
        self.push_pin_btn.setText("핀 푸셔 (∀)")
        self.apply_physics_btn.setText("물리 적용 (∀)")
        self.rotate_cw_btn.setText("90 회전")
        self.rotate_ccw_btn.setText("270 회전")
        self.paint_btn.setText("칠하기")
        self.crystal_btn.setText("생성")
        self.classifier_btn.setText("분류기 (∀)")
        
        # 스태커와 스와퍼 텍스트 변경 (비활성화하지 않음)
        self.stack_btn.setText("스태커 (∀+B)")
        self.swap_btn.setText("스와퍼 (∀↔B)")
        self.apply_button.setEnabled(False)
        
        # 버튼 클릭 이벤트를 대량처리용으로 변경
        self.destroy_half_btn.clicked.disconnect()
        self.destroy_half_btn.clicked.connect(lambda: self.on_batch_operation("destroy_half"))
        
        self.push_pin_btn.clicked.disconnect()
        self.push_pin_btn.clicked.connect(lambda: self.on_batch_operation("push_pin"))
        
        self.apply_physics_btn.clicked.disconnect()
        self.apply_physics_btn.clicked.connect(lambda: self.on_batch_operation("apply_physics"))
        
        self.rotate_cw_btn.clicked.disconnect()
        self.rotate_cw_btn.clicked.connect(lambda: self.on_batch_operation("rotate_cw"))
        
        self.rotate_ccw_btn.clicked.disconnect()
        self.rotate_ccw_btn.clicked.connect(lambda: self.on_batch_operation("rotate_ccw"))
        
        self.paint_btn.clicked.disconnect()
        self.paint_btn.clicked.connect(lambda: self.on_batch_operation("paint"))
        
        self.crystal_btn.clicked.disconnect()
        self.crystal_btn.clicked.connect(lambda: self.on_batch_operation("crystal_generator"))
        
        self.classifier_btn.clicked.disconnect()
        self.classifier_btn.clicked.connect(lambda: self.on_batch_operation("classifier"))
        
        # 스태커와 스와퍼를 대량처리용으로 연결
        self.stack_btn.clicked.disconnect()
        self.stack_btn.clicked.connect(lambda: self.on_batch_operation("stack"))
        
        self.swap_btn.clicked.disconnect()
        self.swap_btn.clicked.connect(lambda: self.on_batch_operation("swap"))
    
    def switch_to_single_mode(self):
        """단일 모드로 전환"""
        # 버튼 텍스트 복원
        self.destroy_half_btn.setText("절반 파괴기 (A)")
        self.push_pin_btn.setText("핀 푸셔 (A)")
        self.apply_physics_btn.setText("물리 적용 (A)")
        self.rotate_cw_btn.setText("90 회전")
        self.rotate_ccw_btn.setText("270 회전")
        self.paint_btn.setText("칠하기")
        self.crystal_btn.setText("생성")
        self.classifier_btn.setText("분류기 (A)")
        
        # 스태커와 스와퍼 텍스트 복원
        self.stack_btn.setText("스태커 (A+B)")
        self.swap_btn.setText("스와퍼 (A↔B)")
        
        # 버튼 클릭 이벤트를 단일 모드용으로 복원
        self.destroy_half_btn.clicked.disconnect()
        self.destroy_half_btn.clicked.connect(self.on_destroy_half)
        
        self.push_pin_btn.clicked.disconnect()
        self.push_pin_btn.clicked.connect(self.on_push_pin)
        
        self.apply_physics_btn.clicked.disconnect()
        self.apply_physics_btn.clicked.connect(self.on_apply_physics)
        
        self.rotate_cw_btn.clicked.disconnect()
        self.rotate_cw_btn.clicked.connect(lambda: self.on_rotate(True))
        
        self.rotate_ccw_btn.clicked.disconnect()
        self.rotate_ccw_btn.clicked.connect(lambda: self.on_rotate(False))
        
        self.paint_btn.clicked.disconnect()
        self.paint_btn.clicked.connect(self.on_paint)
        
        self.crystal_btn.clicked.disconnect()
        self.crystal_btn.clicked.connect(self.on_crystal_gen)
        
        self.classifier_btn.clicked.disconnect()
        self.classifier_btn.clicked.connect(self.on_classifier)
        
        # 스태커와 스와퍼를 단일 모드용으로 복원
        self.stack_btn.clicked.disconnect()
        self.stack_btn.clicked.connect(self.on_stack)
        
        self.swap_btn.clicked.disconnect()
        self.swap_btn.clicked.connect(self.on_swap)

class CustomTabWidget(QTabWidget):
    """탭 삭제 가능한 커스텀 탭 위젯"""
    tab_close_requested = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.on_tab_close_requested)
    
    def on_tab_close_requested(self, index):
        if self.count() > 1:  # 최소 1개 탭은 유지
            self.tab_close_requested.emit(index)

class DragDropTableWidget(QTableWidget):
    """드래그 앤 드롭을 지원하는 테이블 위젯"""
    rows_reordered = pyqtSignal(int, int) # 실제 데이터 리스트 순서 변경을 위한 시그널
    
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True) # 드롭 허용
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.drag_start_row = -1
        self.drag_start_point = QPoint() # 드래그 시작 위치 저장

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item:
                self.drag_start_row = item.row()
                self.drag_start_point = event.pos() # 드래그 시작 위치 저장
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_start_row != -1:
            # 드래그 임계값 이상 이동했을 때만 드래그 시작
            if (event.pos() - self.drag_start_point).manhattanLength() > QApplication.startDragDistance():
                self.startDrag(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)

    def startDrag(self, supportedActions):
        """드래그 시작 시 호출"""
        selected_items = self.selectedItems()
        if selected_items:
            # 드래그할 항목의 MIME 데이터 생성 (여기서는 실제 데이터를 담지 않음, 그냥 신호용)
            mimeData = QMimeData()
            mimeData.setText(str(self.drag_start_row)) # 시작 행 정보를 MIME 데이터에 저장
            
            drag = QDrag(self)
            drag.setMimeData(mimeData)
            # 드래그 아이콘 설정 (옵션)
            # pixmap = QPixmap(self.grab(self.visualItemRect(self.item(self.drag_start_row, 0))))
            # drag.setPixmap(pixmap)
            
            drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): # 텍스트 MIME 데이터 확인 (startDrag에서 설정한 것)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.source() == self and event.mimeData().hasText():
            from_row = int(event.mimeData().text()) # MIME 데이터에서 시작 행 가져오기
            drop_pos_y = event.position().toPoint().y()
            to_row = self.rowAt(drop_pos_y)
            
            if to_row == -1: # 테이블의 빈 공간에 드롭한 경우 맨 마지막으로 간주
                to_row = self.rowCount() # 삽입될 위치는 현재 행 수와 같음

            # from_row와 to_row가 다르고 유효한 범위 내에 있을 때만 처리
            if from_row != to_row:
                # 실제 데이터 리스트의 insert 위치는 pop 후의 인덱스를 고려해야 함
                # 예를 들어, 5번 항목을 2번 위치로 옮기면, 5번은 pop 되고 2번에 insert됨
                # 2번 항목을 5번 위치로 옮기면, 2번은 pop 되고 5번에 insert됨. 이때 5번 인덱스는 이미 한 칸 당겨진 상태.
                # 간단하게는 from_row가 to_row보다 크면 to_row는 그대로, 작으면 to_row-1
                adjusted_to_row = to_row
                if from_row < to_row: # 아래로 이동하는 경우
                    adjusted_to_row = to_row - 1

                self.rows_reordered.emit(from_row, adjusted_to_row)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            super().dropEvent(event)
        
        # 드래그 정보 초기화
        self.drag_start_row = -1
        self.drag_start_point = QPoint()

class DataTabWidget(QWidget):
    """개별 데이터 탭 위젯"""
    def __init__(self, tab_name="새 탭", data=None):
        super().__init__()
        self.tab_name = tab_name
        self.data = data or []
        
        # 데이터 히스토리 관리 객체 생성
        self.data_history = DataHistory(50)
        self.history_update_in_progress = False  # 히스토리 업데이트 중 플래그
        
        self.setup_ui()
        
        # 초기 데이터를 히스토리에 추가
        if self.data:
            self.data_history.add_entry(self.data, "초기 데이터")
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 데이터 테이블
        self.data_table = DragDropTableWidget()
        self.data_table.setColumnCount(2)
        self.data_table.setHorizontalHeaderLabels(["유효성", "도형 코드"])
        self.data_table.horizontalHeader().setStretchLastSection(True)
        self.data_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.data_table.customContextMenuRequested.connect(self.on_table_context_menu)
        self.data_table.rows_reordered.connect(self.on_data_moved)
        layout.addWidget(self.data_table)
        
        # 단축키 설정
        self.setup_shortcuts()
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        
        # 저장 버튼
        self.save_button = QPushButton("저장")
        self.save_button.clicked.connect(self.on_save_data)
        button_layout.addWidget(self.save_button)
        
        # 복제 버튼
        self.clone_button = QPushButton("복제")
        self.clone_button.clicked.connect(self.on_clone_tab)
        button_layout.addWidget(self.clone_button)
        
        # 데이터 히스토리 Undo/Redo 버튼
        self.data_undo_button = QPushButton("↶")
        self.data_undo_button.setMaximumWidth(30)
        self.data_undo_button.setToolTip("데이터 Undo (Ctrl+Shift+Z)")
        self.data_undo_button.clicked.connect(self.on_data_undo)
        self.data_undo_button.setEnabled(False)
        button_layout.addWidget(self.data_undo_button)
        
        self.data_redo_button = QPushButton("↷")
        self.data_redo_button.setMaximumWidth(30)
        self.data_redo_button.setToolTip("데이터 Redo (Ctrl+Shift+Y)")
        self.data_redo_button.clicked.connect(self.on_data_redo)
        self.data_redo_button.setEnabled(False)
        button_layout.addWidget(self.data_redo_button)
        
        # 데이터 지우기 버튼
        self.clear_button = QPushButton("데이터 지우기")
        self.clear_button.clicked.connect(self.on_clear_data)
        button_layout.addWidget(self.clear_button)
        
        button_layout.addStretch()
        
        # 선택된 항목 처리 버튼
        self.process_button = QPushButton("선택된 항목 처리")
        self.process_button.clicked.connect(self.on_process_selected)
        button_layout.addWidget(self.process_button)
        
        layout.addLayout(button_layout)
        
        # 초기 데이터 업데이트
        self.update_table()
    
    def setup_shortcuts(self):
        """단축키 설정"""
        # Ctrl+C: 클립보드로 복사
        self.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self.copy_shortcut.activated.connect(self.on_copy_to_clipboard)
        
        # Ctrl+V: 클립보드에서 붙여넣기
        self.paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self.paste_shortcut.activated.connect(self.on_paste_from_clipboard)
        
        # Delete: 선택된 항목 삭제
        self.delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self)
        self.delete_shortcut.activated.connect(self.on_delete_selected)
        
        # 데이터 히스토리 단축키
        self.data_undo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.data_undo_shortcut.activated.connect(self.on_data_undo)
        
        self.data_redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Y"), self)
        self.data_redo_shortcut.activated.connect(self.on_data_redo)
    
    def on_data_moved(self, from_row, to_row):
        """드래그 앤 드롭으로 데이터 이동"""
        
        # 같은 위치로 이동하는 경우 이미 dropEvent에서 걸러짐
        # 여기서 다시 확인할 필요 없음

        if 0 <= from_row < len(self.data) and 0 <= to_row <= len(self.data): # to_row는 마지막 위치 바로 다음까지 가능
            # 데이터 삭제 후 해당 위치에 삽입
            moved_item = self.data.pop(from_row)
            
            self.data.insert(to_row, moved_item)
            
            # 테이블 업데이트 (번호 열 갱신 및 버튼 상태 갱신 등을 위해 필요)
            self.update_table()
            
            # 히스토리에 추가
            self.add_to_data_history(f"이동 ({from_row + 1}→{to_row + 1})")
            
            # 이동된 행을 선택 상태로 유지
            self.data_table.selectRow(to_row)
            
            main_window = self.get_main_window()
            if main_window:
                main_window.log(f"항목이 {from_row + 1}번에서 {to_row + 1}번으로 이동되었습니다.")
        else:
            pass
    
    def on_paste_from_clipboard(self):
        """클립보드에서 데이터 붙여넣기"""
        app = QApplication.instance()
        if not app:
            return
            
        clipboard_text = app.clipboard().text().strip()
        if not clipboard_text:
            return
        
        # \n으로 분리하여 각 줄을 데이터로 추가
        lines = clipboard_text.split('\n')
        valid_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                valid_lines.append(line)
        
        if not valid_lines:
            return
        
        # 삽입 위치 결정
        insert_position = len(self.data)  # 기본값: 맨 아래
        
        # 선택된 항목이 있으면 그 아래에 삽입
        selected_rows = set()
        for item in self.data_table.selectedItems():
            selected_rows.add(item.row())
        
        if selected_rows:
            insert_position = max(selected_rows) + 1
        
        # 데이터 삽입
        for i, line in enumerate(valid_lines):
            self.data.insert(insert_position + i, line)
        
        self.update_table()
        
        # 히스토리에 추가
        self.add_to_data_history(f"붙여넣기 ({len(valid_lines)}개)")
        
        main_window = self.get_main_window()
        if main_window:
            main_window.log(f"{len(valid_lines)}개 항목이 {insert_position + 1}번 위치에 추가되었습니다.")
    
    def update_table(self):
        """테이블 업데이트"""
        # 현재 선택된 행들을 기억
        selected_rows = set()
        for item in self.data_table.selectedItems():
            selected_rows.add(item.row())
        
        self.data_table.setRowCount(len(self.data))
        
        for i, shape_code in enumerate(self.data):
            # 번호 열
            number_item = QTableWidgetItem(str(i + 1))
            number_item.setFlags(number_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.data_table.setItem(i, 0, number_item)
            
            # 도형 코드 열
            code_item = QTableWidgetItem(shape_code)
            self.data_table.setItem(i, 1, code_item)

            # 이전에 선택된 행이었으면 다시 선택
            if i in selected_rows:
                self.data_table.item(i, 0).setSelected(True)
                self.data_table.item(i, 1).setSelected(True)
        
        # 첫 번째 열 너비 조정
        self.data_table.setColumnWidth(0, 60)
        
        # 버튼 상태 업데이트
        has_data = len(self.data) > 0
        self.clear_button.setEnabled(has_data)
        self.process_button.setEnabled(has_data)
        self.save_button.setEnabled(has_data)
        self.clone_button.setEnabled(has_data)
        
        # 데이터 히스토리 버튼 상태 업데이트
        self.update_data_history_buttons()
    
    def on_table_context_menu(self, position):
        """테이블 우클릭 메뉴"""
        menu = QMenu(self.data_table)
        
        # 클립보드 관련 기능들
        paste_action = menu.addAction("붙여넣기 (Ctrl+V)")
        paste_action.triggered.connect(self.on_paste_from_clipboard)
        
        if self.data_table.selectedItems():
            menu.addSeparator()
            
            # 복사 관련 기능들
            clipboard_action = menu.addAction("복사 (Ctrl+C)")
            clipboard_action.triggered.connect(self.on_copy_to_clipboard)
            
            copy_action = menu.addAction("입력 A로 복사")
            copy_action.triggered.connect(self.on_copy_to_input_a)
            
            menu.addSeparator()
            
            # 삭제 기능
            delete_action = menu.addAction("삭제 (Del)")
            delete_action.triggered.connect(self.on_delete_selected)
        
        menu.exec(self.data_table.mapToGlobal(position))
    
    def on_copy_to_input_a(self):
        """선택된 항목을 입력 A로 복사"""
        selected_rows = set()
        for item in self.data_table.selectedItems():
            selected_rows.add(item.row())
        
        if selected_rows:
            first_row = min(selected_rows)
            if first_row < len(self.data):
                shape_code = self.data[first_row]
                # 메인 윈도우의 입력 A에 복사
                main_window = self.get_main_window()
                if main_window:
                    main_window.input_a.setText(shape_code)
    
    def on_copy_to_clipboard(self):
        """선택된 항목들을 클립보드로 복사"""
        selected_rows = set()
        for item in self.data_table.selectedItems():
            selected_rows.add(item.row())
        
        if selected_rows:
            selected_codes = []
            for row in sorted(selected_rows):
                if row < len(self.data):
                    selected_codes.append(self.data[row])
            
            if selected_codes:
                clipboard_text = '\n'.join(selected_codes)
                app = QApplication.instance()
                if app:
                    app.clipboard().setText(clipboard_text)
                    main_window = self.get_main_window()
                    if main_window:
                        main_window.log(f"{len(selected_codes)}개 항목이 클립보드에 복사되었습니다.")
    
    def on_delete_selected(self):
        """선택된 항목들을 삭제"""
        selected_rows = set()
        for item in self.data_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            return
        
        reply = QMessageBox.question(
            self, "확인", 
            f"선택된 {len(selected_rows)}개 항목을 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 역순으로 정렬하여 인덱스 변경 문제 방지
            for row in sorted(selected_rows, reverse=True):
                if row < len(self.data):
                    del self.data[row]
            
            self.update_table()
            
            # 히스토리에 추가
            self.add_to_data_history(f"삭제 ({len(selected_rows)}개)")
            
            main_window = self.get_main_window()
            if main_window:
                main_window.log(f"{len(selected_rows)}개 항목이 삭제되었습니다.")
    
    def get_main_window(self):
        """메인 윈도우 참조 가져오기"""
        widget = self
        while widget:
            if isinstance(widget, ShapezGUI):
                return widget
            widget = widget.parent()
        return None
    
    def on_save_data(self):
        """데이터를 파일로 저장"""
        if not self.data:
            QMessageBox.information(self, "알림", "저장할 데이터가 없습니다.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "데이터 저장",
            f"data/{self.tab_name}.txt",
            "텍스트 파일 (*.txt);;모든 파일 (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for shape_code in self.data:
                        f.write(f"{shape_code}\n")
                QMessageBox.information(self, "완료", f"데이터가 저장되었습니다:\n{file_path}")
                main_window = self.get_main_window()
                if main_window:
                    main_window.log(f"데이터 저장 완료: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 중 오류 발생:\n{str(e)}")
    
    def on_clear_data(self):
        """데이터 지우기"""
        reply = QMessageBox.question(
            self, "확인", 
            "이 탭의 모든 데이터를 지우시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.data.clear()
            self.update_table()
            
            # 히스토리에 추가
            self.add_to_data_history("모든 데이터 지우기")
            
            main_window = self.get_main_window()
            if main_window:
                main_window.log(f"탭 '{self.tab_name}' 데이터가 지워졌습니다.")
    
    def on_process_selected(self):
        """선택된 항목 처리 (기존 기능 유지)"""
        selected_rows = set()
        for item in self.data_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.information(self, "알림", "처리할 항목을 선택하세요.")
            return
        
        selected_codes = [self.data[row] for row in sorted(selected_rows) if row < len(self.data)]
        
        # 유효성 검사
        invalid_codes = []
        for code in selected_codes:
            try:
                Shape.from_string(code)
            except Exception:
                invalid_codes.append(code)
        
        if invalid_codes:
            QMessageBox.warning(self, "경고", 
                f"다음 도형 코드가 유효하지 않습니다:\n{', '.join(invalid_codes[:5])}"
                + (f"\n... 외 {len(invalid_codes)-5}개" if len(invalid_codes) > 5 else ""))
        else:
            QMessageBox.information(self, "완료", f"{len(selected_codes)}개의 도형 코드가 유효합니다.")
        
        main_window = self.get_main_window()
        if main_window:
            main_window.log(f"선택된 {len(selected_codes)}개 항목 처리 완료")

    def on_clone_tab(self):
        """현재 탭을 복제"""
        main_window = self.get_main_window()
        if main_window:
            # 현재 데이터를 복사
            cloned_data = self.data.copy()
            
            # 새 탭 이름 생성
            clone_tab_name = f"{self.tab_name}_복제"
            
            # 새 탭 추가
            main_window.add_data_tab(clone_tab_name, cloned_data)
            
            main_window.log(f"탭 '{self.tab_name}'이 '{clone_tab_name}'로 복제되었습니다. ({len(cloned_data)}개 항목)")
        else:
            QMessageBox.warning(self, "오류", "메인 윈도우를 찾을 수 없습니다.")

    def on_data_undo(self):
        """데이터 Undo"""
        entry = self.data_history.undo()
        if entry is not None:
            data, operation_name = entry
            self.history_update_in_progress = True
            self.data = data.copy()
            self.update_table()
            self.history_update_in_progress = False
            
            main_window = self.get_main_window()
            if main_window:
                main_window.log(f"데이터 Undo: {operation_name}")
    
    def on_data_redo(self):
        """데이터 Redo"""
        entry = self.data_history.redo()
        if entry is not None:
            data, operation_name = entry
            self.history_update_in_progress = True
            self.data = data.copy()
            self.update_table()
            self.history_update_in_progress = False
            
            main_window = self.get_main_window()
            if main_window:
                main_window.log(f"데이터 Redo: {operation_name}")
    
    def add_to_data_history(self, operation_name=""):
        """현재 데이터 상태를 히스토리에 추가"""
        if not self.history_update_in_progress:
            self.data_history.add_entry(self.data, operation_name)
            self.update_data_history_buttons()

    def update_data_history_buttons(self):
        """데이터 히스토리 버튼 상태 업데이트"""
        self.data_undo_button.setEnabled(self.data_history.can_undo())
        self.data_redo_button.setEnabled(self.data_history.can_redo())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ShapezGUI()
    ex.show()
    sys.exit(app.exec()) 