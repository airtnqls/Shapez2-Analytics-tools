from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QPushButton, QGraphicsScene
from i18n import _


def build_process_tree_tab(main_window) -> QWidget:
    """
    공정트리 탭 UI를 구성하고, main_window에 필요한 위젯 레퍼런스를 설정합니다.
    반환값: 탭으로 추가할 QWidget
    """
    process_tree_tab_widget = QWidget()
    process_tree_layout = QVBoxLayout(process_tree_tab_widget)

    # 입력 그룹
    tree_input_group = QGroupBox(_("공정 트리 분석"))
    tree_input_layout = QVBoxLayout(tree_input_group)

    # 분석 버튼
    analyze_button = QPushButton(_("공정 트리 생성"))
    analyze_button.clicked.connect(main_window.on_generate_process_tree)
    tree_input_layout.addWidget(analyze_button)

    process_tree_layout.addWidget(tree_input_group)

    # 트리 표시 영역
    tree_display_group = QGroupBox(_("공정 트리"))
    tree_display_layout = QVBoxLayout(tree_display_group)

    # QGraphicsView/Scene은 main_window에서 제공
    if getattr(main_window, "tree_graphics_view", None) is None:
        main_window.tree_graphics_view = main_window._create_tree_view()
    main_window.tree_graphics_view.setMinimumHeight(400)
    main_window.tree_graphics_view.setDragMode(main_window.tree_graphics_view.DragMode.ScrollHandDrag)
    main_window.tree_graphics_view.setRenderHint(main_window.tree_graphics_view.renderHints())

    main_window.tree_scene = QGraphicsScene()
    main_window.tree_graphics_view.setScene(main_window.tree_scene)

    tree_display_layout.addWidget(main_window.tree_graphics_view)
    process_tree_layout.addWidget(tree_display_group)

    return process_tree_tab_widget
