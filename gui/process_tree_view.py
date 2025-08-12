from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt

class TreeGraphicsView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._zoom = 0
        self._zoom_step = 1.15
        self._zoom_min = -10
        self._zoom_max = 5

    def wheelEvent(self, event):
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            if angle > 0 and self._zoom < self._zoom_max:
                self._zoom += 1
                self.scale(self._zoom_step, self._zoom_step)
            elif angle < 0 and self._zoom > self._zoom_min:
                self._zoom -= 1
                self.scale(1 / self._zoom_step, 1 / self._zoom_step)
            event.accept()
        else:
            super().wheelEvent(event)
