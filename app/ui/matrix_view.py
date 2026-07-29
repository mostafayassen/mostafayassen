"""Eisenhower matrix board: a first-class 4-quadrant view of open tasks.

Each quadrant is its own list; tasks can be reassigned to a different
quadrant via a right-click context menu / combo box (drag-and-drop between
quadrant lists is also wired up using Qt's built-in list drag/drop).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import db
from app.models import ALL_QUADRANTS, QUADRANT_LABELS, STATUS_DONE, Task


class _QuadrantList(QListWidget):
    """A QListWidget representing one quadrant; supports drag-drop between
    quadrant lists and emits taskDropped(task_id, new_quadrant) when a task
    lands here from another quadrant."""

    taskDropped = Signal(int, str)

    def __init__(self, quadrant: str, parent=None):
        super().__init__(parent)
        self.quadrant = quadrant
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        source = event.source()
        item = source.currentItem() if source else None
        super().dropEvent(event)
        if item is not None:
            task_id = item.data(Qt.UserRole)
            if task_id is not None:
                self.taskDropped.emit(task_id, self.quadrant)


class MatrixView(QWidget):
    def __init__(self, db_path: Optional[str], on_open_task=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.on_open_task = on_open_task
        self.lists: dict[str, _QuadrantList] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Eisenhower Matrix</h2>"))
        layout.addWidget(
            QLabel(
                "Drag tasks between quadrants, or right-click a task to reassign it."
            )
        )

        grid = QGridLayout()
        positions = {
            ALL_QUADRANTS[0]: (0, 0),  # urgent+important
            ALL_QUADRANTS[2]: (0, 1),  # urgent+not important
            ALL_QUADRANTS[1]: (1, 0),  # not urgent+important
            ALL_QUADRANTS[3]: (1, 1),  # not urgent+not important
        }
        for quadrant, (row, col) in positions.items():
            box = QGroupBox(QUADRANT_LABELS[quadrant])
            box_layout = QVBoxLayout(box)
            list_widget = _QuadrantList(quadrant)
            list_widget.itemDoubleClicked.connect(self._open_item)
            list_widget.taskDropped.connect(self._on_task_dropped)
            list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            list_widget.customContextMenuRequested.connect(
                lambda pos, lw=list_widget: self._show_context_menu(lw, pos)
            )
            box_layout.addWidget(list_widget)
            grid.addWidget(box, row, col)
            self.lists[quadrant] = list_widget

        layout.addLayout(grid)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        self.refresh()

    def refresh(self) -> None:
        for list_widget in self.lists.values():
            list_widget.clear()
        tasks = [t for t in db.list_tasks(self.db_path) if t.status != STATUS_DONE]
        for task in tasks:
            quadrant = task.quadrant if task.quadrant in self.lists else ALL_QUADRANTS[1]
            item = QListWidgetItem(task.title)
            item.setData(Qt.UserRole, task.id)
            self.lists[quadrant].addItem(item)

    def _open_item(self, item: QListWidgetItem) -> None:
        if self.on_open_task:
            self.on_open_task(item.data(Qt.UserRole))

    def _on_task_dropped(self, task_id: int, new_quadrant: str) -> None:
        task = db.get_task(task_id, self.db_path)
        if task and task.quadrant != new_quadrant:
            task.quadrant = new_quadrant
            db.update_task(task, self.db_path)
        self.refresh()

    def _show_context_menu(self, list_widget: _QuadrantList, pos) -> None:
        item = list_widget.itemAt(pos)
        if item is None:
            return
        task_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        for quadrant in ALL_QUADRANTS:
            if quadrant == list_widget.quadrant:
                continue
            action = menu.addAction(f"Move to: {QUADRANT_LABELS[quadrant]}")
            action.triggered.connect(
                lambda checked=False, q=quadrant, tid=task_id: self._reassign(tid, q)
            )
        menu.exec(list_widget.mapToGlobal(pos))

    def _reassign(self, task_id: int, quadrant: str) -> None:
        task = db.get_task(task_id, self.db_path)
        if task:
            task.quadrant = quadrant
            db.update_task(task, self.db_path)
        self.refresh()
