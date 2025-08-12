import os
import importlib.util
from typing import Optional, List
from PyQt6.QtWidgets import (
    QApplication, QTabWidget, QWidget, QFrame, QTextEdit, QLabel, QGridLayout, QTableWidget,
    QHeaderView, QSizePolicy, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QLineEdit,
    QTableWidgetItem, QMenu, QMessageBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPoint, QMimeData
from PyQt6.QtGui import QPixmap, QFont, QColor, QKeySequence, QShortcut, QDrag
from shape import Quadrant, Shape
from i18n import _

# 공통 색상 매핑 (루트 main.py와 동일 매핑 유지)
COLOR_MAP = {'r':'#E33','g':'#3E3','b':'#33E','m':'#E3E','c':'#3EE','y':'#EE3','u':'#BBB','w':'#FFF','C':'#CDD','P':'#999'}

class QuadrantWidget(QLabel):
    def __init__(self, quadrant: Optional[Quadrant], compact=False, layer_index=None, quad_index=None, input_name=None, handler=None):
        super().__init__()
        self.setFixedSize(30, 30)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layer_index = layer_index
        self.quad_index = quad_index
        self.input_name = input_name
        self.handler = handler
        self.quadrant = quadrant
        font = QFont("맑은 고딕", 12)
        font.setBold(True)
        if quadrant and quadrant.shape == 'c':
            font_c = QFont("Consolas", 15)
            font_c.setBold(True)
            self.setFont(font_c)
        else:
            self.setFont(font)
        if quadrant:
            if quadrant.shape == 'c':
                base_color = QColor(COLOR_MAP['C'])
                paint_color = QColor(COLOR_MAP.get(quadrant.color, '#FFF'))
                self.setStyleSheet(f"""
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, 
                        stop:0 {base_color.name()}, stop:0.5 {base_color.name()}, stop:0.51 {paint_color.name()}, stop:1 {paint_color.name()});
                    color: black; border: 1px solid #555; border-radius: 0px;
                """)
                self.setText('c')
            elif quadrant.shape == 'P':
                color_code = QColor(COLOR_MAP['P'])
                self.setStyleSheet(f"background-color: {color_code.name()}; color: black; border: 1px solid #555; border-radius: 0px;")
                self.setText(quadrant.shape.upper())
            else:
                color_code = QColor(COLOR_MAP.get(quadrant.color, '#FFF'))
                self.setStyleSheet(f"background-color: {color_code.name()}; color: black; border: 1px solid #555; border-radius: 0px;")
                self.setText(quadrant.shape.upper())
        else:
            self.setStyleSheet("background-color: #333; border: 1px solid #555; border-radius: 0px;")


class RowHeaderWidget(QLabel):
    def __init__(self, layer_index, input_name):
        super().__init__("")
        self.layer_index = layer_index
        self.input_name = input_name
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(8, 30)
        self.setStyleSheet("background-color: #AAAAAA; border: 1px solid #777777; border-radius: 0px;")


class ColumnHeaderWidget(QLabel):
    def __init__(self, quad_index, input_name):
        super().__init__("")
        self.quad_index = quad_index
        self.input_name = input_name
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(30, 8)
        self.setStyleSheet("background-color: #AAAAAA; color: white; border: 1px solid #777777; border-radius: 0px;")


class ShapeWidget(QFrame):
    def __init__(self, shape: Shape, compact=False, title=None, handler=None, input_name: Optional[str]=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.shape = shape
        self.title = title
        self.handler = handler
        self.setAcceptDrops(True)
        grid_layout = QGridLayout(self)
        grid_layout.setSpacing(0)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(grid_layout)
        if title:
            title_label = QLabel(f"<b>{title}</b>")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setContentsMargins(0, 0, 0, 4)
            grid_layout.addWidget(title_label, 0, 0, 1, 6)
        clean_shape = shape.copy()
        while len(clean_shape.layers) > 0 and clean_shape.layers[-1].is_empty():
            clean_shape.layers.pop()
        if not clean_shape.layers:
            grid_layout.addWidget(QLabel("완전히 파괴됨"), 2, 1)
            return
        input_name = input_name
        show_headers = input_name is not None
        if not show_headers and self.title and self.title.startswith("입력"):
            input_name = self.title.split(" ")[1]
            show_headers = True
        if show_headers:
            for j in range(4):
                grid_layout.addWidget(ColumnHeaderWidget(j, input_name), 1, j + 1)
        num_layers = len(clean_shape.layers)
        start_row = 2 if show_headers else 1
        for i, layer in enumerate(reversed(clean_shape.layers)):
            row_pos = i + start_row
            if show_headers:
                grid_layout.addWidget(RowHeaderWidget(num_layers - 1 - i, input_name), row_pos, 0)
            for j in range(4):
                grid_layout.addWidget(QuadrantWidget(
                    layer.quadrants[j],
                    compact=compact,
                    layer_index=num_layers - 1 - i,
                    quad_index=j,
                    input_name=input_name,
                    handler=self.handler
                ), row_pos, j + 1)


class CustomTabWidget(QTabWidget):
    tab_close_requested = pyqtSignal(int)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._emit_close)
    def _emit_close(self, index: int):
        if self.count() > 1:
            self.tab_close_requested.emit(index)

class DragDropTableWidget(QTableWidget):
    rows_reordered = pyqtSignal(int, int)
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.drag_start_row = -1
        self.drag_start_point = QPoint()
        self.setMouseTracking(True)
        self.shape_tooltip = None
        self.tooltip_timer = QTimer()
        self.tooltip_timer.timeout.connect(self.show_shape_tooltip)
        self.tooltip_timer.setSingleShot(True)
        self.hovered_item = None
        self.hover_position = QPoint()
        self.itemSelectionChanged.connect(self._prune_hidden_from_selection)
    def _prune_hidden_from_selection(self):
        sm = self.selectionModel()
        if not sm:
            return
        for row in range(self.rowCount()):
            if self.isRowHidden(row) and sm.isRowSelected(row, self.rootIndex()):
                self.setRangeSelected(self.visualRangeForRow(row), False)
    def visualRangeForRow(self, row: int):
        from PyQt6.QtCore import QItemSelection
        left = self.model().index(row, 0)
        right = self.model().index(row, max(0, self.columnCount()-1))
        return QItemSelection(left, right)
    def keyPressEvent(self, event):
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
            self.hovered_item = None
            return
        try:
            shape_code = self.hovered_item.text().strip()
            from shape import Shape
            shape = Shape.from_string(shape_code)
            self.shape_tooltip = ShapeTooltipWidget(shape)
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
            self.setToolTip(_("ui.tooltip.shape_code", code=shape_code) + "\n" + _("ui.tooltip.parse_error", error=str(e)))
    def hide_shape_tooltip(self):
        if self.shape_tooltip:
            self.shape_tooltip.close()
            self.shape_tooltip = None
        self.setToolTip("")

class ShapeTooltipWidget(QFrame):
    def __init__(self, shape):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QFrame { background-color: rgba(50,50,50,240); border: 1px solid #666; border-radius: 8px; padding: 8px; }
            QLabel { color: white; background-color: transparent; }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(6,6,6,6)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shape_widget = ShapeWidget(shape, compact=True)
        shape_widget.setStyleSheet("background-color: white; border-radius: 4px; padding: 1px;")
        shape_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(shape_widget, 0, Qt.AlignmentFlag.AlignCenter)
        code_label = QLabel(_("ui.tooltip.shape_code", code=repr(shape)))
        code_label.setStyleSheet("""
            font-size: 11px; color: black; font-family: 'Consolas','Monaco', monospace;
            background-color: rgba(255,255,255,200); border-radius: 4px; padding: 2px 4px;
        """)
        code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(code_label)
        self.setLayout(layout)
        self.adjustSize()
        size = self.sizeHint()
        self.setFixedSize(size)

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.shape_tooltip = None
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.setInterval(300)
        self.tooltip_timer.timeout.connect(self._show_shape_tooltip)
        self.last_mouse_pos = QPoint()
    def mouseMoveEvent(self, event):
        self.last_mouse_pos = event.pos()
        self.tooltip_timer.start()
        super().mouseMoveEvent(event)
    def leaveEvent(self, event):
        self.tooltip_timer.stop()
        self._hide_shape_tooltip()
        super().leaveEvent(event)
    def wheelEvent(self, event):
        self._hide_shape_tooltip()
        super().wheelEvent(event)
    def mousePressEvent(self, event):
        self._hide_shape_tooltip()
        super().mousePressEvent(event)
    def _show_shape_tooltip(self):
        self._hide_shape_tooltip()
        cursor = self.cursorForPosition(self.last_mouse_pos)
        pos_in_line = cursor.positionInBlock()
        line_text = cursor.block().text()
        import re
        found_code = None
        for match in re.finditer(r'[\w:-]+', line_text):
            if match.start() <= pos_in_line < match.end():
                potential_code = match.group(0).strip(":")
                if not potential_code:
                    continue
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
            self.shape_tooltip = ShapeTooltipWidget(shape)
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
            self._hide_shape_tooltip()
    def _hide_shape_tooltip(self):
        if self.shape_tooltip:
            self.shape_tooltip.close()
            self.shape_tooltip = None


def load_icon_pixmap(filename: str, size: int = 16) -> Optional[QPixmap]:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    candidates = [
        os.path.join(base_dir, "icons", filename),
        os.path.join(base_dir, "icon", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                if size > 0:
                    pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                return pm
    return None

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.shape_tooltip = None
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.setInterval(300)
        self.tooltip_timer.timeout.connect(self._show_shape_tooltip)
        self.last_mouse_pos = QPoint()
    def mouseMoveEvent(self, event):
        self.last_mouse_pos = event.pos()
        self.tooltip_timer.start()
        super().mouseMoveEvent(event)
    def leaveEvent(self, event):
        self.tooltip_timer.stop()
        self._hide_shape_tooltip()
        super().leaveEvent(event)
    def wheelEvent(self, event):
        self._hide_shape_tooltip()
        super().wheelEvent(event)
    def mousePressEvent(self, event):
        self._hide_shape_tooltip()
        super().mousePressEvent(event)
    def _show_shape_tooltip(self):
        self._hide_shape_tooltip()
        cursor = self.cursorForPosition(self.last_mouse_pos)
        pos_in_line = cursor.positionInBlock()
        line_text = cursor.block().text()
        import re
        found_code = None
        for match in re.finditer(r'[\w:-]+', line_text):
            if match.start() <= pos_in_line < match.end():
                potential_code = match.group(0).strip(":")
                if not potential_code:
                    continue
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
            self.shape_tooltip = ShapeTooltipWidget(shape)
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
            self._hide_shape_tooltip()
    def _hide_shape_tooltip(self):
        if self.shape_tooltip:
            self.shape_tooltip.close()
            self.shape_tooltip = None

class DataTabWidget(QWidget):
    def __init__(self, tab_name="새 탭", data=None):
        super().__init__()
        self.tab_name = tab_name
        self.data = list(data or [])
        self.visualization_checkbox = QCheckBox(_("ui.datatab.visualize"))
        self.search_label = QLabel(_("ui.datatab.search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_("ui.datatab.search.placeholder"))
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self.data_table = QTableWidget()
        self.save_button = QPushButton(_("ui.btn.save"))
        self.save_button.clicked.connect(self.on_save_data_auto)
        self.save_as_button = QPushButton(_("ui.btn.save_as"))
        self.save_as_button.clicked.connect(self.on_save_data_as)
        self.clear_button = QPushButton(_("ui.btn.clear_data"))
        self.clear_button.clicked.connect(self.on_clear_data)
        self._setup_ui()
        self.update_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # 상단 컨트롤: 시각화, 검색, 저장 관련 버튼
        controls = QHBoxLayout()
        controls.addWidget(self.visualization_checkbox)
        controls.addWidget(self.search_label)
        controls.addWidget(self.search_input, 1)
        controls.addStretch(1)
        controls.addWidget(self.save_button)
        controls.addWidget(self.save_as_button)
        controls.addWidget(self.clear_button)
        layout.addLayout(controls)

        self.search_input.textChanged.connect(lambda _t: self._search_timer.start(120))

        # 데이터 테이블 구성
        self.data_table.setColumnCount(2)
        self.data_table.setHorizontalHeaderLabels([_("ui.table.validity"), _("ui.table.shape_code")])
        self.data_table.horizontalHeader().setStretchLastSection(False)
        try:
            self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            self.data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        except Exception:
            pass
        self.data_table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.data_table)

    def _apply_search_filter(self):
        keyword = self.search_input.text().strip()
        row_count = self.data_table.rowCount()
        if not keyword:
            for row in range(row_count):
                self.data_table.setRowHidden(row, False)
            return
        try:
            from shape import Shape
            pattern_shape, wildcard_mask = Shape.parse_pattern_with_wildcard(keyword, wildcard_char='_')
        except Exception:
            for row in range(row_count):
                self.data_table.setRowHidden(row, False)
            return
        def row_matches(code: str) -> bool:
            try:
                target = Shape.from_string(code)
                return target.contains_pattern(pattern_shape, wildcard_mask=wildcard_mask, treat_empty_as_wildcard=False)
            except Exception:
                return False
        for row in range(row_count):
            item = self.data_table.item(row, 1)
            code = item.text() if item else ""
            self.data_table.setRowHidden(row, not row_matches(code))

    def update_table(self):
        self.data_table.blockSignals(True)
        self.data_table.clearSelection()
        self.data_table.setRowCount(len(self.data))
        for i, shape_code in enumerate(self.data):
            validity_item = QTableWidgetItem("")
            validity_item.setFlags(validity_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.data_table.setItem(i, 0, validity_item)
            code_item = QTableWidgetItem(shape_code)
            self.data_table.setItem(i, 1, code_item)
            self.data_table.setRowHeight(i, 30)
        try:
            self.data_table.setColumnWidth(0, 200)
            self.data_table.setColumnWidth(1, 300)
        except Exception:
            pass
        self.data_table.blockSignals(False)
        self._update_visible_validity()

    def _on_item_changed(self, item: QTableWidgetItem):
        # 코드 열 수정 시 내부 데이터 동기화 및 유효성 재계산
        if item.column() == 1 and 0 <= item.row() < len(self.data):
            self.data[item.row()] = item.text().strip()
            self._update_visible_validity()

    def on_save_data_auto(self):
        if not self.data:
            QMessageBox.information(self, _("ui.msg.title.info"), _("ui.msg.no_data"))
            return
        import os
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        safe_filename = "".join(c for c in self.tab_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        file_path = os.path.join(data_dir, f"{safe_filename}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            for shape_code in self.data:
                f.write(f"{shape_code}\n")
        QMessageBox.information(self, _("ui.msg.title.done"), _("ui.msg.saved", path=file_path))

    def on_save_data_as(self):
        if not self.data:
            QMessageBox.information(self, _("ui.msg.title.info"), _("ui.msg.no_data"))
            return
        file_path, _ = QFileDialog.getSaveFileName(self, _("ui.btn.save_as"), f"data/{self.tab_name}.txt", "텍스트 파일 (*.txt);;모든 파일 (*.*)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                for shape_code in self.data:
                    f.write(f"{shape_code}\n")
            QMessageBox.information(self, _("ui.msg.title.done"), _("ui.msg.saved", path=file_path))

    def on_clear_data(self):
        self.data.clear()
        self.update_table()

    def _update_visible_validity(self):
        # 현재 모든 행에 대해 간단 분류 표시 (최적화는 후속)
        try:
            from shape import Shape
        except Exception:
            return
        for row in range(self.data_table.rowCount()):
            if self.data_table.isRowHidden(row):
                continue
            item_code = self.data_table.item(row, 1)
            item_valid = self.data_table.item(row, 0)
            code = item_code.text() if item_code else ""
            text = ""
            try:
                if code.strip():
                    shape = Shape.from_string(code.strip())
                    res, reason = shape.classifier()
                    text = f"{_(res)} ({_(reason)})"
                else:
                    text = _("enum.shape_type.empty") + " (" + _("analyzer.empty") + ")"
            except Exception as e:
                text = _("ui.table.error", error=str(e))
            if item_valid:
                item_valid.setText(text)
