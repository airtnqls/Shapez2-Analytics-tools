from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QListWidget, QLabel, QScrollArea
from PyQt6.QtCore import Qt
from i18n import _


def build_analysis_tab(main_window) -> QWidget:
    """
    분석 도구 탭 UI를 구성하고, main_window에 필요한 위젯 레퍼런스를 설정합니다.
    반환값: 탭으로 추가할 QWidget
    """
    analysis_tab_widget = QWidget()
    right_panel = QVBoxLayout(analysis_tab_widget)

    # 기원 역추적 그룹
    reverse_group = QGroupBox(_("기원 역추적"))
    reverse_group.setMinimumHeight(150)
    reverse_group.setMaximumHeight(250)
    reverse_layout = QVBoxLayout(reverse_group)

    main_window.reverse_input = QLineEdit("P-P-P-P-:CuCuCuCu")
    main_window.reverse_input.setObjectName("역추적 입력")
    reverse_layout.addWidget(QLabel(_("목표 도형:")))
    reverse_layout.addWidget(main_window.reverse_input)

    find_origin_hbox = QHBoxLayout()
    find_origin_hbox.addWidget(QPushButton(_("기원 찾기 (규칙)"), clicked=main_window.on_find_origin))
    copy_button = QPushButton(_("전체 복사"))
    copy_button.clicked.connect(main_window.on_copy_origins)
    find_origin_hbox.addWidget(copy_button)
    reverse_layout.addLayout(find_origin_hbox)

    main_window.origin_list = QListWidget()
    main_window.origin_list.itemClicked.connect(main_window.on_origin_selected)
    reverse_layout.addWidget(QLabel(_("발견된 모든 후보:")))
    reverse_layout.addWidget(main_window.origin_list)
    right_panel.addWidget(reverse_group)

    # 출력 (분석도구 탭 하단)
    output_group = QGroupBox(_("출력"))
    output_vbox = QVBoxLayout(output_group)
    main_window.scroll_area = QScrollArea()
    main_window.scroll_area.setWidgetResizable(True)
    main_window.output_widget = QWidget()
    main_window.output_layout = QHBoxLayout(main_window.output_widget)
    main_window.output_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    main_window.scroll_area.setWidget(main_window.output_widget)
    output_vbox.addWidget(main_window.scroll_area)
    right_panel.addWidget(output_group)

    return analysis_tab_widget
