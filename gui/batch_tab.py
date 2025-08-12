from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton
from i18n import _


def build_batch_tab(main_window) -> QWidget:
    """
    대량처리 탭 UI를 구성하고, main_window에 필요한 위젯 레퍼런스를 설정합니다.
    반환값: 탭으로 추가할 QWidget
    """
    batch_tab_widget = QWidget()
    batch_layout = QVBoxLayout(batch_tab_widget)

    # 파일 선택 그룹
    file_group = QGroupBox(_("파일 선택"))
    file_layout = QVBoxLayout(file_group)

    # 파일 선택 행
    file_select_layout = QHBoxLayout()
    main_window.file_path_label = QLabel(_("선택된 파일 없음"))
    main_window.file_path_label.setStyleSheet("color: #666; font-style: italic;")
    file_select_layout.addWidget(QLabel(_("파일:")))
    file_select_layout.addWidget(main_window.file_path_label, 1)

    main_window.browse_button = QPushButton(_("찾아보기"))
    main_window.browse_button.clicked.connect(main_window.on_browse_file)
    file_select_layout.addWidget(main_window.browse_button)

    file_layout.addLayout(file_select_layout)
    batch_layout.addWidget(file_group)

    # 데이터 탭 위젯 (CustomTabWidget은 main_window에서 보유)
    data_group = QGroupBox(_("데이터"))
    data_layout = QVBoxLayout(data_group)

    data_layout.addWidget(main_window.data_tabs)
    batch_layout.addWidget(data_group)

    return batch_tab_widget
