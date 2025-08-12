from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QLabel, QComboBox, QLineEdit, QGridLayout, QTableWidget, QPushButton
from i18n import _


def build_test_editor_tab(main_window) -> QWidget:
    """
    테스트 편집기 탭 UI를 구성하고, main_window에 필요한 위젯 레퍼런스를 설정합니다.
    주의: 기존 위젯 및 테이블 초기화가 main_window에 구현되어 있어야 합니다.
    반환값: 탭으로 추가할 QWidget
    """
    test_editor_tab_widget = QWidget()
    test_editor_tab_layout = QVBoxLayout(test_editor_tab_widget)

    # 자동 테스트 컨테이너 (맨 위)
    auto_test_group = QGroupBox(_("ui.groups.auto_test"))
    auto_test_layout = QVBoxLayout(auto_test_group)

    # 전체 테스트 실행 버튼
    run_all_tests_btn = QPushButton(_("ui.btn.run_all_tests"))
    run_all_tests_btn.clicked.connect(main_window.run_forward_tests)
    auto_test_layout.addWidget(run_all_tests_btn)

    # 역연산 테스트 실행 버튼
    run_reverse_tests_btn = QPushButton(_("ui.btn.run_reverse_tests"))
    run_reverse_tests_btn.clicked.connect(main_window.run_reverse_tests)
    auto_test_layout.addWidget(run_reverse_tests_btn)

    test_editor_tab_layout.addWidget(auto_test_group)

    # 테스트 케이스 편집기 그룹 (세부 내용은 main_window 구성을 사용)
    test_editor_group = QGroupBox(_("ui.groups.test_editor"))
    test_editor_layout = QVBoxLayout(test_editor_group)
    test_editor_tab_layout.addWidget(test_editor_group)

    return test_editor_tab_widget
