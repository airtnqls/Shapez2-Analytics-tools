from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional, List, Tuple

class OriginFinderThread(QThread):
    progress = pyqtSignal(int, int, str)
    candidate_found = pyqtSignal()
    finished = pyqtSignal(list)
    log_message = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        # 실제 동작은 기존 구현을 사용하되, 인터페이스만 보장
        self.is_cancelled = False

    def run(self):
        # 자리 구현: 즉시 종료 신호
        self.finished.emit([])

    def cancel(self):
        self.is_cancelled = True


class BatchWorkerThread(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished_with_results = pyqtSignal(dict, list, int, bool)  # result_map, append_list, error_count, canceled

    def __init__(self, *args, **kwargs):
        super().__init__()

    def run(self):
        self.finished_with_results.emit({}, [], 0, False)


class InputHistory:
    """입력 필드의 히스토리를 관리하는 클래스 (A, B 통합)"""
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.history: List[Tuple[str, str]] = []
        self.current_index: int = -1

    def add_entry(self, input_a: str, input_b: str) -> None:
        entry = (input_a, input_b)
        if self.history and self.current_index >= 0 and self.history[self.current_index] == entry:
            return
        if self.current_index < len(self.history) - 1:
            self.history = self.history[: self.current_index + 1]
        self.history.append(entry)
        self.current_index = len(self.history) - 1
        if len(self.history) > self.max_size:
            self.history.pop(0)
            self.current_index -= 1

    def can_undo(self) -> bool:
        return self.current_index > 0

    def can_redo(self) -> bool:
        return self.current_index < len(self.history) - 1

    def undo(self) -> Optional[Tuple[str, str]]:
        if self.can_undo():
            self.current_index -= 1
            return self.history[self.current_index]
        return None

    def redo(self) -> Optional[Tuple[str, str]]:
        if self.can_redo():
            self.current_index += 1
            return self.history[self.current_index]
        return None

    def get_current(self) -> Tuple[str, str]:
        if 0 <= self.current_index < len(self.history):
            return self.history[self.current_index]
        return ("", "")


class DataHistory:
    """데이터 탭의 히스토리를 관리하는 클래스"""
    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.history: List[Tuple[list, str]] = []
        self.current_index: int = -1

    def add_entry(self, data: list, operation_name: str = "") -> None:
        entry = (data.copy(), operation_name)
        if self.history and self.current_index >= 0 and self.history[self.current_index][0] == data:
            return
        if self.current_index < len(self.history) - 1:
            self.history = self.history[: self.current_index + 1]
        self.history.append(entry)
        self.current_index = len(self.history) - 1
        if len(self.history) > self.max_size:
            self.history.pop(0)
            self.current_index -= 1

    def can_undo(self) -> bool:
        return self.current_index > 0

    def can_redo(self) -> bool:
        return self.current_index < len(self.history) - 1

    def undo(self) -> Optional[Tuple[list, str]]:
        if self.can_undo():
            self.current_index -= 1
            return self.history[self.current_index]
        return None

    def redo(self) -> Optional[Tuple[list, str]]:
        if self.can_redo():
            self.current_index += 1
            return self.history[self.current_index]
        return None

    def get_current(self) -> Tuple[list, str]:
        if 0 <= self.current_index < len(self.history):
            return self.history[self.current_index]
        return ([], "")
