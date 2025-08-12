import os
import sys
import json
import html
from typing import List, Tuple, Optional
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QFrame, QGridLayout, QTextEdit, QComboBox, QScrollArea,
    QGroupBox, QListWidget, QListWidgetItem, QProgressDialog, QCheckBox,
    QTabWidget, QMainWindow, QProgressBar, QSizePolicy, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QMenu, QTabBar, QGraphicsDropShadowEffect,
    QGraphicsScene, QGraphicsView, QGraphicsWidget, QGraphicsProxyWidget
)
from PyQt6.QtGui import QFont, QColor, QIntValidator, QKeySequence, QShortcut, QDrag, QPen, QPolygonF, QPainter, QPixmap, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QMimeData, QTimer, QPointF, QSettings, QProcess
import numpy as np

from gui.analysis_tab import build_analysis_tab
from gui.batch_tab import build_batch_tab
from gui.process_tree_tab import build_process_tree_tab
from gui.test_editor_tab import build_test_editor_tab
from gui.process_tree_view import TreeGraphicsView

# pyqtgraph 임포트
try:
    import pyqtgraph as pg
except ImportError:
    print("PyQtGraph가 설치되지 않았습니다. 'pip install pyqtgraph'를 실행해주세요.")
    pg = None

# shape.py에서 백엔드 클래스를 임포트합니다.
from shape import Quadrant, Shape, ReverseTracer, InterruptedError
from process_tree_solver import process_tree_solver, ProcessNode
from i18n import load_locales, _, set_language

# 공통 색상 매핑 (아이콘 렌더링용)
COLOR_MAP = {
    'r': '#E33', 'g': '#3E3', 'b': '#33E', 'm': '#E3E', 'c': '#3EE', 'y': '#EE3',
    'u': '#BBB', 'w': '#FFF', 'C': '#CDD', 'P': '#999'
}

# 새로 분리된 GUI 모듈들
from gui.widgets import ShapeWidget, load_icon_pixmap, LogWidget, DataTabWidget, CustomTabWidget, DragDropTableWidget, ShapeTooltipWidget
from gui.utils import InputHistory, DataHistory, OriginFinderThread
from gui.analysis_tab import build_analysis_tab
from gui.batch_tab import build_batch_tab
from gui.process_tree_tab import build_process_tree_tab
from gui.test_editor_tab import build_test_editor_tab
from gui.process_tree_view import TreeGraphicsView

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")
try:
    load_locales(LOCALES_DIR)
except Exception:
    pass

# ==============================================================================
#  GUI 프론트엔드
# ==============================================================================

def _set_label_text(widget, text):
    if isinstance(widget, QLabel):
        widget.setText(text)
    elif hasattr(widget, 'setTitle'):
        widget.setTitle(text)























# ColumnHeaderWidget 클래스는 gui/widgets.py로 이동됨


# ==============================================================================
#  분리된 클래스들
# ==============================================================================
# ShapeWidget, InputHistory, DataHistory 클래스들은 각각 gui/widgets.py, gui/utils.py로 이동됨

class ShapezGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_("app.title"))
        self._setup_language_ui_done = False

        # QSettings 초기화 및 저장된 언어 로드
        self.settings = QSettings("Shapez2", "ShapezGUI")
        try:
            saved_lang = self.settings.value("lang", None)
            if saved_lang:
                from i18n import set_language
                set_language(str(saved_lang))
        except Exception:
            pass
        self.setGeometry(100, 100, 1400, 800)
        self.setMinimumSize(1200, 700)
        
        # 기본 폰트를 맑은 고딕으로 설정
        default_font = QFont("맑은 고딕", 9)
        QApplication.instance().setFont(default_font)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # QSettings 초기화
        self.settings = QSettings("Shapez2", "ShapezGUI")

        # 히스토리 관리 객체 생성 (A, B 통합)
        self.input_history = InputHistory(100)
        self.history_update_in_progress = False  # 히스토리 업데이트 중 플래그
        
        # 출력 결과 추적 변수
        self.current_outputs = []  # [(title, shape), ...] 형태로 저장
        
        # 로그 저장 변수
        self.log_entries = []  # [(message, is_verbose), ...] 형태로 저장
        
        self.total_training_episodes = 0
        
        # 스레드 초기화
        self.origin_finder_thread = None
        
        # 테스트 데이터 초기화
        self.test_data = {}
        # 편집 필드 채우기 중(textChanged 차단) 가드 플래그
        self._suspend_field_updates = False
        
        # ===== 테스트 케이스 편집기 메서드들 =====
        def on_operation_changed(self, operation):
            """연산이 변경되었을 때 입력/출력 필드를 동적으로 표시/숨김 처리합니다."""
            # 모든 필드를 기본적으로 표시
            self.input_b_label.setVisible(True)
            self.input_b_edit.setVisible(True)
            self.expected_a_label.setVisible(True)
            self.expected_a_edit.setVisible(True)
            self.expected_b_label.setVisible(True)
            self.expected_b_edit.setVisible(True)
            
            # 연산에 따라 필드와 라벨 표시/숨김 처리
            if operation == "stack":
                # 스태커: 입력 A, B, 출력 1개 (결합된 결과)
                self.expected_a_label.setVisible(False)
                self.expected_a_edit.setVisible(False)
                self.expected_b_label.setVisible(False)
                self.expected_b_edit.setVisible(False)
            elif operation == "swap":
                # 스와퍼: 입력 A, B, 출력 A, B
                pass
            elif operation == "classifier":
                # 분류기: 입력 A만, 예상결과는 문자열
                self.input_b_label.setVisible(False)
                self.input_b_edit.setVisible(False)
                self.expected_b_label.setVisible(False)
                self.expected_b_edit.setVisible(False)
                # expected_a는 문자열 예상결과를 위해 표시
            elif operation == "exist":
                # 존재성 테스트: 입력 A만, 예상결과 불필요
                self.input_b_label.setVisible(False)
                self.input_b_edit.setVisible(False)
                self.expected_b_label.setVisible(False)
                self.expected_b_edit.setVisible(False)
                # expected_a는 존재성 테스트 결과를 위해 표시
            else:
                # 기본: 입력 A, 예상결과 A (단일 출력)
                self.input_b_label.setVisible(False)
                self.input_b_edit.setVisible(False)
                # expected_a는 단일 출력 연산을 위해 표시 (이미 True로 설정됨)
                self.expected_b_label.setVisible(False)
                self.expected_b_edit.setVisible(False)
        
        def load_test_cases(self):
            """user_tests.json 또는 tests.json 파일에서 테스트 케이스를 로드합니다."""
            try:
                # user_tests.json을 우선적으로 로드 시도
                if os.path.exists("user_tests.json"):
                    with open("user_tests.json", "r", encoding="utf-8") as f:
                        self.test_data = json.load(f)
                    self.log("프로그램 시작: user_tests.json에서 테스트 케이스를 로드했습니다.")
                else:
                    # user_tests.json이 없으면 원본 tests.json 로드
                    with open("tests.json", "r", encoding="utf-8") as f:
                        self.test_data = json.load(f)
                    self.log("프로그램 시작: 원본 tests.json에서 테스트 케이스를 로드했습니다.")
                
                # 카테고리 목록 업데이트
                self.category_combo.clear()
                for category in self.test_data.keys():
                    self.category_combo.addItem(category)
                
                # 테스트 케이스 목록 업데이트
                self.refresh_test_cases_list()
                
                total_count = sum(len(tests) for tests in self.test_data.values())
                self.log(f"총 {total_count}개 테스트 케이스가 로드되었습니다.")
                
            except FileNotFoundError:
                # 두 파일 모두 없는 경우 빈 데이터로 초기화
                self.test_data = {}
                self.log("테스트 파일을 찾을 수 없습니다. 새로 시작합니다.")
            except Exception as e:
                self.log(f"테스트 로드 중 오류 발생: {str(e)}")
                # 오류가 발생해도 빈 데이터로 초기화
                self.test_data = {}
        
        def save_test_cases(self):
            """현재 테스트 케이스를 user_tests.json 파일에 저장합니다."""
            try:
                with open("user_tests.json", "w", encoding="utf-8") as f:
                    json.dump(self.test_data, f, ensure_ascii=False, indent=2)
                
                total_count = sum(len(tests) for tests in self.test_data.values())
                self.log(f"테스트 케이스 {total_count}개를 user_tests.json에 저장했습니다.")
                
            except Exception as e:
                self.log(f"테스트 저장 중 오류 발생: {str(e)}")
                QMessageBox.critical(self, _("ui.msg.title.error"), 
                                   _("ui.msg.save_error", error=str(e)))
        
        def refresh_test_cases_list(self):
            """테스트 케이스 목록을 새로고침합니다."""
            self.test_cases_table.setRowCount(0)
            if not hasattr(self, 'test_data') or not self.test_data:
                return
            
            total_rows = sum(len(tests) for tests in self.test_data.values())
            self.test_cases_table.setRowCount(total_rows)
            
            row = 0
            for category, tests in self.test_data.items():
                for test in tests:
                    # 카테고리 (편집 불가)
                    category_item = QTableWidgetItem(category)
                    category_item.setData(Qt.ItemDataRole.UserRole, (category, test))
                    category_item.setFlags(category_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.test_cases_table.setItem(row, 0, category_item)
                    
                    # 테스트명 (편집 가능)
                    name_item = QTableWidgetItem(test.get('name', 'Unnamed'))
                    name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
                    self.test_cases_table.setItem(row, 1, name_item)
                    
                    # 연산 (편집 불가)
                    operation_item = QTableWidgetItem(test.get('operation', ''))
                    operation_item.setFlags(operation_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.test_cases_table.setItem(row, 2, operation_item)
                    
                    # 입력 (A, B) (편집 불가)
                    input_a = test.get('input_a', '')
                    input_b = test.get('input_b', '')
                    if input_b:
                        input_text = f"A: {input_a}, B: {input_b}"
                    else:
                        input_text = input_a
                    input_item = QTableWidgetItem(input_text)
                    input_item.setFlags(input_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.test_cases_table.setItem(row, 3, input_item)
                    
                    # 출력 (예상결과) (편집 불가)
                    expected_a = test.get('expected_a', '')
                    expected_b = test.get('expected_b', '')
                    
                    if expected_a and expected_b:
                        output_text = f"A: {expected_a}, B: {expected_b}"
                    elif expected_a:
                        output_text = expected_a
                    else:
                        output_text = "N/A"
                    
                    output_item = QTableWidgetItem(output_text)
                    output_item.setFlags(output_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.test_cases_table.setItem(row, 4, output_item)
                    
                    row += 1
        
        def add_test_case(self):
            """새 테스트 케이스를 추가합니다."""
            if not hasattr(self, 'test_data'):
                self.test_data = {}
            
            # 기본 카테고리 선택
            category = self.category_combo.currentText() or "새 카테고리"
            if category not in self.test_data:
                self.test_data[category] = []
                self.category_combo.addItem(category)
            
            # 새 테스트 케이스 생성
            new_test = {
                "name": "새 테스트 케이스",
                "operation": self.operation_combo.currentText(),
                "input_a": "",
                "input_b": "",
                "expected_a": "",
                "expected_b": "",
                "params": {}
            }
            
            self.test_data[category].append(new_test)
            self.refresh_test_cases_list()
            
            # 새로 추가된 항목 선택
            last_row = self.test_cases_table.rowCount() - 1
            if last_row >= 0:
                self.test_cases_table.selectRow(last_row)
                self.on_test_case_selected()
            
            self.log("새 테스트 케이스를 추가했습니다.")
        
        def on_input_field_changed(self):
            """입력 필드가 변경되었을 때 자동으로 테스트 케이스를 업데이트합니다."""
            # 프로그램적으로 필드를 채우는 중에는 업데이트를 막는다
            if getattr(self, '_suspend_field_updates', False):
                return
            
            current_row = self.test_cases_table.currentRow()
            if current_row < 0:
                return
                
            category_item = self.test_cases_table.item(current_row, 0)
            if not category_item:
                return
                
            category, test = category_item.data(Qt.ItemDataRole.UserRole)
            if not test:
                return
                
            # 현재 입력 필드 값들 가져오기
            operation = self.operation_combo.currentText()
            input_a = self.input_a_edit.text()
            input_b = self.input_b_edit.text()
            expected_a = self.expected_a_edit.text()
            expected_b = self.expected_b_edit.text()
            
            # 테스트 케이스 업데이트
            test['operation'] = operation
            test['input_a'] = input_a
            test['input_b'] = input_b
            test['expected_a'] = expected_a
            test['expected_b'] = expected_b
            
            # 테이블 목록 새로고침
            self.refresh_test_cases_list()
            
            # 현재 행 다시 선택
            self.test_cases_table.selectRow(current_row)
            
            self.log("테스트 케이스가 자동으로 업데이트되었습니다.")
        
        def show_context_menu(self, position):
            """우클릭 컨텍스트 메뉴를 표시합니다."""
            if not self.test_cases_table.selectedItems():
                return
                
            context_menu = QMenu(self.test_cases_table)
            
            # 복사 기능 (해당 행 아래에 완전히 같은 테스트케이스 추가)
            copy_action = context_menu.addAction(_("ui.ctx.copy"))
            copy_action.triggered.connect(self.on_copy_test_case)
            
            # 추가 기능 (빈 테스트케이스 추가)
            add_action = context_menu.addAction(_("ui.ctx.add"))
            add_action.triggered.connect(self.on_add_empty_test_case)
            
            context_menu.addSeparator()
            
            # 테스트 실행 기능
            run_action = context_menu.addAction(_("ui.ctx.run"))
            run_action.triggered.connect(self.on_run_single_test)
            
            context_menu.addSeparator()
            
            # 삭제 기능
            delete_action = context_menu.addAction(_("ui.ctx.delete"))
            delete_action.triggered.connect(self.delete_test_case)
            
            # 컨텍스트 메뉴 표시
            context_menu.exec(self.test_cases_table.mapToGlobal(position))
        
        def on_copy_test_case(self):
            """선택된 테스트 케이스를 해당 행 아래에 복제하여 추가"""
            current_row = self.test_cases_table.currentRow()
            if current_row < 0:
                return
                
            category_item = self.test_cases_table.item(current_row, 0)
            if not category_item:
                return
                
            category, test = category_item.data(Qt.ItemDataRole.UserRole)
            if not test:
                return
            
            # 테스트 케이스 복제
            copied_test = test.copy()
            copied_test['name'] = f"{test.get('name', 'Unnamed')} (Copy)"
            
            # 해당 행 아래에 추가
            if category in self.test_data:
                # 현재 행의 다음 위치에 삽입
                all_tests = []
                for cat, tests in self.test_data.items():
                    for t in tests:
                        all_tests.append((cat, t))
                
                # 현재 테스트의 위치 찾기
                current_index = -1
                for i, (cat, t) in enumerate(all_tests):
                    if cat == category and t == test:
                        current_index = i
                        break
                
                if current_index >= 0:
                    # 현재 테스트 다음 위치에 복사본 삽입
                    all_tests.insert(current_index + 1, (category, copied_test))
                    
                    # 테스트 데이터 재구성
                    self.test_data = {}
                    for cat, t in all_tests:
                        if cat not in self.test_data:
                            self.test_data[cat] = []
                        self.test_data[cat].append(t)
                    
                    # 테이블 새로고침
                    self.refresh_test_cases_list()
                    
                    # 복사된 행 선택
                    self.test_cases_table.selectRow(current_row + 1)
                    
                    self.log(f"테스트 케이스 '{test.get('name', 'Unnamed')}'을(를) 복제했습니다.")
        
        def on_add_empty_test_case(self):
            """선택된 행에 빈 테스트케이스 추가 (Add Test Case 기능 수행)"""
            current_row = self.test_cases_table.currentRow()
            if current_row < 0:
                return
                
            category_item = self.test_cases_table.item(current_row, 0)
            if not category_item:
                return
                
            category, test = category_item.data(Qt.ItemDataRole.UserRole)
            if not test:
                return
            
            # 빈 테스트 케이스 생성
            empty_test = {
                'name': 'New Test Case',
                'operation': '',
                'input_a': '',
                'input_b': '',
                'expected_a': '',
                'expected_b': '',
                'params': {}
            }
            
            # 해당 행에 빈 테스트케이스 삽입
            if category in self.test_data:
                # 현재 테스트의 위치 찾기
                test_index = self.test_data[category].index(test)
                if test_index >= 0:
                    # 현재 테스트 다음 위치에 빈 테스트케이스 삽입
                    self.test_data[category].insert(test_index + 1, empty_test)
                    
                    # 테이블 새로고침
                    self.refresh_test_cases_list()
                    
                    # 새로 추가된 행 선택
                    self.test_cases_table.selectRow(current_row + 1)
                    
                    # 편집 필드에 빈 테스트케이스 정보 설정
                    self.on_test_case_selected()
                    
                    self.log(f"빈 테스트 케이스를 '{category}' 카테고리에 추가했습니다.")
        
        def on_run_single_test(self):
            """선택된 테스트 케이스를 실행하고 결과를 검증합니다."""
            current_row = self.test_cases_table.currentRow()
            if current_row < 0:
                return
                
            category_item = self.test_cases_table.item(current_row, 0)
            if not category_item:
                return
                
            category, test = category_item.data(Qt.ItemDataRole.UserRole)
            if not test:
                return
            
            # 테스트 정보 추출
            name = test.get('name', 'Unnamed')
            operation = test.get('operation', '')
            input_a_str = test.get('input_a', '')
            input_b_str = test.get('input_b', '')
            params = test.get('params', {})
            
            if not input_a_str:
                self.log(f"❌ 테스트 실행 실패: {name} - 입력 A가 비어있습니다.")
                return
            
            # 입력 필드에 테스트 데이터 설정
            self.input_a.setText(input_a_str)
            if input_b_str:
                self.input_b.setText(input_b_str)
            else:
                self.input_b.clear()
            
            # 테스트 실행 및 검증
            try:
                from shape import Shape
                shape_a = Shape.from_string(input_a_str)
                
                # swap 연산 처리 (이중 입력/출력)
                if operation == "swap":
                    if not input_b_str:
                        self.log(f"❌ 테스트 실행 실패: {name} - 'swap'은 'input_b'가 필요합니다.")
                        return
                    
                    shape_b = Shape.from_string(input_b_str)
                    actual_a, actual_b = Shape.swap(shape_a, shape_b)
                    actual_a_code, actual_b_code = repr(actual_a), repr(actual_b)
                    
                    expected_a_shape = Shape.from_string(test.get('expected_a', ""))
                    expected_b_shape = Shape.from_string(test.get('expected_b', ""))
                    expected_a_code, expected_b_code = repr(expected_a_shape), repr(expected_b_shape)
                    
                    # 결과 검증
                    if actual_a_code == expected_a_code and actual_b_code == expected_b_code:
                        self.log(f"✅ 테스트 통과: {name}")
                        self.log(f"  - 입력A: {input_a_str}, 입력B: {input_b_str}")
                        self.log(f"  - 예상A: {expected_a_code}, 예상B: {expected_b_code}")
                        self.log(f"  - 실제A: {actual_a_code}, 실제B: {actual_b_code}")
                    else:
                        self.log(f"❌ 테스트 실패: {name}")
                        self.log(f"  - 입력A: {input_a_str}, 입력B: {input_b_str}")
                        self.log(f"  - 예상A: {expected_a_code}, 예상B: {expected_b_code}")
                        self.log(f"  - 실제A: {actual_a_code}, 실제B: {actual_b_code}")
                    return
                
                # classifier 연산 처리 (특별한 출력 형식)
                if operation == "classifier":
                    result_string, reason = shape_a.classifier()
                    expected = test.get('expected_a', "")
                    
                    if expected in result_string:
                        self.log(f"✅ 테스트 통과: {name}")
                        self.log(f"  - 입력: {input_a_str}")
                        self.log(f"  - 예상: {expected}")
                        self.log(f"  - 실제: {result_string} (사유: {reason})")
                    else:
                        self.log(f"❌ 테스트 실패: {name}")
                        self.log(f"  - 입력: {input_a_str}")
                        self.log(f"  - 예상: {expected}")
                        self.log(f"  - 실제: {result_string} (사유: {reason})")
                    return
                
                # 일반 연산 처리
                actual_shape = None
                if input_b_str:
                    shape_b = Shape.from_string(input_b_str)
                    if operation == "stack":
                        actual_shape = Shape.stack(shape_a, shape_b)
                    else:
                        self.log(f"❌ 테스트 실행 실패: {name} - 연산 '{operation}'은 입력 B를 지원하지 않습니다.")
                        return
                else:
                    if operation == "apply_physics":
                        actual_shape = shape_a.apply_physics()
                    elif operation == "destroy_half":
                        actual_shape = shape_a.destroy_half()
                    elif operation == "push_pin":
                        actual_shape = shape_a.push_pin()
                    elif operation == "paint":
                        actual_shape = shape_a.paint(params.get('color', 'r'))
                    elif operation == "crystal_generator":
                        actual_shape = shape_a.crystal_generator(params.get('color', 'r'))
                    elif operation == "rotate":
                        actual_shape = shape_a.rotate(params.get('clockwise', True))
                    elif operation == "cutter":
                        actual_shape = shape_a.cutter()
                    elif operation == "simple_cutter":
                        actual_shape = shape_a.simple_cutter()
                    elif operation == "quad_cutter":
                        actual_shape = shape_a.quad_cutter()
                    elif operation == "mirror":
                        actual_shape = shape_a.mirror()
                    elif operation == "cornerize":
                        actual_shape = shape_a.cornerize()
                    elif operation == "simplify":
                        actual_shape = shape_a.simplify()
                    elif operation == "detail":
                        actual_shape = shape_a.detail()
                    elif operation == "corner1":
                        actual_shape = shape_a.corner1()
                    elif operation == "reverse":
                        actual_shape = shape_a.reverse()
                    else:
                        self.log(f"❌ 테스트 실행 실패: {name} - 알 수 없는 연산: {operation}")
                        return
                
                # 결과 검증
                actual_code = repr(actual_shape)
                expected_shape = Shape.from_string(test.get('expected_a', ""))
                expected_code = repr(expected_shape)
                
                if actual_code == expected_code:
                    self.log(f"✅ 테스트 통과: {name}")
                    self.log(f"  - 입력: {input_a_str}")
                    self.log(f"  - 예상: {expected_code}")
                    self.log(f"  - 실제: {actual_code}")
                else:
                    self.log(f"❌ 테스트 실패: {name}")
                    self.log(f"  - 입력: {input_a_str}")
                    self.log(f"  - 예상: {expected_code}")
                    self.log(f"  - 실제: {actual_code}")
                
            except Exception as e:
                self.log(f"🔥 테스트 실행 오류: {name} - {e.__class__.__name__}: {e}")
                import traceback
                self.log(traceback.format_exc())
        
        def reset_tests(self):
            """원본 tests.json 파일을 불러와 모든 변경사항을 초기화합니다."""
            try:
                # 원본 tests.json 파일 불러오기
                if os.path.exists("tests.json"):
                    with open("tests.json", "r", encoding="utf-8") as f:
                        original_data = json.load(f)
                    
                    # 현재 테스트 데이터를 원본으로 교체
                    self.test_data = original_data
                    
                    # 테이블 새로고침
                    self.refresh_test_cases_list()
                    
                    # 편집 필드 초기화
                    self.clear_test_edit_fields()
                    
                    total_count = sum(len(tests) for tests in self.test_data.values())
                    self.log(f"초기화 완료: 원본 tests.json에서 {total_count}개 테스트 케이스를 불러왔습니다.")
                    
                else:
                    self.log("원본 tests.json 파일을 찾을 수 없습니다.")
                    QMessageBox.warning(self, _("ui.msg.title.warning"), 
                                      "원본 tests.json 파일이 존재하지 않습니다.")
                    
            except Exception as e:
                self.log(f"테스트 초기화 중 오류 발생: {str(e)}")
                QMessageBox.critical(self, _("ui.msg.title.error"), 
                                   f"테스트 초기화 중 오류가 발생했습니다:\n{str(e)}")
        

        
        def on_test_rows_reordered(self, from_row, to_row):
            """드래그앤드롭으로 테스트 케이스 순서가 변경되었을 때 호출됩니다."""
            # 테스트 데이터에서 순서 조절
            all_tests = []
            for category, tests in self.test_data.items():
                for test in tests:
                    all_tests.append((category, test))
            
            if 0 <= from_row < len(all_tests) and 0 <= to_row < len(all_tests):
                # 순서 조절
                item = all_tests.pop(from_row)
                all_tests.insert(to_row, item)
                
                # 테스트 데이터 재구성
                self.test_data = {}
                for category, test in all_tests:
                    if category not in self.test_data:
                        self.test_data[category] = []
                    self.test_data[category].append(test)
                
                # 테이블 새로고침
                self.refresh_test_cases_list()
                
                # 드롭된 행 선택
                self.test_cases_table.selectRow(to_row)
                
                self.log(f"테스트 케이스 순서를 조절했습니다.")
        
        def on_table_item_changed(self, item):
            """테이블 셀이 편집되었을 때 실제 데이터를 업데이트합니다."""
            if not item:
                return
                
            current_row = item.row()
            current_column = item.column()
            
            # 테스트명 컬럼(1)만 편집 가능
            if current_column != 1:
                return
                
            category_item = self.test_cases_table.item(current_row, 0)
            category, test = category_item.data(Qt.ItemDataRole.UserRole)
            if not test:
                return
                
            # 테스트명 업데이트
            new_name = item.text()
            if new_name != test.get('name', ''):
                test['name'] = new_name
                self.log(f"테스트명을 '{new_name}'으로 업데이트했습니다.")
        
        def on_test_case_selected(self):
            """테스트 케이스가 선택되었을 때 편집 필드를 업데이트합니다."""
            current_row = self.test_cases_table.currentRow()
            if current_row < 0:
                return
            
            category_item = self.test_cases_table.item(current_row, 0)
            if not category_item:
                return
                
            category, test = category_item.data(Qt.ItemDataRole.UserRole)
            
            # 카테고리 설정
            index = self.category_combo.findText(category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
            else:
                # 연산이 목록에 없으면 첫 번째 항목으로 설정
                self.operation_combo.setCurrentIndex(0)
            
            # 필드들 설정
            self.test_name_edit.setText(test.get("name", ""))
            
            operation = test.get("operation", "")
            index = self.operation_combo.findText(operation)
            if index >= 0:
                self.operation_combo.setCurrentIndex(index)
            else:
                # 연산이 목록에 없으면 첫 번째 항목으로 설정
                self.operation_combo.setCurrentIndex(0)
            
            # 연산에 따른 필드 상태를 먼저 업데이트
            self.on_operation_changed(self.operation_combo.currentText())
            
            # 필드 채우는 동안 업데이트 중단
            self._suspend_field_updates = True
            try:
                # 그 다음에 데이터를 필드에 설정
                self.input_a_edit.setText(test.get("input_a", ""))
                self.input_b_edit.setText(test.get("input_b", ""))
                self.expected_a_edit.setText(test.get("expected_a", ""))
                self.expected_b_edit.setText(test.get("expected_b", ""))
                
                # 매개변수 JSON 문자열로 변환
                params = test.get("params", {})
                if params:
                    self.params_edit.setText(json.dumps(params, ensure_ascii=False))
                else:
                    self.params_edit.clear()
            finally:
                self._suspend_field_updates = False
        

        

        

        
        def clear_test_edit_fields(self):
            """테스트 편집 필드들을 초기화합니다."""
            self.test_name_edit.clear()
            self.operation_combo.setCurrentIndex(0)
            self.input_a_edit.clear()
            self.input_b_edit.clear()
            self.expected_a_edit.clear()
            self.expected_b_edit.clear()
            self.params_edit.clear()
            
            # 연산에 따른 필드 상태 업데이트
            self.on_operation_changed(self.operation_combo.currentText())
        
        # 메서드를 클래스에 바인딩
        self.on_operation_changed = on_operation_changed.__get__(self, ShapezGUI)
        self.load_test_cases = load_test_cases.__get__(self, ShapezGUI)
        self.save_test_cases = save_test_cases.__get__(self, ShapezGUI)
        self.refresh_test_cases_list = refresh_test_cases_list.__get__(self, ShapezGUI)
        self.add_test_case = add_test_case.__get__(self, ShapezGUI)
        self.on_test_case_selected = on_test_case_selected.__get__(self, ShapezGUI)
        self.on_table_item_changed = on_table_item_changed.__get__(self, ShapezGUI)
        self.on_input_field_changed = on_input_field_changed.__get__(self, ShapezGUI)
        self.show_context_menu = show_context_menu.__get__(self, ShapezGUI)
        self.on_copy_test_case = on_copy_test_case.__get__(self, ShapezGUI)
        self.on_add_empty_test_case = on_add_empty_test_case.__get__(self, ShapezGUI)
        self.on_run_single_test = on_run_single_test.__get__(self, ShapezGUI)
        self.reset_tests = reset_tests.__get__(self, ShapezGUI)
        self.on_test_rows_reordered = on_test_rows_reordered.__get__(self, ShapezGUI)
        self.clear_test_edit_fields = clear_test_edit_fields.__get__(self, ShapezGUI)
        
        self.initUI()
        
        # 테스트 에디터 단축키 설정 (UI 초기화 완료 후)
        self.setup_test_editor_shortcuts()
        
        # 초기 언어 적용
        try:
            self._retranslate_ui()
        except Exception:
            pass
        
        # 저장된 설정 불러오기 (initUI 호출 후에 위젯들이 초기화된 상태에서 값을 로드)
        self.load_settings()
        
        # 테스트 에디터 시그널 연결 및 초기화
        # 버튼 클릭 이벤트 연결
        self.save_tests_btn.clicked.connect(self.save_test_cases)
        self.reset_tests_btn.clicked.connect(self.reset_tests)
        
        # 테스트 케이스 선택 이벤트 연결
        self.test_cases_table.itemSelectionChanged.connect(self.on_test_case_selected)
        
        # 테이블 셀 편집 완료 시그널 연결
        self.test_cases_table.itemChanged.connect(self.on_table_item_changed)
        
        # 키보드 삭제 및 우클릭 컨텍스트 메뉴 설정
        self.test_cases_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.test_cases_table.customContextMenuRequested.connect(self.show_context_menu)
        
        # 드래그앤드롭으로 순서 조절 설정 (DragDropTableWidget에서 자동 처리)
        self.test_cases_table.rows_reordered.connect(self.on_test_rows_reordered)
        
        # 편집 버튼 이벤트 연결 제거 - 자동반영, 키보드/우클릭 삭제, 드래그앤드롭 순서 조절로 대체
        
        # 연산 변경 시 필드 표시/숨김 처리
        self.operation_combo.currentTextChanged.connect(self.on_operation_changed)
        
        # 입력 필드 변경 시 자동 반영 (시그널은 가드 플래그로 보호)
        self.input_a_edit.textChanged.connect(self.on_input_field_changed)
        self.input_b_edit.textChanged.connect(self.on_input_field_changed)
        self.expected_a_edit.textChanged.connect(self.on_input_field_changed)
        self.expected_b_edit.textChanged.connect(self.on_input_field_changed)
        
        # 초기 필드 상태 설정
        self.on_operation_changed("apply_physics")
        
        # 초기 테스트 데이터 로드
        self.load_test_cases()
        




    def load_settings(self):
        """저장된 설정을 불러옵니다."""
        input_a_text = self.settings.value("input_a", "crcrcrcr")
        input_b_text = self.settings.value("input_b", "")
        last_data_path = self.settings.value("last_data_path", "")
        auto_apply_enabled = self.settings.value("auto_apply_enabled", False, type=bool)
        
        # 위젯이 초기화된 후에 값을 설정
        self.input_a.setText(input_a_text)
        self.input_b.setText(input_b_text)
        self.last_opened_data_path = last_data_path  # 초기화

        if last_data_path and os.path.exists(last_data_path):
            self.file_path_label.setText(last_data_path)
            self.file_path_label.setStyleSheet("color: black;")
            self.log_verbose(f"마지막으로 열었던 파일 경로 불러옴: {last_data_path}")
            # 파일 선택 후 자동으로 로드
            self.load_file(last_data_path)
        else:
            self.log_verbose("저장된 파일 경로가 없거나 유효하지 않습니다.")
        
        # 파일 로드가 성공하지 않았을 때만 샘플데이터 추가
        if not self.file_load_success:
            self.add_data_tab(_("ui.sample"), ["CuCuCuCu", "RrRrRrRr", "P-P-P-P-"])

        # 설정 로드 후, 히스토리 초기 상태를 업데이트합니다.
        self.input_history.add_entry(input_a_text, input_b_text)
        self.update_history_buttons()
        self.update_input_display() # 초기 입력 표시
        
        # 자동 적용 체크박스 상태 복원 (위젯이 생성된 후에 설정)
        if hasattr(self, 'auto_apply_checkbox'):
            self.auto_apply_checkbox.setChecked(auto_apply_enabled)
    
    def setup_test_editor_shortcuts(self):
        """테스트 에디터 단축키 설정"""
        # Delete: 선택된 테스트 케이스 삭제
        self.delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.test_cases_table)
        self.delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_test_case)
        
        self.log("테스트 에디터 단축키 설정 완료 (Delete)")
    
    def delete_test_case(self):
        """선택된 테스트 케이스를 삭제합니다."""
        current_row = self.test_cases_table.currentRow()
        if current_row < 0:
            return
            
        category_item = self.test_cases_table.item(current_row, 0)
        if not category_item:
            return
            
        category, test = category_item.data(Qt.ItemDataRole.UserRole)
        if not test:
            return
        
        # 확인 메시지
        reply = QMessageBox.question(
            self, 
            _("ui.msg.title.confirm"), 
            _("ui.msg.confirm_delete_test", name=test.get('name', 'Unnamed')),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 테스트 데이터에서 제거
            if category in self.test_data and test in self.test_data[category]:
                self.test_data[category].remove(test)
                
                # 카테고리가 비어있으면 카테고리도 제거
                if not self.test_data[category]:
                    del self.test_data[category]
                    self.category_combo.removeItem(self.category_combo.findText(category))
                
                # 테이블 새로고침
                self.refresh_test_cases_list()
                
                # 편집 필드 초기화
                self.clear_test_edit_fields()
                
                self.log(f"테스트 케이스 '{test.get('name', 'Unnamed')}'을(를) 삭제했습니다.")

    def initUI(self):
        main_layout = QVBoxLayout(self.central_widget)

        self.log_output = LogWidget()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("맑은 고딕", 9))
        self.log_output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # 전체 창의 상단 부분을 위한 메인 가로 레이아웃
        main_content_hbox = QHBoxLayout()

        # 왼쪽 패널 (언어, 모드 설정, 입력, 건물 작동)
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        # 언어 선택 바 (왼쪽 패널 맨 위)
        lang_bar = QHBoxLayout()
        globe_label = QLabel()
        globe_label.setToolTip(_("ui.lang.label"))
        globe_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        globe_label.setFixedSize(18, 18)
        # 아이콘 파일을 icons/ 또는 icon/ 경로에서 로드
        pm = load_icon_pixmap("globe.png", 16) or load_icon_pixmap("globe.svg", 16)
        globe_label.setPixmap(pm)
        lang_bar.addWidget(globe_label)
        self.lang_label = QLabel(_("ui.lang.label"))
        lang_bar.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        # Language names should be displayed in their native forms and not localized
        self.lang_combo.addItem("한국어", userData="ko")
        self.lang_combo.addItem("English", userData="en")
        # 시스템 언어에 맞춰 선택
        from i18n import get_language, set_language
        current_lang = get_language()
        index = 0 if current_lang == "ko" else 1
        self.lang_combo.setCurrentIndex(index)
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        lang_bar.addWidget(self.lang_combo)
        lang_bar.addStretch()
        left_panel.addLayout(lang_bar)
        
        mode_group = QGroupBox(_("ui.mode"))
        mode_layout = QGridLayout(mode_group)
        
        self.max_layers_combo = QComboBox()
        # 텍스트는 번역 키, 값은 숫자 userData로 보관
        self.max_layers_combo.addItem(_("ui.max_layers.option.5"), 5)
        self.max_layers_combo.addItem(_("ui.max_layers.option.4"), 4)
        self.max_layers_combo.currentIndexChanged.connect(self.on_max_layers_changed)
        self._label_max_layers = QLabel(_("ui.max_layers"))
        mode_layout.addWidget(self._label_max_layers, 0, 0)
        mode_layout.addWidget(self.max_layers_combo, 0, 1)
        
        self.max_depth_input = QLineEdit("4")
        self.max_depth_input.editingFinished.connect(self.on_max_depth_changed)
        mode_layout.addWidget(QLabel(_("ui.max_depth")), 1, 0)
        mode_layout.addWidget(self.max_depth_input, 1, 1)

        self.max_physics_height_input = QLineEdit("2")
        mode_layout.addWidget(QLabel(_("ui.max_physics_height")), 2, 0)
        mode_layout.addWidget(self.max_physics_height_input, 2, 1)



        left_panel.addWidget(mode_group)

        # 언어 변경 시 재번역을 위한 UI 레퍼런스 수집
        self._i18n_widgets = {
            "window_title": self,
            "mode_group": mode_group,
            "max_layers_label": None,
            "input_group": None,
            "input_a_label": None,
            "input_b_label": None,
            "stack_btn": None,
            "swap_btn": None,
            "apply_btn": None,
        }


        self.on_max_layers_changed()
        self.on_max_depth_changed()

        input_group = QGroupBox(_("ui.input.group")); input_layout = QGridLayout(input_group)
        self.input_a = QLineEdit(); self.input_a.setObjectName("입력 A") # 초기값은 load_settings에서 설정
        self.input_b = QLineEdit(); self.input_b.setObjectName("입력 B") # 초기값은 load_settings에서 설정
        
        # 실시간 출력 업데이트를 위한 텍스트 변경 이벤트 연결
        self.input_a.textChanged.connect(self.on_input_a_changed)
        self.input_b.textChanged.connect(self.on_input_b_changed)
        
        # 입력 A 행
        self._label_input_a = QLabel(_("ui.input.a"))
        input_layout.addWidget(self._label_input_a, 0, 0)
        input_layout.addWidget(self.input_a, 0, 1)
        
        # 입력 B 행
        self._label_input_b = QLabel(_("ui.input.b"))
        input_layout.addWidget(self._label_input_b, 1, 0)
        input_layout.addWidget(self.input_b, 1, 1)
        
        # 통합 Undo/Redo 버튼 (입력 A 행에 배치)
        self.undo_button = QPushButton("↶")
        self.undo_button.setMaximumWidth(30)
        self.undo_button.setToolTip(_("ui.tooltip.undo"))
        self.undo_button.clicked.connect(self.on_undo)
        self.undo_button.setEnabled(False)
        input_layout.addWidget(self.undo_button, 0, 2)
        
        self.redo_button = QPushButton("↷")
        self.redo_button.setMaximumWidth(30)
        self.redo_button.setToolTip(_("ui.tooltip.redo"))
        self.redo_button.clicked.connect(self.on_redo)
        self.redo_button.setEnabled(False)
        input_layout.addWidget(self.redo_button, 0, 3)
        
        left_panel.addWidget(input_group)
        
        # 초기 히스토리 항목 추가 (QSettings 로드 후 load_settings에서 add_entry 호출)
        # self.input_history.add_entry("crcrcrcr", "")
        
        # 키보드 단축키 설정
        self.setup_shortcuts()
        
        # 초기 히스토리 버튼 상태 업데이트 (QSettings 로드 후 load_settings에서 update_history_buttons 호출)
        # self.update_history_buttons()
        
        # 엔터키로 적용 버튼 활성화
        self.setup_enter_key_for_apply()
        
        control_group = QGroupBox(_("건물 작동")); control_layout = QGridLayout(control_group)
        
        # 건물 작동 버튼들을 저장
        self.destroy_half_btn = QPushButton("절반 파괴기 (A)")
        self.destroy_half_btn.clicked.connect(self.on_destroy_half)
        self.destroy_half_btn.setToolTip(_("tooltip.destroy_half"))
        # 아이콘 추가
        icon = load_icon_pixmap("half-destroyer.png", 16)
        if icon:
            self.destroy_half_btn.setIcon(QIcon(icon))
        control_layout.addWidget(self.destroy_half_btn, 0, 0, 1, 1)
        
        self.stack_btn = QPushButton(_("스태커 (A가 아래)"))
        self.stack_btn.clicked.connect(self.on_stack)
        self.stack_btn.setToolTip(_("tooltip.stack"))
        # 아이콘 추가
        icon = load_icon_pixmap("stacker.png", 16)
        if icon:
            self.stack_btn.setIcon(QIcon(icon))
        control_layout.addWidget(self.stack_btn, 0, 1, 1, 1)
        
        self.push_pin_btn = QPushButton("핀 푸셔 (A)")
        self.push_pin_btn.clicked.connect(self.on_push_pin)
        self.push_pin_btn.setToolTip(_("tooltip.push_pin"))
        # 아이콘 추가
        icon = load_icon_pixmap("pin-pusher.png", 16)
        if icon:
            self.push_pin_btn.setIcon(QIcon(icon))
        control_layout.addWidget(self.push_pin_btn, 1, 0)
        
        self.apply_physics_btn = QPushButton("물리 적용 (A)")
        self.apply_physics_btn.clicked.connect(self.on_apply_physics)
        self.apply_physics_btn.setToolTip(_("tooltip.apply_physics"))
        control_layout.addWidget(self.apply_physics_btn, 1, 1)
        
        self.swap_btn = QPushButton(_("스와퍼 (A, B)"))
        self.swap_btn.clicked.connect(self.on_swap)
        self.swap_btn.setToolTip(_("tooltip.swap"))
        # 아이콘 추가
        icon = load_icon_pixmap("swapper.png", 16)
        if icon:
            self.swap_btn.setIcon(QIcon(icon))
        control_layout.addWidget(self.swap_btn, 2, 0)
        
        self.cutter_btn = QPushButton("커터 (A)")
        self.cutter_btn.clicked.connect(self.on_cutter)
        self.cutter_btn.setToolTip(_("tooltip.cutter"))
        # 아이콘 추가
        icon = load_icon_pixmap("cutter.png", 16)
        if icon:
            self.cutter_btn.setIcon(QIcon(icon))
        control_layout.addWidget(self.cutter_btn, 2, 1)
        
        rotate_hbox = QHBoxLayout()
        self.rotate_cw_btn = QPushButton("90 회전")
        self.rotate_cw_btn.clicked.connect(lambda: self.on_rotate(True))
        self.rotate_cw_btn.setToolTip(_("tooltip.rotate_cw"))
        # 아이콘 추가
        icon = load_icon_pixmap("rotator-cw.png", 16)
        if icon:
            self.rotate_cw_btn.setIcon(QIcon(icon))
        rotate_hbox.addWidget(self.rotate_cw_btn)

        self.rotate_ccw_btn = QPushButton("270 회전")
        self.rotate_ccw_btn.clicked.connect(lambda: self.on_rotate(False))
        self.rotate_ccw_btn.setToolTip(_("tooltip.rotate_ccw"))
        # 아이콘 추가
        icon = load_icon_pixmap("rotator-ccw.png", 16)
        if icon:
            self.rotate_ccw_btn.setIcon(QIcon(icon))
        rotate_hbox.addWidget(self.rotate_ccw_btn)
        control_layout.addLayout(rotate_hbox, 3, 0, 1, 2)
        
        self.rotate_180_btn = QPushButton("180 회전")
        self.rotate_180_btn.clicked.connect(self.on_rotate_180_building)
        self.rotate_180_btn.setToolTip(_("tooltip.rotate_180"))
        # 아이콘 추가
        icon = load_icon_pixmap("rotator-180.png", 16)
        if icon:
            self.rotate_180_btn.setIcon(QIcon(icon))
        control_layout.addWidget(self.rotate_180_btn, 4, 0)
        
        self.classifier_btn = QPushButton("분류기 (A)")
        self.classifier_btn.clicked.connect(self.on_classifier)
        self.classifier_btn.setToolTip(_("tooltip.classifier"))
        control_layout.addWidget(self.classifier_btn, 4, 1, 1, 1)
        
        self.simple_cutter_btn = QPushButton("심플 커터 (A)")
        self.simple_cutter_btn.clicked.connect(self.on_simple_cutter)
        self.simple_cutter_btn.setToolTip(_("tooltip.simple_cutter"))
        control_layout.addWidget(self.simple_cutter_btn, 5, 0, 1, 1)
        
        self.quad_cutter_btn = QPushButton("쿼드 커터 (A)")
        self.quad_cutter_btn.clicked.connect(self.on_quad_cutter)
        self.quad_cutter_btn.setToolTip(_("tooltip.quad_cutter"))
        control_layout.addWidget(self.quad_cutter_btn, 5, 1, 1, 1)
        
        paint_hbox = QHBoxLayout()
        paint_hbox.addWidget(QLabel("페인터:"))
        self.paint_color = QComboBox()
        for color in Quadrant.VALID_COLORS:
            # 색상 아이콘 생성 (14x14, 검은색 테두리)
            icon_pixmap = QPixmap(14, 14)
            icon_pixmap.fill(QColor(COLOR_MAP.get(color, '#000')))
            # 검은색 테두리 추가
            painter = QPainter(icon_pixmap)
            painter.setPen(QPen(QColor('black'), 1))
            painter.drawRect(0, 0, 13, 13)
            painter.end()
            self.paint_color.addItem(QIcon(icon_pixmap), color)
        paint_hbox.addWidget(self.paint_color)
        self.paint_color.setFixedWidth(60)  # 드롭다운 너비를 반절로 고정
        self.paint_btn = QPushButton("칠하기")
        self.paint_btn.clicked.connect(self.on_paint)
        self.paint_btn.setToolTip(_("tooltip.paint"))
        # 아이콘 추가
        icon = load_icon_pixmap("painter.png", 16)
        if icon:
            self.paint_btn.setIcon(QIcon(icon))
        paint_hbox.addWidget(self.paint_btn)
        control_layout.addLayout(paint_hbox, 6, 0, 1, 2) # Moved to row 6
        
        crystal_hbox = QHBoxLayout()
        crystal_hbox.addWidget(QLabel("크리스탈 생성:"))
        self.crystal_color = QComboBox()
        for color in [c for c in Quadrant.VALID_COLORS if c != 'u']:
            # 색상 아이콘 생성 (14x14, 검은색 테두리)
            icon_pixmap = QPixmap(14, 14)
            icon_pixmap.fill(QColor(COLOR_MAP.get(color, '#000')))
            # 검은색 테두리 추가
            painter = QPainter(icon_pixmap)
            painter.setPen(QPen(QColor('black'), 1))
            painter.drawRect(0, 0, 13, 13)
            painter.end()
            self.crystal_color.addItem(QIcon(icon_pixmap), color)
        crystal_hbox.addWidget(self.crystal_color)
        self.crystal_color.setFixedWidth(60)  # 드롭다운 너비를 반절로 고정
        self.crystal_btn = QPushButton("생성")
        self.crystal_btn.clicked.connect(self.on_crystal_gen)
        self.crystal_btn.setToolTip(_("tooltip.crystal"))
        # 아이콘 추가
        icon = load_icon_pixmap("crystal-generator.png", 16)
        if icon:
            self.crystal_btn.setIcon(QIcon(icon))
        crystal_hbox.addWidget(self.crystal_btn)
        control_layout.addLayout(crystal_hbox, 7, 0, 1, 2) # Moved to row 7
        
        # (이전 위치에서 이동됨) 분류기 버튼은 180회전과 같은 행으로 이동
        
        # 적용 버튼과 자동 적용 체크박스
        self.apply_button = QPushButton(_("ui.apply_outputs"))
        self.apply_button.clicked.connect(self.on_apply_outputs)
        self.apply_button.setEnabled(False)  # 초기에는 비활성화
        self.apply_button.setToolTip(_("tooltip.apply_outputs") if _("tooltip.apply_outputs") != "tooltip.apply_outputs" else "출력 결과를 입력 필드에 적용합니다.\n\n예시:\n출력 A: CuCu\n출력 B: P-P-\n적용 후: 입력 A = CuCu, 입력 B = P-P-")
        control_layout.addWidget(self.apply_button, 8, 0)
        
        self.auto_apply_checkbox = QCheckBox("자동 적용")
        self.auto_apply_checkbox.setToolTip(_("tooltip.apply_outputs"))
        self.auto_apply_checkbox.setText(_("자동 적용"))
        control_layout.addWidget(self.auto_apply_checkbox, 8, 1)

        # 버튼 최소 너비 통일 (라벨 길이에 따른 최대 sizeHint 기반)
        try:
            uniform_min_buttons = [
                self.rotate_cw_btn,
                self.rotate_ccw_btn,
                self.rotate_180_btn,
                self.destroy_half_btn,
                self.stack_btn,
                self.push_pin_btn,
                self.apply_physics_btn,
                self.swap_btn,
                self.cutter_btn,
                self.simple_cutter_btn,
                self.quad_cutter_btn,
                self.classifier_btn,
                self.paint_btn,
                self.crystal_btn,
            ]
            max_w = 0
            for btn in uniform_min_buttons:
                if btn is not None:
                    max_w = max(max_w, btn.sizeHint().width())
            min_w = max_w + 0
            for btn in uniform_min_buttons:
                if btn is not None:
                    btn.setMinimumWidth(min_w)
        except Exception:
            pass

        left_panel.addWidget(control_group)
        
        # 추가 데이터 처리 컨테이너
        data_process_group = QGroupBox("데이터 처리")
        data_process_layout = QGridLayout(data_process_group)
        
        self.simplify_btn = QPushButton(_("ui.btn.simplify"))
        self.simplify_btn.clicked.connect(self.on_simplify)
        self.simplify_btn.setToolTip(_("tooltip.simplify"))
        data_process_layout.addWidget(self.simplify_btn, 0, 0)
        
        self.detail_btn = QPushButton(_("ui.btn.detail"))
        self.detail_btn.clicked.connect(self.on_detail)
        self.detail_btn.setToolTip(_("tooltip.detail"))
        data_process_layout.addWidget(self.detail_btn, 0, 1)
        
        self.corner_3q_btn = QPushButton(_("ui.btn.corner1"))
        self.corner_3q_btn.clicked.connect(self.on_corner_1q)
        self.corner_3q_btn.setToolTip(_("tooltip.corner1"))
        data_process_layout.addWidget(self.corner_3q_btn, 1, 0)
        
        self.remove_impossible_btn = QPushButton(_("ui.btn.remove_impossible"))
        self.remove_impossible_btn.clicked.connect(self.on_remove_impossible)
        self.remove_impossible_btn.setToolTip(_("tooltip.remove_impossible"))
        data_process_layout.addWidget(self.remove_impossible_btn, 1, 1)
        
        self.reverse_btn = QPushButton(_("ui.btn.reverse"))
        self.reverse_btn.clicked.connect(self.on_reverse)
        self.reverse_btn.setToolTip(_("tooltip.reverse"))
        data_process_layout.addWidget(self.reverse_btn, 2, 0)
        
        self.corner_btn = QPushButton(_("ui.btn.corner"))
        self.corner_btn.clicked.connect(self.on_corner)
        self.corner_btn.setToolTip(_("tooltip.corner"))
        data_process_layout.addWidget(self.corner_btn, 2, 1)
        
        self.claw_btn = QPushButton(_("ui.btn.claw"))
        self.claw_btn.clicked.connect(self.on_claw)
        self.claw_btn.setToolTip(_("tooltip.claw"))
        data_process_layout.addWidget(self.claw_btn, 2, 2)
        
        self.mirror_btn = QPushButton(_("ui.btn.mirror"))
        self.mirror_btn.clicked.connect(self.on_mirror)
        self.mirror_btn.setToolTip(_("tooltip.mirror"))
        data_process_layout.addWidget(self.mirror_btn, 3, 0)
        
        self.cornerize_btn = QPushButton(_("ui.btn.cornerize"))
        self.cornerize_btn.clicked.connect(self.on_cornerize)
        self.cornerize_btn.setToolTip(_("tooltip.cornerize"))
        data_process_layout.addWidget(self.cornerize_btn, 3, 1)
        
        self.hybrid_btn = QPushButton(_("ui.btn.hybrid"))
        self.hybrid_btn.clicked.connect(self.on_hybrid)
        self.hybrid_btn.setToolTip(_("tooltip.hybrid"))
        data_process_layout.addWidget(self.hybrid_btn, 3, 2)
        
        left_panel.addWidget(data_process_group)
        
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
        
        idx = right_tabs.addTab(analysis_tab_widget, _("ui.tabs.analysis_tools"))
        right_tabs.tabBar().setTabData(idx, ("key", "ui.tabs.analysis_tools", None))
        
        # 대량처리 탭 추가 (모듈 빌더 사용)
        # 커스텀 탭 위젯은 메인에서 생성해 빌더가 참조하도록 함
        self.data_tabs = CustomTabWidget()
        self.data_tabs.tab_close_requested.connect(self.on_data_tab_close)
        batch_tab_widget = build_batch_tab(self)
        
        # 대량처리 상태 변수 초기화
        self.selected_file_path = None
        self.file_load_success = False
        
        idx = right_tabs.addTab(batch_tab_widget, _("ui.tabs.batch"))
        right_tabs.tabBar().setTabData(idx, ("key", "ui.tabs.batch", None))
        
        # 공정트리 탭 추가
        process_tree_tab_widget = QWidget()
        process_tree_layout = QVBoxLayout(process_tree_tab_widget)
        
        # 입력 그룹
        tree_input_group = QGroupBox("공정 트리 분석")
        tree_input_layout = QVBoxLayout(tree_input_group)
        
        # 분석 버튼
        analyze_button = QPushButton("공정 트리 생성")
        analyze_button.clicked.connect(self.on_generate_process_tree)
        tree_input_layout.addWidget(analyze_button)
        
        process_tree_layout.addWidget(tree_input_group)
        
        # 트리 표시 영역
        tree_display_group = QGroupBox("공정 트리")
        tree_display_layout = QVBoxLayout(tree_display_group)
        
        # 스크롤 영역을 QGraphicsView로 변경
        self.tree_graphics_view = TreeGraphicsView()
        self.tree_graphics_view.setMinimumHeight(400)
        self.tree_graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.tree_graphics_view.setRenderHint(self.tree_graphics_view.renderHints())
        
        # QGraphicsScene for tree visualization  
        self.tree_scene = QGraphicsScene()
        self.tree_graphics_view.setScene(self.tree_scene)
        
        tree_display_layout.addWidget(self.tree_graphics_view)
        process_tree_layout.addWidget(tree_display_group)
        
        idx = right_tabs.addTab(process_tree_tab_widget, _("ui.tabs.process_tree"))
        right_tabs.tabBar().setTabData(idx, ("key", "ui.tabs.process_tree", None))
        
        # 공정트리 초기화 - 빈 메시지 표시
        self._clear_process_tree()
        
        # 테스트 편집기 탭 추가
        test_editor_tab_widget = QWidget()
        test_editor_tab_layout = QVBoxLayout(test_editor_tab_widget)
        
        # 자동 테스트 컨테이너 (맨 위)
        auto_test_group = QGroupBox(_("ui.groups.auto_test"))
        auto_test_layout = QVBoxLayout(auto_test_group)
        
        # 전체 테스트 실행 버튼
        run_all_tests_btn = QPushButton(_("ui.btn.run_all_tests"))
        run_all_tests_btn.clicked.connect(self.run_forward_tests)
        auto_test_layout.addWidget(run_all_tests_btn)
        
        # 역연산 테스트 실행 버튼
        run_reverse_tests_btn = QPushButton(_("ui.btn.run_reverse_tests"))
        run_reverse_tests_btn.clicked.connect(self.run_reverse_tests)
        auto_test_layout.addWidget(run_reverse_tests_btn)
        
        test_editor_tab_layout.addWidget(auto_test_group)
        
        # 테스트 케이스 편집기 그룹
        test_editor_group = QGroupBox(_("ui.groups.test_editor"))
        test_editor_layout = QVBoxLayout(test_editor_group)
        
        # 버튼 행
        test_editor_buttons = QHBoxLayout()
        
        self.save_tests_btn = QPushButton(_("ui.btn.save_tests"))
        self.save_tests_btn.setToolTip(_("ui.tooltip.save_tests"))
        test_editor_buttons.addWidget(self.save_tests_btn)
        
        self.reset_tests_btn = QPushButton(_("ui.btn.reset_tests"))
        self.reset_tests_btn.setToolTip(_("ui.tooltip.reset_tests"))
        test_editor_buttons.addWidget(self.reset_tests_btn)
        
        test_editor_layout.addLayout(test_editor_buttons)
        
        # 테스트 케이스 목록 (테이블 형태로 표시)
        self.test_cases_table = DragDropTableWidget()  # from gui.widgets
        self.test_cases_table.setColumnCount(5)
        self.test_cases_table.setHorizontalHeaderLabels([
            _("ui.table.header.category"), 
            _("ui.table.header.name"), 
            _("ui.table.header.operation"),
            _("ui.table.header.input"), 
            _("ui.table.header.output")
        ])
        # 컬럼 너비 설정 (가로 간격 줄임)
        self.test_cases_table.setColumnWidth(0, 80)   # 카테고리 (줄임)
        self.test_cases_table.setColumnWidth(1, 150)  # 테스트명
        self.test_cases_table.setColumnWidth(2, 100)  # 연산
        self.test_cases_table.setColumnWidth(3, 160)  # 입력 (늘림)
        self.test_cases_table.setColumnWidth(4, 160)  # 출력 (늘림)
        self.test_cases_table.horizontalHeader().setStretchLastSection(False)
        self.test_cases_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.test_cases_table.setAlternatingRowColors(True)
        self.test_cases_table.setSortingEnabled(True)
        test_editor_layout.addWidget(self.test_cases_table)
        
        # 테스트 케이스 편집 영역
        test_edit_group = QGroupBox(_("ui.test_editor.edit_title"))
        test_edit_layout = QVBoxLayout(test_edit_group)
        

        
        # 편집 컨트롤들
        edit_controls = QGridLayout()
        
        # 카테고리 선택
        edit_controls.addWidget(QLabel(_("ui.label.category")), 0, 0)
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setPlaceholderText(_("ui.placeholder.category"))
        edit_controls.addWidget(self.category_combo, 0, 1)
        
        # 테스트명
        edit_controls.addWidget(QLabel(_("ui.label.test_name")), 1, 0)
        self.test_name_edit = QLineEdit()
        self.test_name_edit.setPlaceholderText(_("ui.placeholder.test_name"))
        edit_controls.addWidget(self.test_name_edit, 1, 1)
        
        # 연산
        edit_controls.addWidget(QLabel(_("ui.label.operation")), 2, 0)
        self.operation_combo = QComboBox()
        self.operation_combo.addItems([
            "apply_physics", "destroy_half", "stack", "paint", "crystal_generator",
            "push_pin", "rotate", "swap", "classifier", "cutter", "simple_cutter",
            "quad_cutter", "mirror", "cornerize", "simplify", "detail", "corner1", "reverse"
        ])
        edit_controls.addWidget(self.operation_combo, 2, 1)
        

        
        # 입력 A (항상 표시)
        edit_controls.addWidget(QLabel(_("ui.label.input_a")), 3, 0)
        self.input_a_edit = QLineEdit()
        self.input_a_edit.setPlaceholderText(_("ui.placeholder.input_shape"))
        edit_controls.addWidget(self.input_a_edit, 3, 1)
        
        # 입력 B (일부 연산에만 필요)
        self.input_b_label = QLabel(_("ui.label.input_b"))
        self.input_b_edit = QLineEdit()
        self.input_b_edit.setPlaceholderText(_("ui.placeholder.input_shape"))
        edit_controls.addWidget(self.input_b_label, 4, 0)
        edit_controls.addWidget(self.input_b_edit, 4, 1)
        
        # 예상결과 A, B (이중 출력 연산용)
        self.expected_a_label = QLabel(_("ui.label.expected_a"))
        self.expected_a_edit = QLineEdit()
        self.expected_a_edit.setPlaceholderText(_("ui.placeholder.input_shape"))
        edit_controls.addWidget(self.expected_a_label, 5, 0)
        edit_controls.addWidget(self.expected_a_edit, 5, 1)
        
        self.expected_b_label = QLabel(_("ui.label.expected_b"))
        self.expected_b_edit = QLineEdit()
        self.expected_b_edit.setPlaceholderText(_("ui.placeholder.input_shape"))
        edit_controls.addWidget(self.expected_b_label, 6, 0)
        edit_controls.addWidget(self.expected_b_edit, 6, 1)
        
        # 매개변수
        edit_controls.addWidget(QLabel(_("ui.label.params")), 0, 2)
        self.params_edit = QLineEdit()
        self.params_edit.setPlaceholderText(_("ui.placeholder.params"))
        edit_controls.addWidget(self.params_edit, 0, 2)
        
        test_edit_layout.addLayout(edit_controls)
        
        # 편집 버튼들 제거 - 자동반영, 키보드/우클릭 삭제, 드래그앤드롭 순서 조절로 대체
        
        test_editor_layout.addWidget(test_edit_group)
        test_editor_tab_layout.addWidget(test_editor_group)
        
        # 테스트 편집기 탭 추가
        idx = right_tabs.addTab(test_editor_tab_widget, _("ui.tabs.test_editor"))
        right_tabs.tabBar().setTabData(idx, ("key", "ui.tabs.test_editor", None))
        
        # 연산 변경 시 필드 표시/숨김 처리는 connect_test_editor_signals에서 연결
        
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
        
        # 상세 로그 보기 체크박스
        self.log_checkbox = QCheckBox("상세 로그 보기")
        self.log_checkbox.setChecked(False)  # 기본값을 비활성화로 변경
        self.log_checkbox.stateChanged.connect(self.on_log_level_changed)
        log_header_layout.addWidget(self.log_checkbox)
        
        log_clear_button = QPushButton("지우기")
        log_clear_button.setMaximumWidth(60)
        log_clear_button.clicked.connect(self.on_clear_log)
        log_header_layout.addWidget(log_clear_button)
        
        log_vbox.addLayout(log_header_layout)
        log_vbox.addWidget(self.log_output, 1)
        main_content_hbox.addLayout(log_vbox, 1) # 로그 영역

        main_layout.addLayout(main_content_hbox, 1)

        self.log_verbose(f"시뮬레이터 준비 완료. 자동 테스트는 tests.json 파일을 사용합니다.")
        
        # 자동 적용 체크박스 상태 복원 (UI 초기화 완료 후)
        auto_apply_enabled = self.settings.value("auto_apply_enabled", False, type=bool)
        if hasattr(self, 'auto_apply_checkbox'):
            self.auto_apply_checkbox.setChecked(auto_apply_enabled)
        
        # 초기 입력 표시 (load_settings에서 처리되므로 여기서는 제거)
        # self.update_input_display()
        
        # 테스트 에디터 시그널 연결 및 초기화는 __init__ 끝에서 처리

    def closeEvent(self, event):
        """애플리케이션 종료 시 설정을 저장합니다."""
        self.log("애플리케이션 종료 중... 설정 및 백그라운드 스레드를 정리합니다.")
        
        # 현재 입력 필드의 값 저장
        self.settings.setValue("input_a", self.input_a.text())
        self.settings.setValue("input_b", self.input_b.text())
        
        # 마지막으로 열었던 데이터 경로 저장
        if hasattr(self, 'last_opened_data_path') and self.last_opened_data_path:
            self.settings.setValue("last_data_path", self.last_opened_data_path)
        
        # 자동 적용 체크박스 상태 저장
        if hasattr(self, 'auto_apply_checkbox'):
            self.settings.setValue("auto_apply_enabled", self.auto_apply_checkbox.isChecked())

        if self.origin_finder_thread and self.origin_finder_thread.isRunning():
            self.origin_finder_thread.cancel()
            self.origin_finder_thread.wait()

        event.accept()

    def log(self, message, verbose=False):
        """로그 메시지를 출력합니다.
        
        Args:
            message: 출력할 메시지
            verbose: 상세 로그 여부 (기본값: False)
        """
        # 모든 로그를 저장
        self.log_entries.append((message, verbose))
        
        # 현재 설정에 따라 표시 여부 결정
        if verbose and hasattr(self, 'log_checkbox') and not self.log_checkbox.isChecked():
            return  # 상세 로그가 비활성화되어 있으면 verbose 로그는 출력하지 않음
        
        if verbose:
            # 상세 로그는 진한 회색으로 표시 (HTML 이스케이프 처리)
            escaped_message = html.escape(message)
            self.log_output.append(f'<span style="color: #666666;">{escaped_message}</span>')
        else:
            # 일반 로그는 기본 색상
            self.log_output.append(message)
    
    def log_verbose(self, message):
        """상세 로그 메시지를 출력합니다."""
        self.log(message, verbose=True)
    
    def handle_origin_finder_log(self, message):
        """OriginFinderThread로부터 받은 로그 메시지를 처리합니다."""
        lines = message.split('\n')
        for line in lines:
            if line.startswith('[VERBOSE]'):
                # [VERBOSE] 태그를 제거하고 상세 로그로 처리
                clean_message = line[9:].strip()  # '[VERBOSE] ' 제거
                self.log_verbose(clean_message)
            else:
                self.log(line)

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
            container = QWidget()
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.addStretch(1)
            v_layout.addWidget(ShapeWidget(input_a_shape, compact=True, title="입력 A"))
            self.output_layout.addWidget(container)
        
        # 입력 B 표시 (비어있지 않은 경우만)
        if self.input_b.text().strip():
            input_b_shape = self._get_input_shape(self.input_b)
            if input_b_shape:
                container = QWidget()
                v_layout = QVBoxLayout(container)
                v_layout.setContentsMargins(0, 0, 0, 0)
                v_layout.addStretch(1)
                v_layout.addWidget(ShapeWidget(input_b_shape, compact=True, title="입력 B"))
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
            container = QWidget()
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.addStretch(1)
            v_layout.addWidget(ShapeWidget(input_a_shape, compact=True, title="입력 A"))
            self.output_layout.addWidget(container)
        
        # 입력 B 표시 (비어있지 않은 경우만)
        if self.input_b.text().strip():
            input_b_shape = self._get_input_shape(self.input_b)
            if input_b_shape:
                container = QWidget()
                v_layout = QVBoxLayout(container)
                v_layout.setContentsMargins(0, 0, 0, 0)
                v_layout.addStretch(1)
                v_layout.addWidget(ShapeWidget(input_b_shape, compact=True, title="입력 B"))
                self.output_layout.addWidget(container)

        # 결과 표시 및 추적
        self.current_outputs = []
        for title, shape in shapes:
            if shape:
                container = QWidget()
                v_layout = QVBoxLayout(container)
                v_layout.setContentsMargins(0, 0, 0, 0)
                v_layout.addStretch(1)
                v_layout.addWidget(ShapeWidget(shape, compact=True, title=title))
                self.output_layout.addWidget(container)
                # 출력 결과 추적 (입력이 아닌 결과만)
                if not title.startswith("입력"):
                    self.current_outputs.append((title, shape))
            else:
                container = QFrame()
                layout = QVBoxLayout(container)
                layout.setSpacing(2)
                layout.setContentsMargins(2, 2, 2, 2)
                
                title_label = QLabel(f"<b>{title}</b>")
                title_label.setContentsMargins(0, 0, 0, 2)
                layout.addWidget(title_label)
                layout.addWidget(QLabel("N/A"))
                self.output_layout.addWidget(container)
            if not result_text:
                log_msg += f"[{title}: {repr(shape) if shape else 'None'}] "
        
        # 적용 버튼 활성화/비활성화
        self.apply_button.setEnabled(len(self.current_outputs) > 0)
        
        self.log(log_msg)

    def on_destroy_half(self):
        if s := self._get_input_shape(self.input_a): 
            self.display_outputs([("파괴 후", s.destroy_half())])
            self.auto_apply_if_enabled()
    
    def on_crystal_gen(self):
        if s := self._get_input_shape(self.input_a): 
            self.display_outputs([("생성 후", s.crystal_generator(self.crystal_color.currentText()))])
            self.auto_apply_if_enabled()
    
    def on_apply_physics(self):
        if s := self._get_input_shape(self.input_a): 
            self.display_outputs([("안정화 후", s.apply_physics())])
            self.auto_apply_if_enabled()
    
    def on_stack(self):
        s_a = self._get_input_shape(self.input_a)
        s_b = self._get_input_shape(self.input_b)
        if s_a is not None and s_b is not None:
            self.display_outputs([("스택 후", Shape.stack(s_a, s_b))])
            self.auto_apply_if_enabled()
    
    def on_swap(self):
        s_a = self._get_input_shape(self.input_a)
        s_b = self._get_input_shape(self.input_b)
        if s_a is not None and s_b is not None:
            res_a, res_b = Shape.swap(s_a, s_b)
            self.display_outputs([("출력 A", res_a), ("출력 B", res_b)])
            self.auto_apply_if_enabled()
    
    def on_paint(self):
        if s := self._get_input_shape(self.input_a): 
            self.display_outputs([("페인트 후", s.paint(self.paint_color.currentText()))])
            self.auto_apply_if_enabled()
    
    def on_push_pin(self):
        if s := self._get_input_shape(self.input_a): 
            self.display_outputs([("푸셔 후", s.push_pin())])
            self.auto_apply_if_enabled()
    
    def on_rotate(self, clockwise: bool):
        if s := self._get_input_shape(self.input_a): 
            self.display_outputs([("회전 후", s.rotate(clockwise))])
            self.auto_apply_if_enabled()
    
    def on_rotate_180_building(self):
        """180도 회전 버튼 클릭 시 호출 (건물 작동용)"""
        if s := self._get_input_shape(self.input_a): 
            self.display_outputs([("180도 회전 후", s.rotate_180())])
            self.auto_apply_if_enabled()
    
    def on_simple_cutter(self):
        if s := self._get_input_shape(self.input_a):
            res_a, res_b = s.simple_cutter()
            self.display_outputs([("출력 A", res_a), ("출력 B", res_b)])
            self.auto_apply_if_enabled()
    
    def on_quad_cutter(self):
        """쿼드 커터 버튼 클릭 시 호출"""
        if s := self._get_input_shape(self.input_a):
            res_a, res_b, res_c, res_d = s.quad_cutter()
            self.display_outputs([("출력 A", res_a), ("출력 B", res_b), ("출력 C", res_c), ("출력 D", res_d)])
            self.auto_apply_if_enabled()
    
    def on_cutter(self):
        """커터 버튼 클릭 시 호출"""
        if s := self._get_input_shape(self.input_a):
            res_a, res_b = s.half_cutter()
            self.display_outputs([("출력 A", res_a), ("출력 B", res_b)])
            self.auto_apply_if_enabled()
    
    def on_classifier(self):
        if s := self._get_input_shape(self.input_a):
            try:
                classification_result, classification_reason = s.classifier()
                
                # 분류 결과와 사유를 함께 표시
                result_text = _("ui.classification.result", cls=_(classification_result), reason=classification_reason)
                
                # 분류 결과를 출력 영역에 텍스트로 표시 (로그는 display_outputs 내부에서 처리)
                self.display_outputs([], result_text)
                # 분류기는 텍스트 출력만 하므로 자동 적용하지 않음
                
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
            self.log_verbose(f"출력을 입력 A에 적용: {repr(output_shapes[0])}")
        elif len(output_shapes) == 2:
            # 이중 출력: 첫 번째는 입력 A, 두 번째는 입력 B에 적용
            self.input_a.setText(repr(output_shapes[0]))
            self.input_b.setText(repr(output_shapes[1]))
            self.log_verbose(f"출력을 입력에 적용: A={repr(output_shapes[0])}, B={repr(output_shapes[1])}")
        else:
            # 3개 이상의 출력: 처음 두 개만 사용
            self.input_a.setText(repr(output_shapes[0]))
            self.input_b.setText(repr(output_shapes[1]))
            self.log_verbose(f"출력 중 처음 2개를 입력에 적용: A={repr(output_shapes[0])}, B={repr(output_shapes[1])}")
    
    def auto_apply_if_enabled(self):
        """자동 적용 체크박스가 체크되어 있으면 자동으로 출력을 입력에 적용합니다."""
        if hasattr(self, 'auto_apply_checkbox') and self.auto_apply_checkbox.isChecked():
            self.on_apply_outputs()
    
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
        
        # claw_tracer의 로깅 콜백 설정
        from claw_tracer import set_log_callback
        if log_enabled:
            set_log_callback(self.log)
        else:
            set_log_callback(None)
            
        self.origin_finder_thread = OriginFinderThread(target_shape, ReverseTracer.MAX_SEARCH_DEPTH, max_physics_height, log_enabled)
        self.origin_finder_thread.progress.connect(self.update_progress_dialog)
        self.origin_finder_thread.finished.connect(self.on_find_origin_finished)
        self.origin_finder_thread.log_message.connect(self.handle_origin_finder_log)
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
        
        self.log_verbose(f"선택된 후보 로드: [{op_name}]")
        
        if isinstance(origin_shape, tuple):
            shape_a, shape_b = origin_shape
            self.input_a.setText(repr(shape_a))
            self.input_b.setText(repr(shape_b))
            self.log_verbose(f"  -> 입력 A: {repr(shape_a)}")
            self.log_verbose(f"  -> 입력 B: {repr(shape_b)}")
            
            self.display_outputs([("선택된 후보 A", shape_a), ("선택된 후보 B", shape_b)])

        else:
            self.input_a.setText(repr(origin_shape))
            self.input_b.clear()
            self.log_verbose(f"  -> 입력 A: {repr(origin_shape)}")

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
            self.log_verbose(f"최대 탐색 깊이가 {new_depth}로 설정되었습니다.")
        except ValueError:
            self.log("🔥 오류: 최대 탐색 깊이는 숫자로 입력해야 합니다. 1로 설정합니다.")
            ReverseTracer.MAX_SEARCH_DEPTH = 1
            self.max_depth_input.setText("1")

    def on_max_layers_changed(self):
        data = self.max_layers_combo.currentData()
        try:
            new_max = int(data)
        except (TypeError, ValueError):
            return
        Shape.MAX_LAYERS = new_max
        self.log_verbose(_("log.max_layers.set", n=new_max)) 

    
    def run_forward_tests(self):
        self.clear_log(); self.log("=== 전체 정방향 테스트 시작 (tests.json) ===")
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
                            passed_count += 1; self.log_verbose(f"✅ 통과: {name}")
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
                            expected = test.get('expected_a', "")
                            
                            # 예상 문자열이 결과 문자열에 포함되어 있는지 검사
                            if expected in result_string:
                                passed_count += 1
                                self.log_verbose(f"✅ 통과: {name}")
                            else:
                                self.log(f"❌ 실패: {name}\n  - 입력A: {input_a_str}\n  - 예상: {expected}\n  - 실제: {result_string} (사유: {reason})")
                            continue
                        else: raise ValueError(f"연산 '{operation}'은 입력 A만으로는 수행할 수 없습니다.")
                    
                    actual_code = repr(actual_shape)
                    expected_shape = Shape.from_string(test.get('expected_a', ""))
                    expected_code = repr(expected_shape)

                    if actual_code == expected_code:
                        passed_count += 1; self.log_verbose(f"✅ 통과: {name}")
                    else: self.log(f"❌ 실패: {name}\n  - 입력A: {input_a_str}\n  - 예상: {expected_code}\n  - 실제: {actual_code}")
                except Exception as e:
                    self.log(f"🔥 오류: {name} - {e.__class__.__name__}: {e}")
                    import traceback; self.log(traceback.format_exc())
        summary = f"정방향 테스트 종료: {total_count}개 중 {passed_count}개 통과 ({passed_count/total_count if total_count > 0 else 0:.1%})"
        self.log(f"\n=== {summary} ===")

    def run_reverse_tests(self):
        self.clear_log()
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
                self.log_verbose(f"✅ 통과: {test_name}")
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
        self.log(f"\n=== {summary} ===\n")

        # 테스트 편집기 시그널 연결
        self.connect_test_editor_signals()

    # =================== 키보드 단축키 설정 ===================
    
    def setup_shortcuts(self):
        """키보드 단축키 설정"""
        # 통합 Undo/Redo 단축키 (현재 활성화된 탭에 따라 적절한 기능 호출)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.on_undo)
        
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.on_redo)
        
        # 추가 Redo 단축키 (Ctrl+Shift+Z)
        self.shortcut_redo2 = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.shortcut_redo2.activated.connect(self.on_redo)
    
    def on_language_changed(self):
        lang_code = self.lang_combo.currentData()
        from i18n import set_language
        set_language(lang_code)
        # 저장
        try:
            self.settings.setValue("lang", lang_code)
        except Exception:
            pass
        # 완전 재시작 (요청사항)
        try:
            QProcess.startDetached(sys.executable, sys.argv)
        except Exception:
            pass
        QApplication.quit()

    def _retranslate_ui(self):
        # 윈도우 타이틀
        self.setWindowTitle(_("app.title"))

        # 위젯 전체 일괄 재번역 (별칭 기반)
        for gb in self.findChildren(QGroupBox):
            title = gb.title()
            if title:
                gb.setTitle(_(title))
        for lbl in self.findChildren(QLabel):
            text = lbl.text()
            if text:
                lbl.setText(_(text))
        for btn in self.findChildren(QPushButton):
            text = btn.text()
            if text:
                btn.setText(_(text))
        for chk in self.findChildren(QCheckBox):
            text = chk.text()
            if text:
                chk.setText(_(text))
        for tabs in self.findChildren(QTabWidget):
            for i in range(tabs.count()):
                data = tabs.tabBar().tabData(i)
                if isinstance(data, tuple):
                    if len(data) >= 2 and data[0] == "key":
                        key = data[1]
                        kwargs = data[2] if len(data) > 2 and isinstance(data[2], dict) else {}
                        tabs.setTabText(i, _(key, **kwargs))
                    elif len(data) == 2 and data[0] == "raw":
                        raw = data[1]
                        tabs.setTabText(i, _(raw))

        # 특정 위젯들은 옵션 리스트 재구성 필요
        # 재번역 시 시그널 차단 후 텍스트/데이터 재설정
        self.max_layers_combo.blockSignals(True)
        current_data = self.max_layers_combo.currentData()
        self.max_layers_combo.clear()
        self.max_layers_combo.addItem(_("ui.max_layers.option.5"), 5)
        self.max_layers_combo.addItem(_("ui.max_layers.option.4"), 4)
        # 기존 선택 복원
        idx = 0 if current_data == 5 else 1
        self.max_layers_combo.setCurrentIndex(idx)
        self.max_layers_combo.blockSignals(False)

        # 언어 드롭다운 항목(표시 텍스트) 갱신
        if hasattr(self, 'lang_combo'):
            current_index = self.lang_combo.currentIndex()
            # 텍스트만 교체, userData 유지
            self.lang_combo.setItemText(0, "한국어")
            self.lang_combo.setItemText(1, "English")
            self.lang_label.setText(_("ui.lang.label"))
            self.lang_combo.setCurrentIndex(current_index)

        # 버튼/툴팁 등 세부 항목
        self.stack_btn.setText(_("스태커 (A가 아래)"))
        self.swap_btn.setText(_("스와퍼 (A, B)"))
        self.apply_button.setText(_("ui.apply_outputs"))
        self.apply_button.setToolTip(_("tooltip.apply_outputs") if _("tooltip.apply_outputs") != "tooltip.apply_outputs" else self.apply_button.toolTip())
        
        # 데이터 처리 버튼들
        self.simplify_btn.setText(_("ui.btn.simplify"))
        self.simplify_btn.setToolTip(_("tooltip.simplify"))
        self.detail_btn.setText(_("ui.btn.detail"))
        self.detail_btn.setToolTip(_("tooltip.detail"))
        self.corner_3q_btn.setText(_("ui.btn.corner1"))
        self.corner_3q_btn.setToolTip(_("tooltip.corner1"))
        self.reverse_btn.setText(_("ui.btn.reverse"))
        self.reverse_btn.setToolTip(_("tooltip.reverse"))
        self.mirror_btn.setText(_("ui.btn.mirror"))
        self.mirror_btn.setToolTip(_("tooltip.mirror"))
        self.cornerize_btn.setText(_("ui.btn.cornerize"))
        self.cornerize_btn.setToolTip(_("tooltip.cornerize"))

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
    
    def handle_quadrant_drop(self, src_input_name, src_layer, src_quad,
                             tgt_input_name, tgt_layer, tgt_quad):
        """도형 시각화 위젯 간의 드래그 앤 드롭을 처리합니다."""
        self.log_verbose(f"드롭 이벤트: {src_input_name}[{src_layer}][{src_quad}] -> {tgt_input_name}[{tgt_layer}][{tgt_quad}]")

        src_input_widget = self.input_a if src_input_name == "A" else self.input_b
        tgt_input_widget = self.input_a if tgt_input_name == "A" else self.input_b

        try:
            src_shape = Shape.from_string(src_input_widget.text())
            tgt_shape = Shape.from_string(tgt_input_widget.text()) if src_input_widget != tgt_input_widget else src_shape
        except Exception as e:
            self.log(f"🔥 드롭 오류: 도형 코드를 파싱할 수 없습니다. {e}")
            return
            
        # 레이어 확장
        max_layers = max(len(src_shape.layers), len(tgt_shape.layers), src_layer + 1, tgt_layer + 1)
        src_shape.pad_layers(max_layers)
        tgt_shape.pad_layers(max_layers)

        # Quadrant 교환
        src_quadrant = src_shape.layers[src_layer].quadrants[src_quad]
        tgt_quadrant = tgt_shape.layers[tgt_layer].quadrants[tgt_quad]
        
        src_shape.layers[src_layer].quadrants[src_quad] = tgt_quadrant
        tgt_shape.layers[tgt_layer].quadrants[tgt_quad] = src_quadrant

        # shape 문자열 업데이트
        self.history_update_in_progress = True # 히스토리 중복 추가 방지
        src_input_widget.setText(repr(src_shape))
        if src_input_widget != tgt_input_widget:
            tgt_input_widget.setText(repr(tgt_shape))
        self.history_update_in_progress = False

        # 변경 후 히스토리 추가 및 UI 업데이트
        self.add_to_history()
        self.update_input_display()

    def handle_row_drop(self, src_input_name, src_layer_idx, tgt_input_name, tgt_layer_idx):
        self.log_verbose(f"행 드롭: {src_input_name}[{src_layer_idx}] -> {tgt_input_name}[{tgt_layer_idx}]")
        
        src_input_widget = self.input_a if src_input_name == "A" else self.input_b
        tgt_input_widget = self.input_a if tgt_input_name == "A" else self.input_b

        try:
            src_shape = Shape.from_string(src_input_widget.text())
            tgt_shape = Shape.from_string(tgt_input_widget.text()) if src_input_widget != tgt_input_widget else src_shape
        except Exception as e:
            self.log(f"🔥 드롭 오류: 도형 코드를 파싱할 수 없습니다. {e}")
            return

        max_layers = max(len(src_shape.layers), len(tgt_shape.layers), src_layer_idx + 1, tgt_layer_idx + 1)
        src_shape.pad_layers(max_layers)
        tgt_shape.pad_layers(max_layers)

        # 행(레이어) 교환
        moved_layer = src_shape.layers.pop(src_layer_idx)
        tgt_shape.layers.insert(tgt_layer_idx, moved_layer)
        
        # shape 문자열 업데이트
        self.history_update_in_progress = True
        src_input_widget.setText(repr(src_shape))
        if src_input_widget != tgt_input_widget:
            tgt_input_widget.setText(repr(tgt_shape))
        self.history_update_in_progress = False

        self.add_to_history()
        self.update_input_display()

    def handle_column_drop(self, src_input_name, src_quad_idx, tgt_input_name, tgt_quad_idx):
        self.log_verbose(f"열 드롭: {src_input_name}[{src_quad_idx}] -> {tgt_input_name}[{tgt_quad_idx}]")
        
        # 열 교환은 동일한 입력 창 내에서만 의미가 있음
        if src_input_name != tgt_input_name:
            self.log("🔥 열 교환은 동일한 입력 창 내에서만 가능합니다.")
            return

        input_widget = self.input_a if src_input_name == "A" else self.input_b
        
        try:
            shape = Shape.from_string(input_widget.text())
        except Exception as e:
            self.log(f"🔥 드롭 오류: 도형 코드를 파싱할 수 없습니다. {e}")
            return
            
        # 모든 레이어에 대해 열(사분면) 교환
        for layer in shape.layers:
            quad_to_move = layer.quadrants[src_quad_idx]
            layer.quadrants[src_quad_idx] = layer.quadrants[tgt_quad_idx]
            layer.quadrants[tgt_quad_idx] = quad_to_move
            
        self.history_update_in_progress = True
        input_widget.setText(repr(shape))
        self.history_update_in_progress = False
        
        self.add_to_history()
        self.update_input_display()
    
    def handle_quadrant_change(self, input_name, layer_index, quad_index, new_quadrant):
        """셀 내용 변경을 처리합니다."""
        self.log_verbose(f"셀 변경: {input_name}[{layer_index}][{quad_index}] -> {new_quadrant}")
        
        input_widget = self.input_a if input_name == "A" else self.input_b
        
        try:
            shape = Shape.from_string(input_widget.text())
        except Exception as e:
            self.log(f"🔥 셀 변경 오류: 도형 코드를 파싱할 수 없습니다. {e}")
            return
            
        # 레이어 확장
        max_layers = max(len(shape.layers), layer_index + 1)
        shape.pad_layers(max_layers)
        
        # 셀 내용 변경
        shape.layers[layer_index].quadrants[quad_index] = new_quadrant
        
        # shape 문자열 업데이트
        self.history_update_in_progress = True
        input_widget.setText(repr(shape))
        self.history_update_in_progress = False
        
        # 변경 후 히스토리 추가 및 UI 업데이트
        self.add_to_history()
        self.update_input_display()
    
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
        """Undo 실행 - 현재 활성화된 탭에 따라 적절한 기능 호출"""
        bar = self.main_tabs.tabBar()
        data = bar.tabData(self.main_tabs.currentIndex())
        is_batch = isinstance(data, tuple) and len(data) >= 2 and data[0] == "key" and data[1] == "ui.tabs.batch"
        if not is_batch:
            # 폴백 텍스트 비교
            name = self.main_tabs.tabText(self.main_tabs.currentIndex())
            is_batch = name in ("대량처리", "Batch")
        
        if is_batch:
            # 대량처리 탭이 활성화된 경우, 현재 데이터 탭의 Undo 실행
            current_data_tab = self.get_current_data_tab()
            if current_data_tab:
                self.log_verbose("대량처리 탭에서 Ctrl+Z 실행")
                current_data_tab.on_data_undo()
            else:
                self.log_verbose("활성화된 대량처리 데이터 탭이 없습니다.")
        else:
            # 분석도구 탭이 활성화된 경우, 입력 필드 Undo 실행
            self.log_verbose("분석도구 입력에서 Ctrl+Z 실행")
            entry = self.input_history.undo()
            if entry is not None:
                input_a_text, input_b_text = entry
                self.history_update_in_progress = True
                self.input_a.setText(input_a_text)
                self.input_b.setText(input_b_text)
                self.history_update_in_progress = False
                self.update_history_buttons()
            else:
                self.log_verbose("되돌릴 입력 히스토리가 없습니다.")
    
    def on_redo(self):
        """Redo 실행 - 현재 활성화된 탭에 따라 적절한 기능 호출"""
        bar = self.main_tabs.tabBar()
        data = bar.tabData(self.main_tabs.currentIndex())
        is_batch = isinstance(data, tuple) and len(data) >= 2 and data[0] == "key" and data[1] == "ui.tabs.batch"
        if not is_batch:
            # 폴백 텍스트 비교
            name = self.main_tabs.tabText(self.main_tabs.currentIndex())
            is_batch = name in ("대량처리", "Batch")
        
        if is_batch:
            # 대량처리 탭이 활성화된 경우, 현재 데이터 탭의 Redo 실행
            current_data_tab = self.get_current_data_tab()
            if current_data_tab:
                self.log_verbose("대량처리 탭에서 Ctrl+Y 실행")
                current_data_tab.on_data_redo()
            else:
                self.log_verbose("활성화된 대량처리 데이터 탭이 없습니다.")
        else:
            # 분석도구 탭이 활성화된 경우, 입력 필드 Redo 실행
            self.log_verbose("분석도구 입력에서 Ctrl+Y 실행")
            entry = self.input_history.redo()
            if entry is not None:
                input_a_text, input_b_text = entry
                self.history_update_in_progress = True
                self.input_a.setText(input_a_text)
                self.input_b.setText(input_b_text)
                self.history_update_in_progress = False
                self.update_history_buttons()
            else:
                self.log_verbose("다시실행할 입력 히스토리가 없습니다.")

    # =================== 대량처리 관련 메서드들 ===================
    
    def add_data_tab(self, tab_name: str, data: list):
        """새로운 데이터 탭 추가"""
        tab_widget = _Legacy_DataTabWidget(tab_name, data)
        # 탭에 키/별칭을 데이터로 보관하여 재번역 시 정확히 복원
        self.data_tabs.addTab(tab_widget, _(tab_name))
        try:
            # tab_name이 키인지 별칭인지 알 수 없으므로 원문도 함께 저장
            idx = self.data_tabs.indexOf(tab_widget)
            self.data_tabs.tabBar().setTabData(idx, ("raw", tab_name))
        except Exception:
            pass
        self.data_tabs.setCurrentWidget(tab_widget)
        return tab_widget
    
    def get_current_data_tab(self):
        """현재 활성 데이터 탭 반환"""
        return self.data_tabs.currentWidget()
    
    def on_data_tab_close(self, index):
        """데이터 탭 닫기"""
        if self.data_tabs.count() <= 1:
            QMessageBox.warning(self, _("ui.msg.title.warning"), _("ui.msg.last_tab"))
            return
        
        tab_name = self.data_tabs.tabText(index)
        self.data_tabs.removeTab(index)
        self.log(f"데이터 탭 '{tab_name}' 닫힘")
    
    def on_add_new_data_tab(self):
        """새로운 데이터 탭 추가"""
        new_tab_name = _("ui.data.new_tab_name", n=self.data_tabs.count() + 1)
        self.add_data_tab(new_tab_name, [])
        self.log(f"새 데이터 탭 '{new_tab_name}' 추가")
    
    def on_batch_operation(self, operation_name: str):
        """현재 탭의 모든 데이터에 대해 건물 작동 연산 수행"""
        current_tab = self.get_current_data_tab()
        if not current_tab or not current_tab.data:
            QMessageBox.information(self, _("ui.msg.title.info"), _("ui.msg.no_data"))
            return
        
        # 처리할 데이터 결정: 선택된 항목이 있으면 그것만, 없으면 현재 필터(검색)로 보이는 행만
        selected_rows = current_tab.data_table.selectionModel().selectedRows()
        if selected_rows:
            indices_to_process = [idx.row() for idx in sorted(selected_rows, key=lambda x: x.row())]
            self.log_verbose(f"선택된 {len(indices_to_process)}개 항목에 대해 {operation_name} 연산 수행")
        else:
            visible_indices = [row for row in range(current_tab.data_table.rowCount()) if not current_tab.data_table.isRowHidden(row)]
            if visible_indices:
                indices_to_process = visible_indices
                self.log_verbose(f"검색 결과의 보이는 {len(indices_to_process)}개 항목에 대해 {operation_name} 연산 수행")
            else:
                indices_to_process = range(len(current_tab.data))
                self.log_verbose(f"'{current_tab.tab_name}' 탭의 모든 {len(current_tab.data)}개 항목에 대해 {operation_name} 연산 수행")
        
        # 5천 개 초과 시 비동기 처리 + 진행 상황 표시/취소 지원
        total_count = len(indices_to_process)
        if total_count > 5000:
            # 진행 대화상자
            progress = QProgressDialog(self)
            progress.setWindowTitle(_("ui.msg.title.info"))
            progress.setLabelText(_("ui.progress.batch_running"))
            progress.setCancelButtonText(_("ui.progress.cancel"))
            progress.setRange(0, total_count)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.show()

            # 롤백을 위한 스냅샷 저장
            original_data_snapshot = list(current_tab.data)

            # 처리 함수 어댑터
            def process_adapter(code: str, idx_in_data: int):
                shape = Shape.from_string(code)
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
                    result_shape = shape.paint(self.paint_color.currentText())
                elif operation_name == "crystal_generator":
                    result_shape = shape.crystal_generator(self.crystal_color.currentText())
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
                    input_b_text = self.input_b.text().strip()
                    if not input_b_text:
                        return _("error.input.b.empty"), []
                    shape_b = Shape.from_string(input_b_text)
                    result_shape = Shape.stack(shape, shape_b)
                elif operation_name == "swap":
                    input_b_text = self.input_b.text().strip()
                    if not input_b_text:
                        return _("error.input.b.empty"), []
                    shape_b = Shape.from_string(input_b_text)
                    result_a, result_b = Shape.swap(shape, shape_b)
                    append_values.append(repr(result_b))
                    return repr(result_a), append_values
                return (repr(result_shape) if result_shape is not None else _("ui.table.error", error="no result")), append_values

            # 스레드 시작
            worker = BatchWorkerThread(indices_to_process, current_tab.data, process_adapter)
            self._batch_worker = worker
            worker.progress.connect(lambda cur, tot: progress.setValue(cur))
            def on_finished(result_map, append_list, error_count, canceled):
                progress.close()
                if canceled:
                    # 취소 시 되돌리기
                    current_tab.data = original_data_snapshot
                    current_tab.update_table()
                    current_tab.add_to_data_history(_("ui.history.revert_due_to_cancel"))
                    self.log(_("ui.progress.canceled"))
                else:
                    # 결과 적용
                    for i, new_value in result_map.items():
                        current_tab.data[i] = new_value
                    for extra in append_list:
                        current_tab.data.append(extra)
                    current_tab.update_table()
                    current_tab.add_to_data_history(f"{operation_name} 완료")
                    self.log(_("ui.progress.summary", n=len(result_map), e=error_count))
                    if error_count > 0:
                        QMessageBox.warning(self, _("ui.msg.title.warning"), _("ui.msg.batch_errors", n=error_count))
                self._batch_worker = None
            worker.finished_with_results.connect(on_finished)
            progress.canceled.connect(lambda: worker.cancel())
            worker.start()
            return

        # 동기 처리 (5천개 이하)
        # 작업 전 현재 상태를 히스토리에 저장
        current_tab.add_to_data_history(f"작업 전 ({operation_name})")

        result_data_map = {}
        error_count = 0
        for i in indices_to_process:
            shape_code = current_tab.data[i]
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
                elif operation_name == "rotate_180":
                    result_shape = shape.rotate_180()
                elif operation_name == "mirror":
                    result_shape = shape.mirror()
                elif operation_name == "paint":
                    result_shape = shape.paint(self.paint_color.currentText())
                elif operation_name == "crystal_generator":
                    result_shape = shape.crystal_generator(self.crystal_color.currentText())
                elif operation_name == "classifier":
                    cls_res, cls_reason = shape.classifier()
                    result_data_map[i] = f"{cls_res} ({cls_reason})"
                    continue
                elif operation_name == "simple_cutter":
                    res_a, res_b = shape.simple_cutter()
                    result_data_map[i] = repr(res_a)
                    if i + 1 < len(current_tab.data):
                        current_tab.data.insert(i + 1, repr(res_b))
                    else:
                        current_tab.data.append(repr(res_b))
                    continue
                elif operation_name == "quad_cutter":
                    res_a, res_b, res_c, res_d = shape.quad_cutter()
                    result_data_map[i] = repr(res_a)
                    insert_positions = []
                    for j, result in enumerate([res_b, res_c, res_d], 1):
                        if i + j < len(current_tab.data):
                            insert_positions.append((i + j, repr(result)))
                        else:
                            current_tab.data.append(repr(result))
                    for pos, result in reversed(insert_positions):
                        current_tab.data.insert(pos, result)
                    continue
                elif operation_name == "half_cutter":
                    res_a, res_b = shape.half_cutter()
                    result_data_map[i] = repr(res_a)
                    if i + 1 < len(current_tab.data):
                        current_tab.data.insert(i + 1, repr(res_b))
                    else:
                        current_tab.data.append(repr(res_b))
                    continue
                elif operation_name == "stack":
                    input_b_text = self.input_b.text().strip()
                    if not input_b_text:
                        result_data_map[i] = _("error.input.b.empty")
                        error_count += 1
                        continue
                    try:
                        shape_b = Shape.from_string(input_b_text)
                        result_shape = Shape.stack(shape, shape_b)
                    except Exception as e:
                        result_data_map[i] = _("error.input.b.parse", error=str(e))
                        error_count += 1
                        continue
                elif operation_name == "swap":
                    input_b_text = self.input_b.text().strip()
                    if not input_b_text:
                        result_data_map[i] = _("error.input.b.empty")
                        error_count += 1
                        continue
                    try:
                        shape_b = Shape.from_string(input_b_text)
                        result_a, result_b = Shape.swap(shape, shape_b)
                        result_data_map[i] = repr(result_a)
                        if i + 1 < len(current_tab.data):
                            current_tab.data.insert(i + 1, repr(result_b))
                        else:
                            current_tab.data.append(repr(result_b))
                        continue
                    except Exception as e:
                        result_data_map[i] = _("error.input.b.parse", error=str(e))
                        error_count += 1
                        continue
                if result_shape is not None:
                    result_data_map[i] = repr(result_shape)
                else:
                    result_data_map[i] = "오류: 결과 없음"
                    error_count += 1
            except Exception as e:
                result_data_map[i] = f"오류: {str(e)}"
                error_count += 1

        for i, new_value in result_data_map.items():
            current_tab.data[i] = new_value
        current_tab.update_table()
        current_tab.add_to_data_history(f"{operation_name} 완료")
        self.log(f"대량처리 완료: {len(result_data_map)}개 항목 처리, {error_count}개 오류")
        if error_count > 0:
            QMessageBox.warning(self, _("ui.msg.title.warning"), _("ui.msg.batch_errors", n=error_count))
    
    def process_data_operation(self, operation_name: str, process_func):
        """데이터 처리 작업의 공통 로직"""
        # 대량처리 탭이 활성화되어 있으면 대량처리만 실행 (입력 A/B 무시)
        bar = self.main_tabs.tabBar()
        data = bar.tabData(self.main_tabs.currentIndex())
        is_batch = isinstance(data, tuple) and len(data) >= 2 and data[0] == "key" and data[1] == "ui.tabs.batch"
        if not is_batch:
            # 폴백 텍스트 비교
            name = self.main_tabs.tabText(self.main_tabs.currentIndex())
            is_batch = name in ("대량처리", "Batch")
        if is_batch:
            current_tab = self.get_current_data_tab()
            if not current_tab or not current_tab.data:
                QMessageBox.information(self, _("ui.msg.title.info"), _("ui.msg.no_data"))
                return

            # 처리할 데이터 결정: 선택된 항목이 있으면 그것만, 없으면 현재 필터(검색)로 보이는 행만
            selected_rows = current_tab.data_table.selectionModel().selectedRows()
            if selected_rows:
                indices_to_process = [idx.row() for idx in selected_rows]
                self.log_verbose(f"선택된 {len(indices_to_process)}개 항목에 대해 {operation_name} 연산 수행")
            else:
                visible_indices = [row for row in range(current_tab.data_table.rowCount()) if not current_tab.data_table.isRowHidden(row)]
                if visible_indices:
                    indices_to_process = visible_indices
                    self.log_verbose(f"검색 결과의 보이는 {len(indices_to_process)}개 항목에 대해 {operation_name} 연산 수행")
                else:
                    indices_to_process = range(len(current_tab.data))
                    self.log_verbose(f"'{current_tab.tab_name}' 탭의 모든 {len(current_tab.data)}개 항목에 대해 {operation_name} 연산 수행")
            
            total_count = len(indices_to_process)
            if total_count > 5000:
                # 비동기 처리 + 프로그레스/취소
                progress = QProgressDialog(self)
                progress.setWindowTitle(_("ui.msg.title.info"))
                progress.setLabelText(_("ui.progress.batch_running"))
                progress.setCancelButtonText(_("ui.progress.cancel"))
                progress.setRange(0, total_count)
                progress.setAutoClose(False)
                progress.setAutoReset(False)
                progress.show()

                # 롤백 스냅샷
                original_data_snapshot = list(current_tab.data)

                def process_adapter(code: str, _idx: int):
                    res = process_func(code)
                    if isinstance(res, list):
                        mapped = res[0] if len(res) > 0 else ""
                        append_values = res[1:]
                        return mapped, append_values
                    return res, []

                worker = BatchWorkerThread(indices_to_process, current_tab.data, process_adapter)
                self._batch_worker = worker
                worker.progress.connect(lambda cur, tot: progress.setValue(cur))

                def on_finished(result_map, append_list, error_count, canceled):
                    progress.close()
                    if canceled:
                        # 되돌리기
                        current_tab.data = original_data_snapshot
                        current_tab.update_table()
                        current_tab.add_to_data_history(_("ui.history.revert_due_to_cancel"))
                        self.log(_("ui.progress.canceled"))
                    else:
                        for i, new_value in result_map.items():
                            current_tab.data[i] = new_value
                        for extra in append_list:
                            current_tab.data.append(extra)
                        current_tab.update_table()
                        if current_tab.visualization_checkbox.isChecked():
                            QTimer.singleShot(100, current_tab._update_visible_shapes)
                        current_tab.add_to_data_history(f"{operation_name} 완료")
                        self.log(_("ui.progress.summary", n=len(result_map), e=error_count))
                        if error_count > 0:
                            QMessageBox.warning(self, _("ui.msg.title.warning"), _("ui.msg.batch_errors", n=error_count))
                    self._batch_worker = None

                worker.finished_with_results.connect(on_finished)
                progress.canceled.connect(lambda: worker.cancel())
                worker.start()
                return
            else:
                # 동기 처리 (5천 이하)
                current_tab.add_to_data_history(f"작업 전 ({operation_name})")
                result_data_map = {}
                error_count = 0
                for i in indices_to_process:
                    shape_code = current_tab.data[i]
                    try:
                        result = process_func(shape_code)
                        if isinstance(result, list):
                            for j, item in enumerate(result):
                                if j == 0:
                                    result_data_map[i] = item
                                else:
                                    new_index = len(current_tab.data)
                                    current_tab.data.append(item)
                                    result_data_map[new_index] = item
                        else:
                            result_data_map[i] = result
                    except Exception as e:
                        result_data_map[i] = f"오류: {str(e)}"
                        error_count += 1
                for i, new_value in result_data_map.items():
                    current_tab.data[i] = new_value
                current_tab.update_table()
                if current_tab.visualization_checkbox.isChecked():
                    QTimer.singleShot(100, current_tab._update_visible_shapes)
                current_tab.add_to_data_history(f"{operation_name} 완료")
                if error_count > 0:
                    self.log(f"{operation_name} 완료: {len(result_data_map)}개 결과 생성, {error_count}개 오류")
                else:
                    self.log(f"{operation_name} 완료: {len(result_data_map)}개 결과 생성")
        else:
            # 분석 도구 탭에서는 입력 A/B 처리
            input_a_str = self.input_a.text().strip()
            input_b_str = self.input_b.text().strip()
            
            if not input_a_str and not input_b_str:
                self.log("처리할 입력이 없습니다.")
                return

            if input_a_str:
                try:
                    result_a = process_func(input_a_str)
                    # 리스트 결과인 경우 (하이브리드 등)
                    if isinstance(result_a, list):
                        if len(result_a) >= 1:
                            self.input_a.setText(result_a[0])
                            if len(result_a) >= 2:
                                self.input_b.setText(result_a[1])
                        self.log_verbose(f"입력 A에 {operation_name} 적용: A={result_a[0] if result_a else ''}, B={result_a[1] if len(result_a) > 1 else ''}")
                    else:
                        self.input_a.setText(result_a)
                        self.log_verbose(f"입력 A에 {operation_name} 적용: {result_a}")
                except Exception as e:
                    self.log(f"입력 A {operation_name} 오류: {str(e)}")
            
            if input_b_str:
                try:
                    result_b = process_func(input_b_str)
                    # 리스트 결과인 경우 (하이브리드 등)
                    if isinstance(result_b, list):
                        if len(result_b) >= 1:
                            self.input_a.setText(result_b[0])
                            if len(result_b) >= 2:
                                self.input_b.setText(result_b[1])
                        self.log_verbose(f"입력 B에 {operation_name} 적용: A={result_b[0] if result_b else ''}, B={result_b[1] if len(result_b) > 1 else ''}")
                    else:
                        self.input_b.setText(result_b)
                        self.log_verbose(f"입력 B에 {operation_name} 적용: {result_b}")
                except Exception as e:
                    self.log(f"입력 B {operation_name} 오류: {str(e)}")
            
            self.log(f"{operation_name} 완료 (입력만 처리)")
    
    def on_simplify(self):
        """단순화 버튼 클릭 시 호출 - CuCuCuP- 같은 구조를 SSSP로 단순화"""
        def simplify_shape(shape_code: str) -> str:
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
        
        self.process_data_operation("단순화", simplify_shape)
    
    def on_detail(self):
        """구체화 버튼 클릭 시 호출 - SSSP를 CuCuCuP-로 구체화 (from_string 논리와 동일)"""
        def detail_shape(shape_code: str) -> str:
            try:
                # Shape 객체로 변환 후 다시 문자열로 변환 (정규화)
                shape = Shape.from_string(shape_code)
                return repr(shape)
            except Exception as e:
                raise Exception(f"구체화 실패: {str(e)}")
        
        self.process_data_operation("구체화", detail_shape)
    
    def on_corner_1q(self):
        """1사분면 코너 버튼 클릭 시 호출 - 1사분면만 가져와서 한줄로 단순화"""
        def corner_1q_shape(shape_code: str) -> str:
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
                
                return "".join(corner_chars)
            except Exception as e:
                raise Exception(f"1사분면 코너 추출 실패: {str(e)}")
        
        self.process_data_operation("1사분면 코너", corner_1q_shape)
    
    def on_remove_impossible(self):
        """불가능 제거 버튼 클릭 시 호출 - 불가능한 패턴이거나 오류 발생시 제거"""
        from shape_analyzer import analyze_shape, ShapeType
        
        # 대량처리 탭이 활성화되어 있으면 대량처리만 실행 (입력 A/B 무시)
        bar = self.main_tabs.tabBar()
        data = bar.tabData(self.main_tabs.currentIndex())
        is_batch = isinstance(data, tuple) and len(data) >= 2 and data[0] == "key" and data[1] == "ui.tabs.batch"
        if not is_batch:
            # 폴백 텍스트 비교
            name = self.main_tabs.tabText(self.main_tabs.currentIndex())
            is_batch = name in ("대량처리", "Batch")
        if is_batch:
            current_tab = self.get_current_data_tab()
            if not current_tab or not current_tab.data:
                if input_a_str or input_b_str:
                    self.log("불가능 제거 완료 (입력만 처리)")
                else:
                    QMessageBox.information(self, _("ui.msg.title.info"), _("ui.msg.no_data"))
                return
            
            # 작업 전 현재 상태를 히스토리에 저장
            current_tab.add_to_data_history("작업 전 (불가능 제거)")
            
            self.log_verbose(f"'{current_tab.tab_name}' 탭의 {len(current_tab.data)}개 항목에서 불가능 패턴 제거 수행")
            
            # 유효한 데이터만 필터링
            valid_data = []
            removed_count = 0
            
            for i, shape_code in enumerate(current_tab.data):
                try:
                    shape = Shape.from_string(shape_code)
                    classification, reason = analyze_shape(shape_code, shape)
                    if classification != ShapeType.IMPOSSIBLE.value:
                        valid_data.append(shape_code)
                    else:
                        removed_count += 1
                        self.log_verbose(f"제거됨: {shape_code} ({reason})")
                except Exception as e:
                    removed_count += 1
                    self.log_verbose(f"오류로 제거됨: {shape_code} ({str(e)})")
            
            # 현재 탭의 데이터를 필터링된 결과로 교체
            current_tab.data = valid_data
            current_tab.update_table()
            
            # 작업 완료 후 히스토리에 추가
            current_tab.add_to_data_history("불가능 제거 완료")
            
            self.log(f"불가능 제거 완료: {len(valid_data)}개 유효, {removed_count}개 제거")
        else:
            # 분석 도구 탭에서는 입력 A/B 처리
            input_a_str = self.input_a.text().strip()
            input_b_str = self.input_b.text().strip()
            
            if input_a_str:
                try:
                    shape = Shape.from_string(input_a_str)
                    classification, reason = analyze_shape(input_a_str, shape)
                    if classification == ShapeType.IMPOSSIBLE.value:
                        self.input_a.setText("")
                        self.log(f"입력 A 불가능 패턴 제거: {reason}")
                    else:
                        self.log_verbose(f"입력 A 유효함: {classification}")
                except Exception as e:
                    self.input_a.setText("")
                    self.log(f"입력 A 오류로 제거: {str(e)}")
            
            if input_b_str:
                try:
                    shape = Shape.from_string(input_b_str)
                    classification, reason = analyze_shape(input_b_str, shape)
                    if classification == ShapeType.IMPOSSIBLE.value:
                        self.input_b.setText("")
                        self.log(f"입력 B 불가능 패턴 제거: {reason}")
                    else:
                        self.log_verbose(f"입력 B 유효함: {classification}")
                except Exception as e:
                    self.input_b.setText("")
                    self.log(f"입력 B 오류로 제거: {str(e)}")
            
            if input_a_str or input_b_str:
                self.log("불가능 제거 완료 (입력만 처리)")
    
    def on_reverse(self):
        """역순 버튼 클릭 시 호출 - 데이터들의 문자를 역순으로 배치"""
        def reverse_shape(shape_code: str) -> str:
            try:
                return shape_code[::-1]  # 문자열을 역순으로 변환
            except Exception as e:
                raise Exception(f"역순 변환 실패: {str(e)}")
        
        self.process_data_operation("역순", reverse_shape)
    
    def on_corner(self):
        """Corner 버튼 클릭 시 호출 - corner_tracer.py 기능 수행"""
        from corner_tracer import corner_process
        from shape import Shape
        
        def corner_shape_for_gui(shape_code: str) -> str:
            try:
                shape_obj = Shape.from_string(shape_code)
                result, _ = corner_process(shape_obj)
                return result
            except Exception as e:
                raise Exception(f"Corner 처리 실패: {str(e)}")
        
        self.process_data_operation("Corner", corner_shape_for_gui)
    
    def on_claw(self):
        """Claw 버튼 클릭 시 호출 - claw_tracer.py 기능 수행"""
        from claw_tracer import claw_process
        
        def claw_shape_for_gui(shape_code: str) -> str:
            try:
                # claw_process 호출 시 logger 인자 전달
                return claw_process(shape_code, logger=self.log if self.log_checkbox.isChecked() else None)
            except Exception as e:
                raise Exception(f"Claw 처리 실패: {str(e)}")
        
        self.process_data_operation("Claw", claw_shape_for_gui)
    
    def on_mirror(self):
        """미러 버튼 클릭 시 호출"""
        def mirror_shape_for_gui(shape_code: str) -> str:
            try:
                shape = Shape.from_string(shape_code)
                return repr(shape.mirror())
            except Exception as e:
                return f"오류: {str(e)}"
        
        self.process_data_operation("mirror", mirror_shape_for_gui)
    
    def on_cornerize(self):
        """코너화 버튼 클릭 시 호출 - 모든 문자 사이에 ':' 추가 (색코드 제외)"""
        def cornerize_shape(shape_code: str) -> str:
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
        
        self.process_data_operation("cornerize", cornerize_shape)
    
    def on_hybrid(self):
        """하이브리드 버튼 클릭 시 호출 - 도형을 두 부분으로 분리"""
        def hybrid_shape(shape_code: str) -> list[str]:
            try:
                if not shape_code.strip():
                    return ["", ""]
                
                shape = Shape.from_string(shape_code)
                output_a, output_b = shape.hybrid()
                
                # 두 개의 별도 결과 반환
                result_a = repr(output_a) if output_a.layers else ""
                result_b = repr(output_b) if output_b.layers else ""
                
                return [result_a, result_b]
                    
            except Exception as e:
                return [f"오류: {str(e)}", ""]
        
        self.process_data_operation("hybrid", hybrid_shape)

    def on_browse_file(self):
        """파일 찾아보기 대화상자 열기 및 자동 로드"""
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "도형 데이터 파일 선택",
            "data/",  # 기본 경로를 data 폴더로 설정
            "텍스트 파일 (*.txt);;모든 파일 (*.*)"
        )
        
        if file_path:
            self.selected_file_path = file_path
            self.file_path_label.setText(file_path)
            self.file_path_label.setStyleSheet("color: black;")
            self.log_verbose(f"파일 선택됨: {file_path}")
            # 파일 선택 후 자동으로 로드
            self.load_file(file_path)
    
    def load_file(self, file_path):
        """파일 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
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
            tab_name = os.path.splitext(os.path.basename(file_path))[0]
            self.add_data_tab(tab_name, shape_codes)
            
            self.log(f"파일 로드 완료: {len(shape_codes)}개의 도형 코드를 새 탭 '{tab_name}'에 불러왔습니다.")
            
            # 마지막으로 열었던 파일 경로 저장
            self.last_opened_data_path = file_path
            self.settings.setValue("last_data_path", file_path)
            
            # 파일 로드 성공 플래그 설정
            self.file_load_success = True
            
        except Exception as e:
            QMessageBox.critical(self, _("ui.msg.title.error"), _("ui.msg.file_load_error", error=str(e)))
            self.log(f"파일 로드 오류: {str(e)}")
    
    def on_load_file(self):
        """선택된 파일 로드 (호환성 유지)"""
        if self.selected_file_path:
            self.load_file(self.selected_file_path)
    
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
        self.clear_log()
        self.log_verbose("로그가 지워졌습니다.")

    def on_main_tab_changed(self, index):
        """메인 탭 변경 시 호출"""
        bar = self.main_tabs.tabBar()
        data = bar.tabData(index)
        is_batch = False
        if isinstance(data, tuple) and len(data) >= 2 and data[0] == "key":
            is_batch = (data[1] == "ui.tabs.batch")
        else:
            # 폴백: 표시 텍스트로 판단 (다국어 대비)
            name = self.main_tabs.tabText(index)
            is_batch = name in ("대량처리", "Batch")
        
        if is_batch:
            self.switch_to_batch_mode()
        else:
            # 대량처리가 아닌 모든 탭(분석 도구, 공정트리 등)에서는 단일 모드로 복원
            self.switch_to_single_mode()
        
        # self.log(f"메인 탭이 {self.main_tabs.tabText(index)}로 변경되었습니다.")
    
    def _create_tree_view(self):
        view = TreeGraphicsView()
        view.setMinimumHeight(400)
        view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        view.setRenderHint(view.renderHints())
        return view

    def on_generate_process_tree(self):
        """공정 트리 생성 버튼 클릭 시 호출 (최적화)"""
        try:
            # 입력 A에서 도형 코드 가져오기
            input_shape_code = self.input_a.text().strip()
            if not input_shape_code:
                self.log(_("prompt.input.a.enter"))
                return
            
            self.log(f"공정 트리 생성: {input_shape_code}")
            
            # 공정 트리 계산
            root_node = process_tree_solver.solve_process_tree(input_shape_code)
            
            # 트리 시각화
            self._display_process_tree(root_node)
            
            # 루트 노드 operation에 따른 메시지 출력
            if root_node.operation == process_tree_solver.IMPOSSIBLE_OPERATION:
                self.log(f"'{input_shape_code}'은(는) 불가능한 도형 또는 문법 오류가 있습니다.")
            elif root_node.operation == "불가능":
                self.log(f"'{input_shape_code}'은(는) 논리적으로 불가능한 도형입니다.")
            elif root_node.operation == "문법 오류/생성 오류":
                self.log(f"'{input_shape_code}'은(는) 문법 오류가 있거나 트리 생성 중 오류가 발생했습니다.")
            elif root_node.operation == "클로추적실패":
                self.log(_("gui.claw.trace_failed", shape_code=input_shape_code))
            else:
                self.log(_("ui.msg.done"))
            
        except Exception as e:
            self.log(f"트리 생성 중 예상치 못한 오류: {str(e)[:50]}...")  # 오류 메시지 축약
            # 오류 메시지 표시
            self.tree_scene.clear()
            text_item = self.tree_scene.addText("트리 생성 중 예상치 못한 오류가 발생했습니다.")
            text_item.setPos(-150, 50)
            text_item.setDefaultTextColor(QColor(200, 50, 50))
    
    def _display_process_tree(self, root_node: ProcessNode):
        """유동적 크기 기반 트리 시각화"""
        # scene 완전 초기화
        self.tree_scene.clear()
        
        # 1단계: 노드 위젯들을 생성하고 임시 위치에 배치하여 실제 크기 측정
        node_widgets = {}
        node_sizes = {}
        
        levels = process_tree_solver.get_tree_levels(root_node)
        for level_nodes in levels:
            for node in level_nodes:
                widget = self._create_process_node_widget(node)
                proxy = self.tree_scene.addWidget(widget)
                proxy.setPos(0, 0)  # 임시 위치
                
                # 위젯 크기 측정을 위해 강제 업데이트
                widget.adjustSize()
                size = widget.size()
                
                node_widgets[node] = proxy
                node_sizes[node] = (size.width(), size.height())
        
        # 2단계: 실제 크기를 바탕으로 유동적 위치 계산
        node_positions = self._calculate_flexible_positions(root_node, node_sizes)
        
        # 3단계: 계산된 위치로 노드들 재배치
        for node, (x, y) in node_positions.items():
            if node in node_widgets:
                node_widgets[node].setPos(x, y)
        
        # 4단계: 실제 노드 크기 기반으로 화살표 그리기
        self._draw_flexible_arrows(root_node, node_positions, node_sizes)
        
        # scene 크기 최적화
        self.tree_scene.setSceneRect(self.tree_scene.itemsBoundingRect().adjusted(-30, -30, 30, 30))
    
    def _calculate_tree_positions_optimized(self, root_node: ProcessNode):
        """동적 위치 계산으로 자연스러운 트리 구조 구현"""
        positions = {}
        levels = process_tree_solver.get_tree_levels(root_node)
        
        node_width = 160   # 가로 간격 더 증가 (겹침 완전 방지)
        node_height = 140  # 세로 간격 더 증가 (세로 겹침 방지)
        
        # 하위 레벨부터 상위 레벨로 역순 계산 (bottom-up)
        for level_idx in reversed(range(len(levels))):
            level_nodes = levels[level_idx]
            y = level_idx * node_height
            
            if level_idx == len(levels) - 1:
                # 최하위 레벨 (기본 원료들): 균등 분산 배치
                if len(level_nodes) == 1:
                    positions[level_nodes[0]] = (0, y)
                else:
                    total_width = (len(level_nodes) - 1) * node_width
                    start_x = -total_width / 2
                    for node_idx, node in enumerate(level_nodes):
                        x = start_x + node_idx * node_width
                        positions[node] = (x, y)
            else:
                # 상위 레벨: 자식 노드들의 중앙에 배치
                for node in level_nodes:
                    if node.inputs:
                        # 자식 노드들의 x 좌표 평균 계산
                        child_x_positions = [positions[child][0] for child in node.inputs if child in positions]
                        if child_x_positions:
                            avg_x = sum(child_x_positions) / len(child_x_positions)
                            positions[node] = (avg_x, y)
                        else:
                            positions[node] = (0, y)
                    else:
                        positions[node] = (0, y)
                
                # 같은 레벨의 노드들이 겹치지 않도록 조정
                self._adjust_same_level_positions(level_nodes, positions, node_width)
        
        return positions
    
    def _adjust_same_level_positions(self, level_nodes, positions, min_spacing):
        """같은 레벨 노드들의 겹침 방지"""
        if len(level_nodes) <= 1:
            return
            
        # x 좌표로 정렬
        sorted_nodes = sorted(level_nodes, key=lambda n: positions[n][0])
        
        # 겹침 해결
        for i in range(1, len(sorted_nodes)):
            current_node = sorted_nodes[i]
            prev_node = sorted_nodes[i-1]
            
            current_x, current_y = positions[current_node]
            prev_x, prev_y = positions[prev_node]
            
            # 최소 간격보다 가까우면 조정
            if current_x - prev_x < min_spacing:
                new_x = prev_x + min_spacing
                positions[current_node] = (new_x, current_y)
    
    def _calculate_tree_positions(self, root_node: ProcessNode):
        """기존 호환성을 위한 래퍼 함수"""
        return self._calculate_tree_positions_optimized(root_node)
    
    def _calculate_flexible_positions(self, root_node: ProcessNode, node_sizes):
        """간단하고 확실한 겹침 방지 위치 계산 (동적 세로 간격)"""
        positions = {}
        levels = process_tree_solver.get_tree_levels(root_node)
        
        # 간격 설정
        horizontal_gap = 40   # 가로 간격 
        base_vertical_gap = 30  # 기본 세로 간격
        
        # 각 레벨의 최대 높이를 계산하여 동적 Y 좌표 결정
        level_y_positions = self._calculate_dynamic_level_heights(levels, node_sizes, base_vertical_gap)
        
        # 각 레벨을 독립적으로 처리 (bottom-up)
        for level_idx in reversed(range(len(levels))):
            level_nodes = levels[level_idx]
            base_y = level_y_positions[level_idx]
            
            if level_idx == len(levels) - 1:
                # 최하위 레벨: 단순 가로 배치
                self._layout_nodes_horizontally(level_nodes, node_sizes, positions, base_y, horizontal_gap)
            else:
                # 상위 레벨: 자식들 기준으로 배치하되 겹침 완전 방지
                self._layout_parent_nodes(level_nodes, node_sizes, positions, base_y, horizontal_gap)
        
        return positions
    
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
    
    def _layout_nodes_horizontally(self, nodes, node_sizes, positions, y, gap):
        """노드들을 가로로 배치 (겹침 절대 없음)"""
        if not nodes:
            return
            
        # 전체 폭 계산
        total_width = sum(node_sizes[node][0] for node in nodes) + gap * (len(nodes) - 1)
        start_x = -total_width / 2
        
        current_x = start_x
        for node in nodes:
            width, height = node_sizes[node]
            positions[node] = (current_x, y)
            current_x += width + gap
    
    def _layout_parent_nodes(self, nodes, node_sizes, positions, base_y, gap):
        """부모 노드들을 자식들 기준으로 배치하되 겹침 방지"""
        if not nodes:
            return
            
        # 1단계: 이상적인 위치 계산 (자식들의 중앙)
        ideal_positions = []
        for node in nodes:
            if node.inputs:
                child_centers = []
                for child in node.inputs:
                    if child in positions:
                        child_x, child_y = positions[child]
                        child_width, child_height = node_sizes[child]
                        child_center_x = child_x + child_width / 2
                        child_centers.append(child_center_x)
                
                if child_centers:
                    avg_center_x = sum(child_centers) / len(child_centers)
                    node_width = node_sizes[node][0]
                    ideal_x = avg_center_x - node_width / 2
                    ideal_positions.append((node, ideal_x))
                else:
                    ideal_positions.append((node, 0))
            else:
                ideal_positions.append((node, 0))
        
        # 2단계: x 좌표로 정렬
        ideal_positions.sort(key=lambda x: x[1])
        
        # 3단계: 겹침 해결하면서 실제 위치 배정
        actual_positions = []
        for i, (node, ideal_x) in enumerate(ideal_positions):
            node_width = node_sizes[node][0]
            
            if i == 0:
                # 첫 번째 노드는 이상적 위치 그대로
                actual_x = ideal_x
            else:
                # 이전 노드와 겹치지 않도록 조정
                prev_node, prev_x = actual_positions[-1]
                prev_width = node_sizes[prev_node][0]
                min_x = prev_x + prev_width + gap
                
                # 이상적 위치와 최소 위치 중 더 큰 값 선택
                actual_x = max(ideal_x, min_x)
            
            actual_positions.append((node, actual_x))
            positions[node] = (actual_x, base_y)
    

    
    def _draw_flexible_arrows(self, root_node: ProcessNode, positions, node_sizes):
        """실제 노드 크기 기반 화살표 그리기"""
        import math
        
        def draw_connections_recursive(node):
            if not node.inputs:
                return
                
            parent_pos = positions[node]
            parent_width, parent_height = node_sizes[node]
            
            for child_node in node.inputs:
                if child_node not in positions:
                    continue
                    
                child_pos = positions[child_node]
                child_width, child_height = node_sizes[child_node]
                
                # 연결점 계산 (실제 노드 크기 기반)
                parent_center_x = parent_pos[0] + parent_width / 2
                parent_bottom_y = parent_pos[1] + parent_height
                
                child_center_x = child_pos[0] + child_width / 2
                child_top_y = child_pos[1]
                
                # 화살표 여백
                arrow_margin = 8
                
                # 연결선 시작점과 끝점
                x1, y1 = parent_center_x, parent_bottom_y
                x2, y2 = child_center_x, child_top_y - arrow_margin
                
                # 연결선 그리기
                pen = QPen(QColor(100, 100, 100), 2)
                line = self.tree_scene.addLine(x1, y1, x2, y2, pen)
                
                # 화살표 그리기
                self._draw_arrow_head(x1, y1, x2, y2)
                
                # 재귀 호출
                draw_connections_recursive(child_node)
        
        draw_connections_recursive(root_node)
    
    def _draw_arrow_head(self, x1, y1, x2, y2):
        """화살표 머리 그리기"""
        import math
        
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return
            
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0:
            return
            
        unit_x = dx / length
        unit_y = dy / length
        
        arrow_length = 10
        arrow_angle = math.pi / 4  # 45도
        
        # 화살표 꼭짓점 계산
        arrow_x1 = x2 - arrow_length * (unit_x * math.cos(arrow_angle) - unit_y * math.sin(arrow_angle))
        arrow_y1 = y2 - arrow_length * (unit_y * math.cos(arrow_angle) + unit_x * math.sin(arrow_angle))
        arrow_x2 = x2 - arrow_length * (unit_x * math.cos(arrow_angle) + unit_y * math.sin(arrow_angle))
        arrow_y2 = y2 - arrow_length * (unit_y * math.cos(arrow_angle) - unit_x * math.sin(arrow_angle))
        
        # 화살표 삼각형
        arrow_polygon = QPolygonF([
            QPointF(x2, y2),
            QPointF(arrow_x1, arrow_y1),
            QPointF(arrow_x2, arrow_y2)
        ])
        
        arrow_pen = QPen(QColor(80, 80, 80), 1)
        arrow_brush = QColor(80, 80, 80)
        self.tree_scene.addPolygon(arrow_polygon, arrow_pen, arrow_brush)
    
    def _draw_tree_connections_with_arrows(self, root_node: ProcessNode, positions):
        """정확한 화살표 연결선 그리기 (노드 경계 고려)"""
        import math
        
        # 노드 크기 상수 (실제 위젯 크기 추정)
        NODE_WIDTH = 120
        NODE_HEIGHT = 70
        
        def draw_connections_recursive(node):
            if not node.inputs:
                return
                
            parent_pos = positions[node]
            for child_node in node.inputs:
                child_pos = positions[child_node]
                
                # 연결선 좌표 계산 (노드 경계 기준)
                parent_center_x = parent_pos[0] + NODE_WIDTH / 2
                parent_bottom_y = parent_pos[1] + NODE_HEIGHT
                
                child_center_x = child_pos[0] + NODE_WIDTH / 2  
                child_top_y = child_pos[1]
                
                # 연결선 시작점과 끝점
                x1, y1 = parent_center_x, parent_bottom_y
                x2, y2 = child_center_x, child_top_y
                
                # 화살표 머리가 노드 경계에 닿지 않도록 끝점 조정
                arrow_margin = 8  # 화살표와 노드 사이 여백
                dx = x2 - x1
                dy = y2 - y1
                
                if dy != 0:  # 세로 방향이 있을 때만 조정
                    length = math.sqrt(dx*dx + dy*dy)
                    if length > 0:
                        unit_x = dx / length
                        unit_y = dy / length
                        
                        # 끝점을 노드 경계에서 여백만큼 떨어뜨림
                        x2_adj = x2 - unit_x * arrow_margin
                        y2_adj = y2 - unit_y * arrow_margin
                    else:
                        x2_adj, y2_adj = x2, y2
                else:
                    x2_adj, y2_adj = x2, y2 - arrow_margin
                
                # 연결선 그리기 (조정된 끝점까지)
                pen = QPen(QColor(100, 100, 100), 2)
                line = self.tree_scene.addLine(x1, y1, x2_adj, y2_adj, pen)
                
                # 화살표 머리 그리기 (작고 날렵하게)
                arrow_length = 10
                arrow_angle = math.pi / 4  # 45도 (더 날카롭게)
                
                # 화살표 방향 재계산
                dx_arrow = x2_adj - x1
                dy_arrow = y2_adj - y1
                
                if dx_arrow != 0 or dy_arrow != 0:
                    length_arrow = math.sqrt(dx_arrow*dx_arrow + dy_arrow*dy_arrow)
                    unit_x_arrow = dx_arrow / length_arrow
                    unit_y_arrow = dy_arrow / length_arrow
                    
                    # 화살표 꼭짓점 계산
                    arrow_tip_x, arrow_tip_y = x2_adj, y2_adj
                    
                    arrow_x1 = arrow_tip_x - arrow_length * (unit_x_arrow * math.cos(arrow_angle) - unit_y_arrow * math.sin(arrow_angle))
                    arrow_y1 = arrow_tip_y - arrow_length * (unit_y_arrow * math.cos(arrow_angle) + unit_x_arrow * math.sin(arrow_angle))
                    arrow_x2 = arrow_tip_x - arrow_length * (unit_x_arrow * math.cos(arrow_angle) + unit_y_arrow * math.sin(arrow_angle))
                    arrow_y2 = arrow_tip_y - arrow_length * (unit_y_arrow * math.cos(arrow_angle) - unit_x_arrow * math.sin(arrow_angle))
                    
                    # 화살표 삼각형 그리기
                    arrow_polygon = QPolygonF([
                        QPointF(arrow_tip_x, arrow_tip_y),
                        QPointF(arrow_x1, arrow_y1),
                        QPointF(arrow_x2, arrow_y2)
                    ])
                    
                    # 화살표 색상과 스타일
                    arrow_pen = QPen(QColor(80, 80, 80), 1)
                    arrow_brush = QColor(80, 80, 80)
                    arrow = self.tree_scene.addPolygon(arrow_polygon, arrow_pen, arrow_brush)
                
                # 재귀적으로 자식 노드들의 연결선도 그림
                draw_connections_recursive(child_node)
        
        draw_connections_recursive(root_node)
    
    def _draw_tree_connections(self, root_node: ProcessNode, positions):
        """기존 호환성을 위한 래퍼 함수"""
        self._draw_tree_connections_with_arrows(root_node, positions)
    
    def _create_process_node_widget(self, node: ProcessNode) -> QWidget:
        """개별 공정 노드 위젯 생성 (자동 크기 조정으로 도형이 잘 보이게, border 1줄, 툴팁 지원)"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 도형 시각화
        if node.shape_obj and node.operation != process_tree_solver.IMPOSSIBLE_OPERATION:
            shape_widget = ShapeWidget(node.shape_obj, compact=True)
            shape_widget.setStyleSheet("background-color: white; border: 1px solid #999; border-radius: 4px; padding: 4px;")
            shape_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            layout.addWidget(shape_widget, 0, Qt.AlignmentFlag.AlignCenter)
        else:
            # 유효하지 않거나 불가능한 도형인 경우
            error_widget = QLabel("?")
            error_widget.setStyleSheet("color: red; font-size: 24px; border: 1px solid #999; border-radius: 4px; background-color: white; padding: 15px;")
            error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(error_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 컨테이너도 자동 크기 조정
        container.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        
        # 컨테이너 border 제거, 배경만 약간 투명하게
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 240);
                border: none;
                border-radius: 6px;
            }
        """)
        
        # 툴팁 텍스트 구성
        shape_name = getattr(node.shape_obj, 'name', None) or "(이름 없음)"
        if node.operation == process_tree_solver.IMPOSSIBLE_OPERATION:
            tooltip = _("ui.tooltip.process.impossible", code=node.shape_code)
        else:
            tooltip = _("ui.tooltip.process", operation=str(node.operation), code=node.shape_code)
            if shape_name:
                tooltip += "\n" + _("ui.tooltip.shape_name", name=shape_name)
        container.setToolTip(tooltip)
        
        return container
    
    def _clear_process_tree(self):
        """공정 트리 표시 영역을 완전히 지우기 (최적화)"""
        # QGraphicsScene 완전 초기화
        self.tree_scene.clear()
        
        # 복잡한 예시 트리 표시 (초기화 시에만)
        if not hasattr(self, '_tree_initialized'):
            self._show_example_tree()
            self._tree_initialized = True
    
    def _show_example_tree(self):
        """복잡한 구조의 예시 트리를 표시 (데이터 기반 구현)"""
        try:
            # 복잡한 4레벨 예시 트리 데이터 정의
            example_tree_data = {
                "shape_code": "CuCuCuCu:RrRrRrRr:CcCcCcCc:P-P-P-P-",
                "operation": "최종목표", 
                "inputs": [
                    {
                        "shape_code": "CuCuCuCu:RrRrRrRr:CcCcCcCc",
                        "operation": "2차조합",
                        "inputs": [
                            {
                                "shape_code": "CuCuCuCu:RrRrRrRr", 
                                "operation": "1차가공",
                                "inputs": [
                                    {"shape_code": "CuCuCuCu", "operation": "원료", "inputs": []},
                                    {"shape_code": "RrRrRrRr", "operation": "원료", "inputs": []}
                                ]
                            },
                            {
                                "shape_code": "CcCcCcCc:SsSsSsSs",
                                "operation": "1차가공", 
                                "inputs": [
                                    {"shape_code": "CcCcCcCc", "operation": "원료", "inputs": []},
                                    {"shape_code": "SsSsSsSs", "operation": "원료", "inputs": []}
                                ]
                            }
                        ]
                    },
                    {
                        "shape_code": "P-P-P-P-:Cu------:Rr------",
                        "operation": "2차조합",
                        "inputs": [
                            {
                                "shape_code": "P-P-P-P-:Cu------",
                                "operation": "1차가공",
                                "inputs": [
                                    {"shape_code": "P-P-P-P-", "operation": "원료", "inputs": []},
                                    {"shape_code": "Cu------", "operation": "원료", "inputs": []}
                                ]
                            },
                            {
                                "shape_code": "Rr------:CcCcCcCc", 
                                "operation": "1차가공",
                                "inputs": [
                                    {"shape_code": "Rr------", "operation": "원료", "inputs": []},
                                    {"shape_code": "CcCcCcCc", "operation": "원료", "inputs": []}  # 재사용
                                ]
                            }
                        ]
                    }
                ]
            }
            
            # 데이터를 ProcessNode 트리로 변환
            root_node = process_tree_solver.create_tree_from_data(example_tree_data)
            
            # 플렉서블 시스템으로 트리 표시
            self._display_process_tree(root_node)
            
            # 설명 텍스트 추가
            desc_text = self.tree_scene.addText("복잡한 예시 트리입니다. '공정트리 생성'으로 실제 트리를 생성하세요.", 
                                              QFont("Arial", 10))
            desc_text.setPos(-150, -50)
            desc_text.setDefaultTextColor(QColor(100, 100, 100))
            
        except Exception as e:
            print(f"예시 트리 생성 오류: {e}")
            import traceback
            traceback.print_exc()
    

    
    def switch_to_batch_mode(self):
        """대량처리 모드로 전환"""
        self.apply_button.setEnabled(False)
        
        # 배치모드에서 비활성화할 버튼들
        self.swap_btn.setEnabled(False)
        self.cutter_btn.setEnabled(False)
        self.simple_cutter_btn.setEnabled(False)
        self.quad_cutter_btn.setEnabled(False)
        
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
        
        self.rotate_180_btn.clicked.disconnect()
        self.rotate_180_btn.clicked.connect(lambda: self.on_batch_operation("rotate_180"))
        
        self.paint_btn.clicked.disconnect()
        self.paint_btn.clicked.connect(lambda: self.on_batch_operation("paint"))
        
        self.crystal_btn.clicked.disconnect()
        self.crystal_btn.clicked.connect(lambda: self.on_batch_operation("crystal_generator"))
        
        self.classifier_btn.clicked.disconnect()
        self.classifier_btn.clicked.connect(lambda: self.on_batch_operation("classifier"))
        
        # 스태커를 대량처리용으로 연결
        self.stack_btn.clicked.disconnect()
        self.stack_btn.clicked.connect(lambda: self.on_batch_operation("stack"))
        
        # 데이터 처리 버튼들의 클릭 이벤트는 이미 대량처리를 지원하므로 그대로 유지
    
    def switch_to_single_mode(self):
        """단일 모드로 전환"""
        # 비활성화된 버튼들을 다시 활성화
        self.swap_btn.setEnabled(True)
        self.cutter_btn.setEnabled(True)
        self.simple_cutter_btn.setEnabled(True)
        self.quad_cutter_btn.setEnabled(True)
        
        # 버튼 클릭 이벤트를 단일 모드용으로 복원
        self.destroy_half_btn.clicked.disconnect()
        self.destroy_half_btn.clicked.connect(self.on_destroy_half)
        
        self.push_pin_btn.clicked.disconnect()
        self.push_pin_btn.clicked.connect(self.on_push_pin)
        
        self.apply_physics_btn.clicked.disconnect()
        self.apply_physics_btn.clicked.connect(self.on_apply_physics)
        
        self.simple_cutter_btn.clicked.disconnect()
        self.simple_cutter_btn.clicked.connect(self.on_simple_cutter)
        
        self.quad_cutter_btn.clicked.disconnect()
        self.quad_cutter_btn.clicked.connect(self.on_quad_cutter)
        
        self.cutter_btn.clicked.disconnect()
        self.cutter_btn.clicked.connect(self.on_cutter)
        
        self.rotate_cw_btn.clicked.disconnect()
        self.rotate_cw_btn.clicked.connect(lambda: self.on_rotate(True))
        
        self.rotate_ccw_btn.clicked.disconnect()
        self.rotate_ccw_btn.clicked.connect(lambda: self.on_rotate(False))
        
        self.rotate_180_btn.clicked.disconnect()
        self.rotate_180_btn.clicked.connect(self.on_rotate_180_building)
        
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

    def on_log_level_changed(self):
        """상세 로그 표시 설정이 변경되었을 때 로그를 다시 렌더링합니다."""
        self.refresh_log_display()
        self.log_verbose(f"상세 로그 레벨이 {'활성화' if self.log_checkbox.isChecked() else '비활성화'}되었습니다.")
    
    def clear_log(self):
        """로그 창과 저장된 로그 엔트리들을 모두 지웁니다."""
        self.log_entries.clear()
        self.log_output.clear()
    
    def refresh_log_display(self):
        """저장된 로그 엔트리들을 현재 설정에 따라 다시 표시합니다."""
        self.log_output.clear()
        
        for message, is_verbose in self.log_entries:
            # 상세 로그가 비활성화되어 있고 verbose 로그면 건너뛰기
            if is_verbose and hasattr(self, 'log_checkbox') and not self.log_checkbox.isChecked():
                continue
                
            if is_verbose:
                # 상세 로그는 진한 회색으로 표시 (HTML 이스케이프 처리)
                escaped_message = html.escape(message)
                self.log_output.append(f'<span style="color: #666666;">{escaped_message}</span>')
            else:
                # 일반 로그는 기본 색상
                self.log_output.append(message)



    def get_main_window(self):
        """메인 윈도우 참조 가져오기"""
        widget = self
        while widget:
            if isinstance(widget, ShapezGUI):
                return widget
            widget = widget.parent()
        return None

# moved to gui.widgets
class _Legacy_CustomTabWidget(QTabWidget):
    """탭 삭제 가능한 커스텀 탭 위젯"""
    tab_close_requested = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.on_tab_close_requested)
    
    def on_tab_close_requested(self, index):
        if self.count() > 1:  # 최소 1개 탭은 유지
            self.tab_close_requested.emit(index)

# moved to gui.widgets
class _Legacy_DragDropTableWidget(QTableWidget):
    """드래그 앤 드롭을 지원하는 테이블 위젯"""
    rows_reordered = pyqtSignal(int, int) # 실제 데이터 리스트 순서 변경을 위한 시그널
    
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True) # 드롭 허용
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.drag_start_row = -1
        self.drag_start_point = QPoint() # 드래그 시작 위치 저장
        self.setMouseTracking(True)  # 마우스 추적 활성화
        self.shape_tooltip = None  # 도형 툴팁 위젯
        self.tooltip_timer = QTimer()
        # 툴팁 표시 타이머 연결
        self.tooltip_timer.timeout.connect(self.show_shape_tooltip)
        self.tooltip_timer.setSingleShot(True)
        self.hovered_item = None
        self.hover_position = QPoint()

        # 선택 변경 시, 숨겨진(필터된) 행은 선택 해제하여 검색결과 내 선택만 유지
        self.itemSelectionChanged.connect(self._prune_hidden_from_selection)

    def _prune_hidden_from_selection(self):
        sm = self.selectionModel()
        if not sm:
            return
        # 숨긴 행의 선택을 제거
        for row in range(self.rowCount()):
            if self.isRowHidden(row):
                if sm.isRowSelected(row, self.rootIndex()):
                    self.setRangeSelected(
                        self.visualRangeForRow(row),
                        False
                    )

    def visualRangeForRow(self, row: int):
        # 헬퍼: 한 행 전체의 선택 범위
        from PyQt6.QtCore import QItemSelection
        left = self.model().index(row, 0)
        right = self.model().index(row, max(0, self.columnCount()-1))
        return QItemSelection(left, right)

    def keyPressEvent(self, event):
        # Ctrl+A 처리: 필터된(보이는) 행만 선택
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self.select_all_visible_rows()
            event.accept()
            return
        super().keyPressEvent(event)

    def select_all_visible_rows(self):
        self.clearSelection()
        for row in range(self.rowCount()):
            if not self.isRowHidden(row):
                self.selectRow(row)

    # ===== 마우스/드래그/툴팁 핸들러 (데이터 테이블용) =====
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item:
                self.drag_start_row = item.row()
                self.drag_start_point = event.pos()
            self.hide_shape_tooltip()
            self.tooltip_timer.stop()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_start_row != -1:
            if (event.pos() - self.drag_start_point).manhattanLength() > QApplication.startDragDistance():
                self.startDrag(Qt.DropAction.MoveAction)
        else:
            if self.drag_start_row == -1:
                item = self.itemAt(event.pos())
                if self.hovered_item != item:
                    self.hide_shape_tooltip()
                    self.hovered_item = item
                    self.tooltip_timer.stop()
                    if item and item.text().strip():
                        self.hover_position = event.globalPosition().toPoint()
                        self.tooltip_timer.start(300)
            else:
                self.hide_shape_tooltip()
                self.tooltip_timer.stop()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.drag_start_row = -1
        self.drag_start_point = QPoint()

    def startDrag(self, supportedActions):
        selected_items = self.selectedItems()
        if selected_items:
            mimeData = QMimeData()
            mimeData.setText(str(self.drag_start_row))
            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
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
            from_row = int(event.mimeData().text())
            drop_pos_y = event.position().toPoint().y()
            to_row = self.rowAt(drop_pos_y)
            if to_row == -1:
                to_row = self.rowCount()
            if from_row != to_row:
                adjusted_to_row = to_row
                if from_row < to_row:
                    adjusted_to_row = to_row - 1
                self.rows_reordered.emit(from_row, adjusted_to_row)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            super().dropEvent(event)
        self.drag_start_row = -1
        self.drag_start_point = QPoint()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hide_shape_tooltip()
        self.tooltip_timer.stop()
        self.hovered_item = None

    def show_shape_tooltip(self):
        if not self.hovered_item:
            return
        try:
            if not self.hovered_item.text().strip():
                return
        except RuntimeError:
            # QTableWidgetItem이 이미 삭제된 경우
            self.hovered_item = None
            return
        try:
            shape_code = self.hovered_item.text().strip()
            from shape import Shape
            shape = Shape.from_string(shape_code)
            self.shape_tooltip = ShapeTooltipWidget(shape)  # from gui.widgets
            screen_rect = QApplication.primaryScreen().geometry()
            tooltip_size = self.shape_tooltip.sizeHint()
            pos = self.hover_position + QPoint(10, 10)
            if pos.x() + tooltip_size.width() > screen_rect.right():
                pos.setX(self.hover_position.x() - tooltip_size.width() - 10)
            if pos.y() + tooltip_size.height() > screen_rect.bottom():
                pos.setY(self.hover_position.y() - tooltip_size.height() - 10)
            self.shape_tooltip.move(pos)
            self.shape_tooltip.show()
        except Exception as e:
            from i18n import _
            self.setToolTip(_("ui.tooltip.shape_code", code=shape_code) + "\n" + _("ui.tooltip.parse_error", error=str(e)))

    def hide_shape_tooltip(self):
        if self.shape_tooltip:
            self.shape_tooltip.close()
            self.shape_tooltip = None
        self.setToolTip("")


class BatchWorkerThread(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished_with_results = pyqtSignal(dict, list, int, bool)  # result_map, append_list, error_count, canceled

    def __init__(self, indices_to_process, data_snapshot, process_func):
        super().__init__()
        self._indices = list(indices_to_process)
        self._data = list(data_snapshot)
        self._process_func = process_func
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        result_map = {}
        append_list = []
        error_count = 0
        total = len(self._indices)
        for pos, idx in enumerate(self._indices, start=1):
            if self._cancel_requested:
                self.progress.emit(pos, total)
                break
            try:
                code = self._data[idx]
                mapped_value, append_values = self._process_func(code, idx)
                if mapped_value is not None:
                    result_map[idx] = mapped_value
                if append_values:
                    append_list.extend(append_values)
            except Exception:
                error_count += 1
            if pos % 50 == 0 or pos == total:
                self.progress.emit(pos, total)
        self.finished_with_results.emit(result_map, append_list, error_count, self._cancel_requested)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item:
                self.drag_start_row = item.row()
                self.drag_start_point = event.pos() # 드래그 시작 위치 저장
            # 마우스 클릭 시 툴팁 숨기기
            self.hide_shape_tooltip()
            self.tooltip_timer.stop()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_start_row != -1:
            # 드래그 임계값 이상 이동했을 때만 드래그 시작
            if (event.pos() - self.drag_start_point).manhattanLength() > QApplication.startDragDistance():
                self.startDrag(Qt.DropAction.MoveAction)
        else:
            # 드래그 중이 아닐 때만 툴팁 처리
            if self.drag_start_row == -1:
                # 현재 마우스 위치의 아이템 찾기
                item = self.itemAt(event.pos())
                
                # 이전 호버 아이템과 다르면 툴팁 숨기기
                if self.hovered_item != item:
                    self.hide_shape_tooltip()
                    self.hovered_item = item
                    self.tooltip_timer.stop()
                    
                    if item and item.text().strip():
                        # 호버 위치 저장
                        self.hover_position = event.globalPosition().toPoint()
                        # 짧은 지연 후 툴팁 표시
                        self.tooltip_timer.start(300)  # 300ms 지연
            else:
                # 드래그 중이면 툴팁 숨기기
                self.hide_shape_tooltip()
                self.tooltip_timer.stop()
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """마우스를 놓았을 때 드래그 상태 초기화"""
        super().mouseReleaseEvent(event)
        # 드래그 상태 초기화
        self.drag_start_row = -1
        self.drag_start_point = QPoint()

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
    

    
    def leaveEvent(self, event):
        """마우스가 테이블을 벗어날 때 툴팁 숨기기"""
        super().leaveEvent(event)
        self.hide_shape_tooltip()
        self.tooltip_timer.stop()
        self.hovered_item = None
    
    def show_shape_tooltip(self):
        """도형 툴팁 표시"""
        if not self.hovered_item or not self.hovered_item.text().strip():
            return
            
        shape_code = self.hovered_item.text().strip()
        
        try:
            from shape import Shape
            shape = Shape.from_string(shape_code)
            
            # 툴팁 위젯 생성
            self.shape_tooltip = ShapeTooltipWidget(shape)  # from gui.widgets
            
            # 화면 크기 고려하여 툴팁 위치 조정
            screen_rect = QApplication.primaryScreen().geometry()
            tooltip_size = self.shape_tooltip.sizeHint()
            
            # 기본 위치 (마우스 오른쪽 아래)
            pos = self.hover_position + QPoint(10, 10)
            
            # 화면 오른쪽 경계를 벗어나면 왼쪽으로 이동
            if pos.x() + tooltip_size.width() > screen_rect.right():
                pos.setX(self.hover_position.x() - tooltip_size.width() - 10)
            
            # 화면 아래쪽 경계를 벗어나면 위쪽으로 이동
            if pos.y() + tooltip_size.height() > screen_rect.bottom():
                pos.setY(self.hover_position.y() - tooltip_size.height() - 10)
            
            self.shape_tooltip.move(pos)
            self.shape_tooltip.show()
            
        except Exception as e:
            # 도형 파싱 실패 시 기본 툴팁 사용
            self.setToolTip(_("ui.tooltip.shape_code", code=shape_code) + "\n" + _("ui.tooltip.parse_error", error=str(e)))



    
    def hide_shape_tooltip(self):
        """도형 툴팁 숨기기"""
        if self.shape_tooltip:
            self.shape_tooltip.close()
            self.shape_tooltip = None
        self.setToolTip("")

# moved to gui.widgets
class _Legacy_ShapeTooltipWidget(QFrame):
    """도형 시각화를 위한 툴팁 위젯"""
    def __init__(self, shape):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 스타일시트 적용
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(50, 50, 50, 240);
                border: 1px solid #666;
                border-radius: 8px;
                padding: 8px;
            }
            QLabel {
                color: white;
                background-color: transparent;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 도형 위젯 추가 (컴팩트 모드로)
        shape_widget = ShapeWidget(shape, compact=True)
        shape_widget.setStyleSheet("background-color: white; border-radius: 4px; padding: 1px;")
        shape_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(shape_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 도형 코드 표시 (반투명 배경)
        code_label = QLabel(_("ui.tooltip.shape_code", code=repr(shape)))
        code_label.setStyleSheet(
            """
            font-size: 11px;
            color: black;
            font-family: 'Consolas', 'Monaco', monospace;
            background-color: rgba(255, 255, 255, 200);
            border-radius: 4px;
            padding: 2px 4px;
            """
        )
        code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(code_label)
        
        self.setLayout(layout)
        self.adjustSize()
        
        # 고정 크기로 설정하여 오른쪽 갭 방지
        size = self.sizeHint()
        self.setFixedSize(size)
        
        # 그림자 효과
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(2)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(shadow)

# moved to gui.widgets
class _Legacy_LogWidget(QTextEdit):
    """도형 코드에 마우스를 올리면 툴팁을 표시하는 로그 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.shape_tooltip = None
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.setInterval(300) # 300ms delay
        self.tooltip_timer.timeout.connect(self.show_shape_tooltip)
        self.last_mouse_pos = QPoint()

    def mouseMoveEvent(self, event):
        self.last_mouse_pos = event.pos()
        self.tooltip_timer.start()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.tooltip_timer.stop()
        self.hide_shape_tooltip()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        self.hide_shape_tooltip()
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        self.hide_shape_tooltip()
        super().mousePressEvent(event)

    def show_shape_tooltip(self):
        self.hide_shape_tooltip()

        cursor = self.cursorForPosition(self.last_mouse_pos)
        pos_in_line = cursor.positionInBlock()
        line_text = cursor.block().text()

        import re
        found_code = None
        # Regex for shape-like codes
        for match in re.finditer(r'[\w:-]+', line_text):
            if match.start() <= pos_in_line < match.end():
                potential_code = match.group(0).strip(":")
                if not potential_code: continue
                try:
                    Shape.from_string(potential_code)
                    found_code = potential_code
                    break
                except Exception:
                    continue
        
        if not found_code:
            return

        try:
            shape = Shape.from_string(found_code)
            self.shape_tooltip = ShapeTooltipWidget(shape)  # from gui.widgets
            
            global_pos = self.mapToGlobal(self.last_mouse_pos)
            screen_rect = QApplication.primaryScreen().geometry()
            tooltip_size = self.shape_tooltip.sizeHint()
            
            pos = global_pos + QPoint(20, 20)
            
            if pos.x() + tooltip_size.width() > screen_rect.right():
                pos.setX(global_pos.x() - tooltip_size.width() - 20)
            if pos.y() + tooltip_size.height() > screen_rect.bottom():
                pos.setY(global_pos.y() - tooltip_size.height() - 20)
            
            self.shape_tooltip.move(pos)
            self.shape_tooltip.show()

        except Exception:
            self.hide_shape_tooltip()

    def hide_shape_tooltip(self):
        if self.shape_tooltip:
            self.shape_tooltip.close()
            self.shape_tooltip = None

# moved to gui.widgets
class _Legacy_DataTabWidget(QWidget):
    """개별 데이터 탭 위젯"""
    def __init__(self, tab_name="새 탭", data=None):
        super().__init__()
        self.tab_name = tab_name
        self.data = data or []
        
        # 데이터 히스토리 관리 객체 생성
        self.data_history = DataHistory(50)
        self.history_update_in_progress = False  # 히스토리 업데이트 중 플래그
        
        # 비교 테이블 여부 플래그
        self.is_comparison_table = False
        
        # 현재 화면에 표시되는 시각화 위젯들을 추적
        self.visible_shape_widgets = {} # {row_index: ShapeWidget}
        
        # 유효성 계산 여부 추적 (최적화용)
        self.validity_calculated_rows = set()
        
        self.setup_ui()
        # 검색 디바운스 타이머
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search_filter)
        
        # 초기 데이터를 히스토리에 추가
        if self.data:
            self.data_history.add_entry(self.data, "초기 데이터")
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 상단 컨트롤 영역
        control_layout = QHBoxLayout()
        
        # 시각화 체크박스
        self.visualization_checkbox = QCheckBox(_("ui.datatab.visualize"))
        self.visualization_checkbox.setToolTip(_("ui.datatab.visualize"))
        self.visualization_checkbox.stateChanged.connect(self.on_visualization_toggled)
        control_layout.addWidget(self.visualization_checkbox)

        # 검색 라벨 + 입력
        self.search_label = QLabel(_("ui.datatab.search"))
        control_layout.addWidget(self.search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_("ui.datatab.search.placeholder"))
        try:
            self.search_input.setClearButtonEnabled(True)
        except Exception:
            pass
        self.search_input.textChanged.connect(self.on_search_text_changed)
        control_layout.addWidget(self.search_input, 1)
        
        control_layout.addStretch()  # 오른쪽으로 밀어내기
        layout.addLayout(control_layout)
        
        # 데이터 테이블
        self.data_table = DragDropTableWidget()  # from gui.widgets
        self.data_table.setColumnCount(2)
        self.data_table.setHorizontalHeaderLabels([_("ui.table.validity"), _("ui.table.shape_code")])
        # 창 크기 확장 시 유효성과 도형 코드 컬럼이 늘어나도록 설정
        self.data_table.horizontalHeader().setStretchLastSection(False)
        self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.data_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.data_table.customContextMenuRequested.connect(self.on_table_context_menu)
        self.data_table.rows_reordered.connect(self.on_data_moved)
        self.data_table.itemChanged.connect(self.on_table_item_changed)
        
        # 테이블 셀 내용을 수직 중앙 정렬
        self.data_table.setStyleSheet("""
            QTableWidget::item {
                text-align: center;
                vertical-align: middle;
            }
        """)
        
        layout.addWidget(self.data_table)
        
        # 스크롤 이벤트 연결 (수정된 부분)
        # 스크롤 쓰로틀링: 빠른 스크롤 중 중복 연산 방지
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._do_scroll_updates)

        scroll_bar = self.data_table.verticalScrollBar()
        scroll_bar.valueChanged.connect(self._on_scroll_value_changed)
        horizontal_scroll_bar = self.data_table.horizontalScrollBar()
        horizontal_scroll_bar.valueChanged.connect(self._on_scroll_value_changed)
        
        # 단축키 설정
        self.setup_shortcuts()
        
        # 버튼 레이아웃 (버튼 순서를 유연하게 재배치 가능하도록 구성)
        button_layout = QHBoxLayout()

        # 버튼 인스턴스 생성만 먼저 수행
        self.save_button = QPushButton(_("ui.btn.save"))
        self.save_button.setToolTip(_("ui.tooltip.save_auto"))
        self.save_button.clicked.connect(self.on_save_data_auto)

        self.save_as_button = QPushButton(_("ui.btn.save_as"))
        self.save_as_button.setToolTip(_("ui.tooltip.save_as"))
        self.save_as_button.clicked.connect(self.on_save_data_as)

        self.clone_button = QPushButton(_("ui.btn.clone"))
        self.clone_button.clicked.connect(self.on_clone_tab)

        self.data_undo_button = QPushButton("↶")
        self.data_undo_button.setMaximumWidth(30)
        self.data_undo_button.setToolTip(_("ui.tooltip.data_undo"))
        self.data_undo_button.clicked.connect(self.on_data_undo)
        self.data_undo_button.setEnabled(False)

        self.data_redo_button = QPushButton("↷")
        self.data_redo_button.setMaximumWidth(30)
        self.data_redo_button.setToolTip(_("ui.tooltip.data_redo"))
        self.data_redo_button.clicked.connect(self.on_data_redo)
        self.data_redo_button.setEnabled(False)

        self.clear_button = QPushButton(_("ui.btn.clear_data"))
        self.clear_button.clicked.connect(self.on_clear_data)

        # (신규 위치) 새 탭 버튼을 동일 행에 배치
        self.new_tab_button = QPushButton(_("ui.btn.add_tab"))
        # 메인 윈도우의 on_add_new_data_tab 호출
        self.new_tab_button.clicked.connect(lambda: self.get_main_window().on_add_new_data_tab() if self.get_main_window() else None)

        # 버튼 사양과 순서를 정의 (필요 시 손쉽게 순서 재배치 가능)
        button_specs = {
            "save": self.save_button,
            "save_as": self.save_as_button,
            "clone": self.clone_button,
            "undo": self.data_undo_button,
            "redo": self.data_redo_button,
            "clear": self.clear_button,
            "new_tab": self.new_tab_button,
        }
        # 기본 순서: 저장, 다른 이름으로 저장, 복제, Undo, Redo, 지우기, 새 탭
        button_order = ["save", "save_as", "clone", "undo", "redo", "clear", "new_tab"]

        for key in button_order:
            button_layout.addWidget(button_specs[key])

        button_layout.addStretch()

        # (요청사항) 비교 및 선택항목 처리 버튼 제거로 인해 더 이상 추가하지 않음

        layout.addLayout(button_layout)
        
        # 초기 데이터 업데이트
        self.update_table()

    def _on_scroll_value_changed(self, _value):
        try:
            self._scroll_timer.start(60)
        except Exception:
            self._do_scroll_updates()

    def _do_scroll_updates(self):
        # 대량 스크롤 시 잦은 재계산을 한 번으로 병합
        self._update_visible_validity()
        self._update_visible_shapes()
    
    def setup_comparison_table(self):
        """비교 결과용 3열 테이블 설정"""
        self.is_comparison_table = True
        
        # 테이블을 3열로 재구성
        self.data_table.setColumnCount(3)
        self.data_table.setHorizontalHeaderLabels(["데이터A", "데이터B", "비교결과"])
        self.data_table.horizontalHeader().setStretchLastSection(False)
        
        # 열 너비 설정
        self.data_table.setColumnWidth(0, 200)
        self.data_table.setColumnWidth(1, 200)
        self.data_table.setColumnWidth(2, 80)
        
        # 테이블 업데이트
        self.update_table()
    
    def setup_shortcuts(self):
        """단축키 설정"""
        main_window = self.get_main_window()
        if main_window:
            main_window.log_verbose("대량처리 탭 단축키 설정 중...")
        
        # Ctrl+C: 클립보드로 복사
        self.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self.copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.copy_shortcut.activated.connect(self.on_copy_to_clipboard)
        
        # Ctrl+V: 클립보드에서 붙여넣기
        self.paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        self.paste_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.paste_shortcut.activated.connect(self.on_paste_from_clipboard)
        
        # Delete: 선택된 항목 삭제
        self.delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self)
        self.delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.on_delete_selected)
        
        # 데이터 히스토리 단축키는 메인 윈도우에서 처리하므로 제거
        # (메인 윈도우의 on_undo/on_redo에서 현재 탭 상태에 따라 적절한 기능 호출)
        
        # 저장 단축키
        self.save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)  # Ctrl+S
        self.save_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.activated.connect(self.on_save_data_auto)
        
        self.save_as_shortcut = QShortcut(QKeySequence.StandardKey.SaveAs, self)  # Ctrl+Shift+S
        self.save_as_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_as_shortcut.activated.connect(self.on_save_data_as)
        
        if main_window:
            main_window.log_verbose("대량처리 탭 단축키 설정 완료 (Ctrl+C, Ctrl+V, Delete, Ctrl+S, Ctrl+Shift+S)")
    
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
                main_window.log_verbose(f"항목이 {from_row + 1}번에서 {to_row + 1}번으로 이동되었습니다.")
        else:
            pass
    
    def on_table_item_changed(self, item):
        """테이블 아이템이 변경되었을 때 호출"""
        if self.history_update_in_progress:
            return  # 히스토리 업데이트 중에는 무시
        
        row = item.row()
        column = item.column()
        
        if 0 <= row < len(self.data):
            if self.is_comparison_table:
                # 비교 테이블인 경우 3열 처리
                new_text = item.text().strip()
                
                # 현재 데이터를 탭으로 분리
                parts = self.data[row].split('\t')
                data_a = parts[0] if len(parts) > 0 else ""
                data_b = parts[1] if len(parts) > 1 else ""
                comparison = parts[2] if len(parts) > 2 else ""
                
                # 변경된 열에 따라 업데이트
                old_value = ""
                if column == 0:  # 데이터A 열
                    old_value = data_a
                    data_a = new_text
                elif column == 1:  # 데이터B 열
                    old_value = data_b
                    data_b = new_text
                elif column == 2:  # 비교결과 열
                    old_value = comparison
                    comparison = new_text
                
                # 변경사항이 있는 경우에만 처리
                if new_text != old_value:
                    # 데이터 업데이트
                    self.data[row] = f"{data_a}\t{data_b}\t{comparison}"
                    
                    # 비교 결과에 따라 색상 업데이트
                    if column == 2:  # 비교결과 열인 경우
                        if comparison == "1":
                            item.setBackground(QColor(200, 255, 200))  # 연한 초록색
                        elif comparison == "0":
                            item.setBackground(QColor(255, 200, 200))  # 연한 빨간색
                        else:
                            item.setBackground(QColor(255, 255, 255))  # 흰색
                    
                    # 히스토리에 추가
                    column_names = ["데이터A", "데이터B", "비교결과"]
                    self.add_to_data_history(f"편집 ({row + 1}번 {column_names[column]}: {old_value} → {new_text})")
                    
                    main_window = self.get_main_window()
                    if main_window:
                        main_window.log_verbose(f"{row + 1}번 {column_names[column]}이 '{old_value}'에서 '{new_text}'로 변경되었습니다.")
            else:
                # 일반 테이블인 경우 도형 코드 열(1번 열)만 처리
                if column == 1:
                    new_text = item.text().strip()
                    old_text = self.data[row]
                    
                    # 변경사항이 있는 경우에만 처리
                    if new_text != old_text:
                        # 데이터 업데이트
                        self.data[row] = new_text
                        
                        # 유효성 캐시에서 해당 행 제거하여 재계산 유도
                        self.validity_calculated_rows.discard(row)
                        
                        # 시각화 위젯이 있다면 제거하여 재계산 유도
                        if row in self.visible_shape_widgets:
                            widget = self.visible_shape_widgets.pop(row)
                            self.data_table.removeCellWidget(row, 2)
                            widget.deleteLater()
                        
                        # 변경 즉시 유효성 업데이트, 그 후 시각화 업데이트
                        self._update_visible_validity()
                        self._update_visible_shapes()

                        # 히스토리에 추가
                        self.add_to_data_history(f"편집 ({row + 1}번: {old_text} → {new_text})")
                        
                        main_window = self.get_main_window()
                        if main_window:
                            main_window.log_verbose(f"{row + 1}번 항목이 '{old_text}'에서 '{new_text}'로 변경되었습니다.")
    
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
            main_window.log_verbose(f"{len(valid_lines)}개 항목이 {insert_position + 1}번 위치에 추가되었습니다.")
    
    def update_table(self):
        """테이블 업데이트 (최적화: 구조만 만들고 계산은 동적으로 처리)"""
        # 기존 선택 상태 저장
        selected_cells = set()
        for item in self.data_table.selectedItems():
            selected_cells.add((item.row(), item.column()))
            
        # 유효성 계산 상태 초기화
        self.validity_calculated_rows.clear()
        
        # 시각화 위젯들 초기화 (데이터가 변경되었으므로)
        if self.visualization_checkbox.isChecked():
            self._clear_all_shape_widgets()
        
        self.data_table.blockSignals(True) # 시그널 일시 차단
        self.data_table.clearSelection() # 기존 선택 명시적으로 초기화 (매우 중요!)
        
        self.data_table.setRowCount(len(self.data))
        
        if self.is_comparison_table:
            # 비교 테이블인 경우 3열로 표시
            for i, data_line in enumerate(self.data):
                # 탭 구분자로 분리
                parts = data_line.split('\t')
                data_a = parts[0] if len(parts) > 0 else ""
                data_b = parts[1] if len(parts) > 1 else ""
                comparison = parts[2] if len(parts) > 2 else ""
                
                # 데이터A 열
                data_a_item = QTableWidgetItem(data_a)
                self.data_table.setItem(i, 0, data_a_item)
                
                # 데이터B 열
                data_b_item = QTableWidgetItem(data_b)
                self.data_table.setItem(i, 1, data_b_item)
                
                # 비교결과 열
                comparison_item = QTableWidgetItem(comparison)
                # 비교 결과에 따라 색상 설정
                if comparison == "1":
                    comparison_item.setBackground(QColor(200, 255, 200))  # 연한 초록색
                elif comparison == "0":
                    comparison_item.setBackground(QColor(255, 200, 200))  # 연한 빨간색
                self.data_table.setItem(i, 2, comparison_item)
        else:
            # 일반 테이블인 경우 2열로 표시
            for i, shape_code in enumerate(self.data):
                # 유효성 열: 비워둠 (동적 로딩)
                validity_item = QTableWidgetItem("")
                validity_item.setFlags(validity_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.data_table.setItem(i, 0, validity_item)
                
                # 도형 코드 열: 값만 설정
                code_item = QTableWidgetItem(shape_code)
                self.data_table.setItem(i, 1, code_item)

                # 행 높이는 시각화 상태에 따라 동적으로 설정됨 (여기서는 기본값만 설정)
                if not self.visualization_checkbox.isChecked():
                    self.data_table.setRowHeight(i, 30)

        # 컬럼 너비 조정 (유효성 컬럼을 두 배로 늘림)
        self.data_table.setColumnWidth(0, 200)  # 유효성 컬럼을 두 배로 늘림
        self.data_table.setColumnWidth(1, 300)  # 도형 코드 컬럼

        # 선택 상태 복원
        for row, col in selected_cells:
            if row < self.data_table.rowCount() and col < self.data_table.columnCount():
                item = self.data_table.item(row, col)
                if item:
                    item.setSelected(True)

        self.data_table.blockSignals(False) # 시그널 차단 해제

        # 버튼 상태 업데이트
        has_data = len(self.data) > 0
        self.clear_button.setEnabled(has_data)
        self.save_button.setEnabled(has_data)
        self.save_as_button.setEnabled(has_data)
        self.clone_button.setEnabled(has_data)
        
        # 데이터 히스토리 버튼 상태 업데이트
        self.update_data_history_buttons()
        
        # 초기 화면 업데이트는 쓰로틀 함수로 병합 실행
        QTimer.singleShot(0, self._do_scroll_updates)
        QTimer.singleShot(0, self._apply_search_filter)

    def on_search_text_changed(self, _text: str):
        """검색어 변경 시 디바운스로 필터 적용"""
        # 대량 데이터 대비 디바운스
        try:
            self._search_timer.start(120)
        except Exception:
            # 타이머 사용 불가 시 즉시 적용
            self._apply_search_filter()

    def _apply_search_filter(self):
        """검색어가 포함되는 행만 표시 (대소문자 구분)"""
        try:
            keyword = self.search_input.text().strip()
        except Exception:
            keyword = ""
        row_count = self.data_table.rowCount()
        if not keyword:
            for row in range(row_count):
                self.data_table.setRowHidden(row, False)
            return

        # 도형 매칭 기반 필터링: '_'는 와일드카드, '-'는 완전 매칭용 빈칸
        try:
            from shape import Shape
            pattern_shape, wildcard_mask = Shape.parse_pattern_with_wildcard(keyword, wildcard_char='_')
        except Exception:
            # 파싱 실패 시 전체 숨김 해제(관용적 처리)
            for row in range(row_count):
                self.data_table.setRowHidden(row, False)
            return

        def row_matches_shape_code(code: str) -> bool:
            try:
                target = Shape.from_string(code)
                return target.contains_pattern(pattern_shape, wildcard_mask=wildcard_mask, treat_empty_as_wildcard=False)
            except Exception:
                return False

        for row in range(row_count):
            if self.is_comparison_table:
                item_a = self.data_table.item(row, 0)
                item_b = self.data_table.item(row, 1)
                code_a = item_a.text() if item_a else ""
                code_b = item_b.text() if item_b else ""
                match_found = row_matches_shape_code(code_a) or row_matches_shape_code(code_b)
            else:
                item = self.data_table.item(row, 1)
                code = item.text() if item else ""
                match_found = row_matches_shape_code(code)
            self.data_table.setRowHidden(row, not match_found)
        # 필터 변경 시 선택 영역 정리: 숨겨진 행은 선택 해제
        try:
            self.data_table._prune_hidden_from_selection()
        except Exception:
            pass
        # 필터 적용 후, 보이는 영역 업데이트를 쓰로틀로 호출
        self._on_scroll_value_changed(0)
    
    def on_table_context_menu(self, position):
        """테이블 우클릭 메뉴"""
        menu = QMenu(self.data_table)
        
        # 클립보드 관련 기능들
        paste_action = menu.addAction(_("ui.ctx.paste"))
        paste_action.triggered.connect(self.on_paste_from_clipboard)
        
        if self.data_table.selectedItems():
            menu.addSeparator()
            
            # 복사 관련 기능들
            clipboard_action = menu.addAction(_("ui.ctx.copy"))
            clipboard_action.triggered.connect(self.on_copy_to_clipboard)
            
            copy_action = menu.addAction(_("ui.ctx.copy_to_input_a"))
            copy_action.triggered.connect(self.on_copy_to_input_a)
            
            menu.addSeparator()
            
            # 삭제 기능
            delete_action = menu.addAction(_("ui.ctx.delete"))
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
                    if self.is_comparison_table:
                        # 비교 테이블인 경우 이미 탭으로 구분된 데이터 사용
                        selected_codes.append(self.data[row])
                    else:
                        # 일반 테이블인 경우 기존 방식
                        selected_codes.append(self.data[row])
            
            if selected_codes:
                clipboard_text = '\n'.join(selected_codes)
                app = QApplication.instance()
                if app:
                    app.clipboard().setText(clipboard_text)
                    main_window = self.get_main_window()
                    if main_window:
                        main_window.log_verbose(f"{len(selected_codes)}개 항목이 클립보드에 복사되었습니다.")
    
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
                main_window.log_verbose(f"{len(selected_rows)}개 항목이 삭제되었습니다.")
    
    def get_main_window(self):
        """메인 윈도우 참조 가져오기"""
        widget = self
        while widget:
            if isinstance(widget, ShapezGUI):
                return widget
            widget = widget.parent()
        return None
    
    def on_save_data_auto(self):
        """현재 탭을 data/{탭제목}.txt에 자동 저장 (덮어쓰기)"""
        if not self.data:
            QMessageBox.information(self, "알림", "저장할 데이터가 없습니다.")
            return
        
        import os
        
        # data 폴더가 없으면 생성
        data_dir = "data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # 파일명에서 특수문자 제거
        safe_filename = "".join(c for c in self.tab_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        file_path = os.path.join(data_dir, f"{safe_filename}.txt")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for shape_code in self.data:
                    f.write(f"{shape_code}\n")
            
            main_window = self.get_main_window()
            if main_window:
                main_window.log(f"데이터 저장 완료: {file_path}")
                
            # 간단한 알림 (선택사항)
            QMessageBox.information(self, _("ui.msg.title.done"), _("ui.msg.saved", path=file_path))
            
        except Exception as e:
            QMessageBox.critical(self, _("ui.msg.title.error"), _("ui.msg.save_error", error=str(e)))
    
    def on_save_data_as(self):
        """데이터를 다른 이름으로 저장"""
        if not self.data:
            QMessageBox.information(self, "알림", "저장할 데이터가 없습니다.")
            return
        
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "다른 이름으로 저장",
            f"data/{self.tab_name}.txt",
            "텍스트 파일 (*.txt);;모든 파일 (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for shape_code in self.data:
                        f.write(f"{shape_code}\n")
                QMessageBox.information(self, _("ui.msg.title.done"), _("ui.msg.saved", path=file_path))
                main_window = self.get_main_window()
                if main_window:
                    main_window.log_verbose(f"다른 이름으로 저장 완료: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, _("ui.msg.title.error"), _("ui.msg.save_error", error=str(e)))
    
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
                main_window.log_verbose(f"탭 '{self.tab_name}' 데이터가 지워졌습니다.")
    
    def on_compare_data(self):
        """현재 탭과 다음 탭의 데이터를 비교"""
        main_window = self.get_main_window()
        if not main_window:
            return
        
        # 현재 탭 인덱스 찾기
        current_index = -1
        for i in range(main_window.data_tabs.count()):
            if main_window.data_tabs.widget(i) == self:
                current_index = i
                break
        
        if current_index == -1:
            QMessageBox.warning(self, "오류", "현재 탭을 찾을 수 없습니다.")
            return
        
        # 다음 탭 확인
        next_index = current_index + 1
        if next_index >= main_window.data_tabs.count():
            QMessageBox.information(self, "알림", "비교할 다음 탭이 없습니다.")
            return
        
        next_tab = main_window.data_tabs.widget(next_index)
        if not next_tab:
            QMessageBox.warning(self, "오류", "다음 탭을 찾을 수 없습니다.")
            return
        
        # 데이터 비교
        current_data = self.data
        next_data = next_tab.data
        
        if not current_data and not next_data:
            QMessageBox.information(self, "알림", "비교할 데이터가 없습니다.")
            return
        
        # 비교 결과 저장
        comparison_results = []
        same_count = 0
        diff_count = 0
        
        max_length = max(len(current_data), len(next_data))
        
        for i in range(max_length):
            current_item = current_data[i] if i < len(current_data) else ""
            next_item = next_data[i] if i < len(next_data) else ""
            
            is_same = current_item == next_item
            comparison_value = "1" if is_same else "0"
            
            if is_same:
                same_count += 1
            else:
                diff_count += 1
            
            # 결과 데이터 생성 (현재 탭 데이터, 다음 탭 데이터, 비교 결과)
            comparison_results.append(f"{current_item}\t{next_item}\t{comparison_value}")
        
        # 로그 출력
        main_window.log(f"데이터 비교 완료: 같음 {same_count}개, 다름 {diff_count}개")
        main_window.log_verbose(f"'{self.tab_name}' 탭과 '{next_tab.tab_name}' 탭 비교 결과:")
        
        # 상세 비교 결과 로그 (상세 로그로만 출력)
        for i, result in enumerate(comparison_results[:10]):  # 처음 10개만 로그로 출력
            parts = result.split('\t')
            current_item, next_item, comparison = parts[0], parts[1], parts[2]
            if comparison == "0":  # 다른 경우만 상세 로그로 출력
                main_window.log_verbose(f"[{i}] '{current_item}' ≠ '{next_item}'")
        
        if len(comparison_results) > 10:
            main_window.log_verbose(f"... 외 {len(comparison_results) - 10}개")
        
        # 새 데이터 탭 생성
        new_tab_name = f"비교결과_{self.tab_name}_vs_{next_tab.tab_name}"
        new_tab = main_window.add_data_tab(new_tab_name, comparison_results)
        
        # 비교 결과 탭을 3열 구조로 설정
        if new_tab:
            new_tab.setup_comparison_table()
        
        main_window.log(f"비교 결과가 새 탭 '{new_tab_name}'에 저장되었습니다.")
    
    def on_process_selected(self):
        """(제거됨) 선택된 항목 처리 버튼 제거에 따라 사용되지 않음"""
        pass

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
            
            main_window.log_verbose(f"탭 '{self.tab_name}'이 '{clone_tab_name}'로 복제되었습니다. ({len(cloned_data)}개 항목)")
        else:
            QMessageBox.warning(self, "오류", "메인 윈도우를 찾을 수 없습니다.")

    def on_data_undo(self):
        """데이터 Undo"""
        main_window = self.get_main_window()
        if main_window:
            main_window.log_verbose("Ctrl+Z 단축키가 실행되었습니다.")
        
        entry = self.data_history.undo()
        if entry is not None:
            data, operation_name = entry
            self.history_update_in_progress = True
            self.data = data.copy()
            self.update_table()
            self.history_update_in_progress = False
            
            if main_window:
                main_window.log_verbose(f"데이터 Undo 완료: {operation_name}")
        else:
            if main_window:
                main_window.log_verbose("되돌릴 작업이 없습니다.")
    
    def on_data_redo(self):
        """데이터 Redo"""
        main_window = self.get_main_window()
        if main_window:
            main_window.log_verbose("Ctrl+Y (또는 Ctrl+Shift+Z) 단축키가 실행되었습니다.")
        
        entry = self.data_history.redo()
        if entry is not None:
            data, operation_name = entry
            self.history_update_in_progress = True
            self.data = data.copy()
            self.update_table()
            self.history_update_in_progress = False
            
            if main_window:
                main_window.log_verbose(f"데이터 Redo 완료: {operation_name}")
        else:
            if main_window:
                main_window.log_verbose("다시실행할 작업이 없습니다.")
    
    def add_to_data_history(self, operation_name=""):
        """현재 데이터 상태를 히스토리에 추가"""
        if not self.history_update_in_progress:
            self.data_history.add_entry(self.data, operation_name)
            self.update_data_history_buttons()

    def update_data_history_buttons(self):
        """데이터 히스토리 버튼 상태 업데이트"""
        self.data_undo_button.setEnabled(self.data_history.can_undo())
        self.data_redo_button.setEnabled(self.data_history.can_redo())
    
    def on_visualization_toggled(self, state):
        """도형 시각화 체크박스 상태 변경 시 호출"""
        if state == Qt.CheckState.Checked.value: # 체크됨
            if self.data_table.columnCount() == 2:
                self.data_table.setColumnCount(3)
                self.data_table.setHorizontalHeaderLabels(["유효성", "도형 코드", "시각화"])
                # 시각화 컬럼도 마우스로 조절 가능하도록 설정
                self.data_table.setColumnWidth(2, 160)
                # 창 크기 확장 시 유효성과 도형 코드 컬럼이 늘어나도록 설정
                self.data_table.horizontalHeader().setStretchLastSection(False)
                self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
                self.data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
                self.data_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            # 시각화가 켜지면 모든 행 높이를 도형에 맞게 조정
            self._update_all_row_heights()
            self._update_visible_shapes() # 시각화 위젯만 다시 그림
        else: # 체크 해제됨
            self._clear_all_shape_widgets() # 모든 시각화 위젯 제거
            if self.data_table.columnCount() == 3:
                self.data_table.setColumnCount(2)
                self.data_table.setHorizontalHeaderLabels([_("ui.table.validity"), _("ui.table.shape_code")])
                # 창 크기 확장 시 유효성과 도형 코드 컬럼이 늘어나도록 설정
                self.data_table.horizontalHeader().setStretchLastSection(False)
                self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
                self.data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            # 시각화가 꺼지면 모든 행 높이를 기본값으로 재설정
            for i in range(self.data_table.rowCount()):
                self.data_table.setRowHeight(i, 30)
    


    def _update_visible_validity(self):
        """현재 뷰포트에 보이는 행의 유효성만 동적으로 계산합니다."""
        if self.is_comparison_table: return

        # 보이는 행 범위 계산 (숨겨진 행은 건너뜀)
        viewport_rect = self.data_table.viewport().rect()
        first = self.data_table.indexAt(viewport_rect.topLeft()).row()
        last = self.data_table.indexAt(viewport_rect.bottomRight()).row()
        if first == -1: first = 0
        if last == -1: last = self.data_table.rowCount() - 1
        if last < 0: return
        
        # 더 많은 행을 표시하도록 범위 확장 (최대 20개까지)
        buffer_rows = 10  # 위아래로 10개씩 추가
        first = max(0, first - buffer_rows)
        last = min(self.data_table.rowCount() - 1, last + buffer_rows)

        # 보이는 행에 대해서만 유효성 계산
        for row in range(first, last + 1):
            if self.data_table.isRowHidden(row):
                continue
            if row not in self.validity_calculated_rows:
                shape_code = self.data_table.item(row, 1).text()
                validity_item = self.data_table.item(row, 0)
                code_item = self.data_table.item(row, 1)

                is_impossible = False
                try:
                    if shape_code.strip():
                        from shape import Shape
                        shape = Shape.from_string(shape_code.strip())
                        res, reason = shape.classifier()
                        validity_item.setText(f"{_(res)} ({_(reason)})")
                        is_impossible = res == "불가능형"
                    else:
                        validity_item.setText(_("enum.shape_type.empty") + " (" + _("analyzer.empty") + ")")
                except Exception as e:
                    validity_item.setText(_("ui.table.error", error=str(e)))

                # 배경색 설정
                bg_color = QColor(240, 240, 240) if is_impossible else QColor(255, 255, 255)
                validity_item.setBackground(bg_color)
                code_item.setBackground(bg_color)
                
                self.validity_calculated_rows.add(row)

    def _update_visible_shapes(self):
        """현재 뷰포트에 보이는 행의 시각화 위젯만 관리합니다."""
        # 시각화가 꺼져 있거나, 비교 테이블 모드이면 아무것도 하지 않음
        if not self.visualization_checkbox.isChecked() or self.is_comparison_table:
            self._clear_all_shape_widgets()
            return

        # 보이는 행 범위 계산 (숨겨진 행은 제외)
        viewport_rect = self.data_table.viewport().rect()
        first = self.data_table.indexAt(viewport_rect.topLeft()).row()
        last = self.data_table.indexAt(viewport_rect.bottomRight()).row()
        if first == -1: first = 0
        if last == -1: last = self.data_table.rowCount() - 1
        if last < 0: return
        
        # 더 많은 행을 표시하도록 범위 확장 (최대 20개까지)
        buffer_rows = 10  # 위아래로 10개씩 추가
        start_row = max(0, first - buffer_rows)
        end_row = min(self.data_table.rowCount() - 1, last + buffer_rows)
        needed_rows = {r for r in range(start_row, end_row + 1) if not self.data_table.isRowHidden(r)}
        
        # 화면 밖 위젯 제거 (안전하게 처리)
        rows_to_remove = set(self.visible_shape_widgets.keys()) - needed_rows
        for row in rows_to_remove:
            widget = self.visible_shape_widgets.pop(row)
            try:
                self.data_table.removeCellWidget(row, 2)
                if widget and not widget.isHidden():
                    widget.deleteLater()
            except RuntimeError:
                # 이미 삭제된 위젯인 경우 무시
                pass
            
        # 기존 위젯들도 모두 제거 (데이터가 변경되었을 수 있으므로)
        for row in list(self.visible_shape_widgets.keys()):
            if row not in needed_rows:
                widget = self.visible_shape_widgets.pop(row)
                try:
                    self.data_table.removeCellWidget(row, 2)
                    if widget and not widget.isHidden():
                        widget.deleteLater()
                except RuntimeError:
                    pass
            
        # 화면 안 위젯 추가/업데이트 (기존 위젯도 새로 생성)
        for row in needed_rows:
            # 기존 위젯이 있으면 제거
            if row in self.visible_shape_widgets:
                old_widget = self.visible_shape_widgets.pop(row)
                try:
                    self.data_table.removeCellWidget(row, 2)
                    if old_widget and not old_widget.isHidden():
                        old_widget.deleteLater()
                except RuntimeError:
                    pass
            
            shape_code = self.data_table.item(row, 1).text()
            # 배경색은 이미 유효성 검사에서 설정되었으므로 가져와서 사용
            is_impossible = self.data_table.item(row, 0).background().color() == QColor(240, 240, 240)
            
            shape_widget = None
            try:
                if shape_code.strip():
                    from shape import Shape
                    shape = Shape.from_string(shape_code.strip())
                    
                    # 컴팩트한 컨테이너 생성
                    container = QFrame()
                    container.setFrameShape(QFrame.Shape.NoFrame)
                    container.setContentsMargins(0, 0, 0, 0)
                    
                    # 수직 레이아웃으로 중앙 정렬
                    container_layout = QVBoxLayout(container)
                    container_layout.setContentsMargins(0, 0, 0, 0)
                    container_layout.setSpacing(0)
                    container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    # ShapeWidget 생성 (행열버튼 포함)
                    # 행 편집을 위해 handler=self, input_name=f"D{row}" 전달
                    shape_widget = ShapeWidget(shape, compact=True, handler=self, input_name=f"D{row}")
                    bg_color_str = "rgb(240, 240, 240)" if is_impossible else "white"
                    shape_widget.setStyleSheet(f"background-color: {bg_color_str}; border: none;")
                    
                    # 컨테이너에 ShapeWidget 추가
                    container_layout.addWidget(shape_widget)
                    
                    layer_count = len(shape.layers)
                    self.data_table.setRowHeight(row, max(30, 20 + layer_count * 30))
                else:
                    self.data_table.setRowHeight(row, 30)
            except Exception:
                self.data_table.setRowHeight(row, 30)

            if shape_widget:
                # 컨테이너를 테이블 셀에 추가
                self.data_table.setCellWidget(row, 2, container)
                self.visible_shape_widgets[row] = container

    def _update_all_row_heights(self):
        """시각화가 켜져 있을 때 모든 행의 높이를 도형 레이어 수에 맞게 조정합니다."""
        if not self.visualization_checkbox.isChecked() or self.is_comparison_table:
            return
            
        for row in range(self.data_table.rowCount()):
            try:
                shape_code = self.data_table.item(row, 1).text()
                if shape_code.strip():
                    from shape import Shape
                    shape = Shape.from_string(shape_code.strip())
                    layer_count = len(shape.layers)
                    self.data_table.setRowHeight(row, max(30, 20 + layer_count * 30))
                else:
                    self.data_table.setRowHeight(row, 30)
            except Exception:
                self.data_table.setRowHeight(row, 30)

    def _clear_all_shape_widgets(self):
        """모든 시각화 위젯을 테이블에서 제거합니다."""
        for row, widget in list(self.visible_shape_widgets.items()):
            try:
                self.data_table.removeCellWidget(row, 2)
                if widget and not widget.isHidden():
                    widget.deleteLater()
            except RuntimeError:
                # 이미 삭제된 위젯인 경우 무시
                pass
        self.visible_shape_widgets.clear()
        # 모든 행 높이를 기본으로 재설정
        for i in range(self.data_table.rowCount()):
            self.data_table.setRowHeight(i, 30)

    # ===== 대량처리 시각화 편집 핸들러 (분석도구와 동일 인터페이스) =====
    def _parse_shape_or_none(self, text: str):
        text = (text or "").strip()
        if not text:
            return None
        try:
            from shape import Shape
            return Shape.from_string(text)
        except Exception:
            return None

    def _row_to_input_name(self, row: int) -> str:
        return f"D{row}"

    def _input_name_to_row(self, input_name: str) -> int:
        # expects format D{row}
        try:
            if input_name and input_name.startswith("D"):
                return int(input_name[1:])
        except Exception:
            pass
        return -1

    def _update_row_code(self, row: int, new_shape_repr: str):
        if 0 <= row < len(self.data):
            self.data[row] = new_shape_repr
            # 테이블 셀 갱신
            item = self.data_table.item(row, 1)
            if item:
                item.setText(new_shape_repr)
            # 캐시 무효화 및 시각화 재생성 유도
            self.validity_calculated_rows.discard(row)
            if row in self.visible_shape_widgets:
                widget = self.visible_shape_widgets.pop(row)
                self.data_table.removeCellWidget(row, 2)
                widget.deleteLater()
            self._update_visible_validity()
            self._update_visible_shapes()
            # 히스토리
            self.add_to_data_history(_("ui.history.edit_visual"))

    def handle_quadrant_drop(self, src_input_name, src_layer, src_quad, tgt_input_name, tgt_layer, tgt_quad):
        src_row = self._input_name_to_row(src_input_name)
        tgt_row = self._input_name_to_row(tgt_input_name)
        if src_row < 0 or tgt_row < 0:
            return
        src_shape = self._parse_shape_or_none(self.data[src_row])
        tgt_shape = self._parse_shape_or_none(self.data[tgt_row]) if src_row != tgt_row else src_shape
        if src_shape is None or tgt_shape is None:
            return
        max_layers = max(len(src_shape.layers), len(tgt_shape.layers), src_layer + 1, tgt_layer + 1)
        src_shape.pad_layers(max_layers)
        tgt_shape.pad_layers(max_layers)
        src_q = src_shape.layers[src_layer].quadrants[src_quad]
        tgt_q = tgt_shape.layers[tgt_layer].quadrants[tgt_quad]
        src_shape.layers[src_layer].quadrants[src_quad] = tgt_q
        tgt_shape.layers[tgt_layer].quadrants[tgt_quad] = src_q
        self._update_row_code(src_row, repr(src_shape))
        if src_row != tgt_row:
            self._update_row_code(tgt_row, repr(tgt_shape))

    def handle_row_drop(self, src_input_name, src_layer_idx, tgt_input_name, tgt_layer_idx):
        src_row = self._input_name_to_row(src_input_name)
        tgt_row = self._input_name_to_row(tgt_input_name)
        if src_row < 0 or tgt_row < 0:
            return
        shape = self._parse_shape_or_none(self.data[src_row])
        if shape is None:
            return
        max_layers = max(len(shape.layers), src_layer_idx + 1, tgt_layer_idx + 1)
        shape.pad_layers(max_layers)
        moved_layer = shape.layers.pop(src_layer_idx)
        shape.layers.insert(tgt_layer_idx, moved_layer)
        self._update_row_code(src_row, repr(shape))

    def handle_column_drop(self, src_input_name, src_quad_idx, tgt_input_name, tgt_quad_idx):
        # 동일 행에서만 의미 있음
        if src_input_name != tgt_input_name:
            return
        row = self._input_name_to_row(src_input_name)
        if row < 0:
            return
        shape = self._parse_shape_or_none(self.data[row])
        if shape is None:
            return
        for layer in shape.layers:
            q = layer.quadrants[src_quad_idx]
            layer.quadrants[src_quad_idx] = layer.quadrants[tgt_quad_idx]
            layer.quadrants[tgt_quad_idx] = q
        self._update_row_code(row, repr(shape))

    def handle_quadrant_change(self, input_name, layer_index, quad_index, new_quadrant):
        row = self._input_name_to_row(input_name)
        if row < 0:
            return
        shape = self._parse_shape_or_none(self.data[row])
        if shape is None:
            return
        max_layers = max(len(shape.layers), layer_index + 1)
        shape.pad_layers(max_layers)
        shape.layers[layer_index].quadrants[quad_index] = new_quadrant
        self._update_row_code(row, repr(shape))

    
            
        current_item = self.test_cases_list.currentItem()
        if current_item is None:
            return
        category, test = current_item.data(Qt.ItemDataRole.UserRole)
        
        # 카테고리 설정
        index = self.category_combo.findText(category)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        
        # 필드들 설정
        self.test_name_edit.setText(test.get("name", ""))
        
        operation = test.get("operation", "")
        index = self.operation_combo.findText(operation)
        if index >= 0:
            self.operation_combo.setCurrentIndex(index)
        else:
            # 연산이 목록에 없으면 첫 번째 항목으로 설정
            self.operation_combo.setCurrentIndex(0)
        
        self.input_a_edit.setText(test.get("input_a", ""))
        self.input_b_edit.setText(test.get("input_b", ""))
        self.expected_a_edit.setText(test.get("expected_a", ""))
        self.expected_b_edit.setText(test.get("expected_b", ""))
        
        # 매개변수 JSON 문자열로 변환
        params = test.get("params", {})
        if params:
            self.params_edit.setText(json.dumps(params, ensure_ascii=False))
        else:
            self.params_edit.clear()
        
        # 연산에 따른 필드 상태 업데이트
        self.on_operation_changed(self.operation_combo.currentText())

    def update_test_case(self):
        """선택된 테스트 케이스를 업데이트합니다."""
        current_item = self.test_cases_list.currentItem()
        if not current_item:
            return
            
        category, test = current_item.data(Qt.ItemDataRole.UserRole)
        
        # 필드 값들 가져오기
        test["name"] = self.test_name_edit.text()
        test["operation"] = self.operation_combo.currentText()
        test["input_a"] = self.input_a_edit.text()
        test["input_b"] = self.input_b_edit.text()
        test["expected_a"] = self.expected_a_edit.text()
        test["expected_b"] = self.expected_b_edit.text()
        
        # 매개변수 파싱
        params_text = self.params_edit.text().strip()
        if params_text:
            try:
                test["params"] = json.loads(params_text)
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, _("ui.msg.title.warning"), 
                                  _("ui.msg.invalid_json", error=str(e)))
                return
        else:
            test["params"] = {}
        
        # 카테고리 변경 처리
        new_category = self.category_combo.currentText()
        if new_category != category:
            # 기존 카테고리에서 제거
            self.test_data[category].remove(test)
            if not self.test_data[category]:  # 빈 카테고리 제거
                del self.test_data[category]
                index = self.category_combo.findText(category)
                if index >= 0:
                    self.category_combo.removeItem(index)
            
            # 새 카테고리에 추가
            if new_category not in self.test_data:
                self.test_data[new_category] = []
                self.category_combo.addItem(new_category)
            self.test_data[new_category].append(test)
        
        # 목록 새로고침
        self.refresh_test_cases_list()
        
        # 업데이트된 항목 선택
        for i in range(self.test_cases_list.count()):
            item = self.test_cases_list.item(i)
            item_category, item_test = item.data(Qt.ItemDataRole.UserRole)
            if item_test == test:
                self.test_cases_list.setCurrentItem(item)
                break
        
        self.log(f"테스트 케이스 '{test['name']}'을(를) 업데이트했습니다.")

    def delete_test_case(self):
        """선택된 테스트 케이스를 삭제합니다."""
        current_item = self.test_cases_list.currentItem()
        if not current_item:
            return
            
        reply = QMessageBox.question(self, _("ui.msg.title.warning"), 
                                   _("ui.msg.confirm_delete"),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            category, test = current_item.data(Qt.ItemDataRole.UserRole)
            self.test_data[category].remove(test)
            
            # 빈 카테고리 제거
            if not self.test_data[category]:
                del self.test_data[category]
                index = self.category_combo.findText(category)
                if index >= 0:
                    self.category_combo.removeItem(index)
            
            self.refresh_test_cases_list()
            
            # 편집 필드 초기화
            self.clear_test_edit_fields()
            
            self.log(f"테스트 케이스 '{test.get('name', 'Unnamed')}'을(를) 삭제했습니다.")

    def move_test_case_up(self):
        """테스트 케이스를 위로 이동합니다."""
        current_item = self.test_cases_list.currentItem()
        if not current_item:
            return
            
        current_row = self.test_cases_list.row(current_item)
        if current_row <= 0:
            return
            
        category, test = current_item.data(Qt.ItemDataRole.UserRole)
        tests = self.test_data[category]
        
        # 리스트에서 위치 교환
        test_index = tests.index(test)
        if test_index > 0:
            tests[test_index], tests[test_index - 1] = tests[test_index - 1], tests[test_index]
            self.refresh_test_cases_list()
            
            # 이동된 항목 선택
            new_item = self.test_cases_list.item(current_row - 1)
            if new_item:
                self.test_cases_list.setCurrentItem(new_item)
            
            self.log(f"테스트 케이스 '{test.get('name', 'Unnamed')}'을(를) 위로 이동했습니다.")

    def move_test_case_down(self):
        """테스트 케이스를 아래로 이동합니다."""
        current_item = self.test_cases_list.currentItem()
        if not current_item:
            return
            
        current_row = self.test_cases_list.row(current_item)
        if current_row >= self.test_cases_list.count() - 1:
            return
            
        category, test = current_item.data(Qt.ItemDataRole.UserRole)
        tests = self.test_data[category]
        
        # 리스트에서 위치 교환
        test_index = tests.index(test)
        if test_index < len(tests) - 1:
            tests[test_index], tests[test_index + 1] = tests[test_index + 1], tests[test_index]
            self.refresh_test_cases_list()
            
            # 이동된 항목 선택
            new_item = self.test_cases_list.item(current_row + 1)
            if new_item:
                self.test_cases_list.setCurrentItem(new_item)
            
            self.log(f"테스트 케이스 '{test.get('name', 'Unnamed')}'을(를) 아래로 이동했습니다.")

    def clear_test_edit_fields(self):
        """테스트 편집 필드들을 초기화합니다."""
        self.test_name_edit.clear()
        self.operation_combo.setCurrentIndex(0)
        self.input_a_edit.clear()
        self.input_b_edit.clear()
        self.expected_a_edit.clear()
        self.expected_b_edit.clear()
        self.params_edit.clear()
        
        # 연산에 따른 필드 상태 업데이트
        self.on_operation_changed(self.operation_combo.currentText())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 스태커 아이콘을 프로그램 아이콘으로 설정
    stacker_icon = load_icon_pixmap("stacker.png", 32)
    if stacker_icon:
        app.setWindowIcon(QIcon(stacker_icon))
    
    ex = ShapezGUI()
    ex.show()
    sys.exit(app.exec()) 