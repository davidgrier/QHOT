import logging

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager
from QHOT.lib.tasks.QTaskTree import QTaskTree


logger = logging.getLogger(__name__)

__all__ = ['QTaskManagerWidget']

_ROLE = QtCore.Qt.ItemDataRole.UserRole


class QTaskManagerWidget(QtWidgets.QWidget):

    '''Widget for monitoring and controlling a QTaskManager.

    Displays all scheduled blocking tasks in a single queue list.
    The active task is shown in bold; completed tasks are grayed;
    failed tasks are shown in red.  Background tasks appear in a
    separate list.  Clicking any task item shows its editable
    parameters in a ParameterTree below; changes are written back to
    the task immediately.  Provides Pause/Resume, Stop, and Clear
    controls.  Emits ``status`` with a human-readable description of
    the manager state on every refresh.

    The widget requires no arguments at construction time.  Connect
    it to a manager via the ``manager`` property after construction::

        widget = QTaskManagerWidget()
        widget.manager = some_manager

    Parameters
    ----------
    *args, **kwargs
        Forwarded to ``QWidget``.

    Attributes
    ----------
    manager : QTaskManager or None
        The connected task manager.  Setting this property connects
        the widget to ``manager.changed`` and refreshes the display.

    Signals
    -------
    status(str)
        Emitted on every state change with a short description
        suitable for display in a status bar.
    '''

    status = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._manager: QTaskManager | None = None
        self._selectedTask = None
        self._taskTree: QTaskTree | None = None
        self._setupUi()

    def _setupUi(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Blocking queue (all scheduled tasks; active shown bold)
        queueGroup = QtWidgets.QGroupBox('Queue')
        queueLayout = QtWidgets.QVBoxLayout(queueGroup)
        self._queueList = QtWidgets.QListWidget()
        self._queueList.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._queueList.setMaximumHeight(120)
        queueLayout.addWidget(self._queueList)
        layout.addWidget(queueGroup)

        # Background tasks
        bgGroup = QtWidgets.QGroupBox('Background')
        bgLayout = QtWidgets.QVBoxLayout(bgGroup)
        self._bgList = QtWidgets.QListWidget()
        self._bgList.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._bgList.setMaximumHeight(80)
        bgLayout.addWidget(self._bgList)
        layout.addWidget(bgGroup)

        # Parameter tree (populated on task selection)
        paramsGroup = QtWidgets.QGroupBox('Parameters')
        self._paramsLayout = QtWidgets.QVBoxLayout(paramsGroup)
        layout.addWidget(paramsGroup)

        # Controls
        controlLayout = QtWidgets.QHBoxLayout()
        self._pauseButton = QtWidgets.QPushButton('Pause')
        self._pauseButton.setEnabled(False)
        self._stopButton = QtWidgets.QPushButton('Stop')
        self._stopButton.setEnabled(False)
        self._clearButton = QtWidgets.QPushButton('Clear')
        self._clearButton.setEnabled(False)
        controlLayout.addWidget(self._pauseButton)
        controlLayout.addWidget(self._stopButton)
        controlLayout.addWidget(self._clearButton)
        controlLayout.addStretch()
        layout.addLayout(controlLayout)

        self._pauseButton.clicked.connect(self._onPauseClicked)
        self._stopButton.clicked.connect(self._onStopClicked)
        self._clearButton.clicked.connect(self._onClearClicked)
        self._queueList.itemClicked.connect(self._onTaskItemClicked)
        self._bgList.itemClicked.connect(self._onTaskItemClicked)

    # ------------------------------------------------------------------
    # manager property

    @property
    def manager(self) -> QTaskManager | None:
        '''The connected task manager, or ``None``.'''
        return self._manager

    @manager.setter
    def manager(self, manager: QTaskManager | None) -> None:
        if manager is self._manager:
            return
        if self._manager is not None:
            self._manager.changed.disconnect(self._refresh)
        self._manager = manager
        if manager is not None:
            manager.changed.connect(self._refresh)
        self._refresh()

    # ------------------------------------------------------------------
    # Private helpers

    @staticmethod
    def _taskItem(task: QTask) -> QtWidgets.QListWidgetItem:
        '''Create a list item styled according to the task's state.'''
        item = QtWidgets.QListWidgetItem(type(task).__name__)
        item.setData(_ROLE, task)
        state = task.state
        if state is QTask.State.RUNNING:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        elif state is QTask.State.COMPLETED:
            item.setForeground(QtGui.QBrush(
                QtGui.QColor(128, 128, 128)))
        elif state is QTask.State.FAILED:
            item.setForeground(QtGui.QBrush(
                QtGui.QColor(192, 0, 0)))
        return item

    def _reselectTask(self) -> None:
        '''Re-highlight the previously selected task after a refresh.

        If the task is no longer present, removes the parameter tree.
        '''
        if self._selectedTask is None:
            return
        for lst in (self._queueList, self._bgList):
            for i in range(lst.count()):
                item = lst.item(i)
                if item.data(_ROLE) is self._selectedTask:
                    lst.setCurrentItem(item)
                    return
        # Task is gone — remove tree
        self._selectedTask = None
        self._removeTaskTree()

    # ------------------------------------------------------------------
    # Slots

    @QtCore.pyqtSlot()
    def _onPauseClicked(self) -> None:
        if self._manager is not None:
            self._manager.pause(not self._manager.paused)

    @QtCore.pyqtSlot()
    def _onStopClicked(self) -> None:
        if self._manager is not None:
            self._manager.stop()

    @QtCore.pyqtSlot()
    def _onClearClicked(self) -> None:
        if self._manager is not None:
            self._manager.clear()

    def _removeTaskTree(self) -> None:
        '''Detach and discard the current QTaskTree, if any.'''
        if self._taskTree is not None:
            self._taskTree.setParent(None)
            self._taskTree = None

    @QtCore.pyqtSlot(QtWidgets.QListWidgetItem)
    def _onTaskItemClicked(self, item: QtWidgets.QListWidgetItem) -> None:
        '''Show the clicked task's parameters in a fresh QTaskTree.'''
        task = item.data(_ROLE)
        self._selectedTask = task
        self._removeTaskTree()
        if task is not None and type(task).parameters:
            self._taskTree = QTaskTree(task)
            self._taskTree.setMinimumHeight(80)
            self._paramsLayout.addWidget(self._taskTree)

    @QtCore.pyqtSlot()
    def _refresh(self) -> None:
        '''Repopulate all display elements from the manager state.'''
        has_manager = self._manager is not None
        self._pauseButton.setEnabled(has_manager)
        self._stopButton.setEnabled(has_manager)
        self._clearButton.setEnabled(has_manager)

        if not has_manager:
            self.status.emit('Task manager: not connected')
            self._queueList.clear()
            self._bgList.clear()
            self._selectedTask = None
            self._removeTaskTree()
            return

        # Status signal
        if self._manager.paused:
            self.status.emit('Task manager: Paused')
            self._pauseButton.setText('Resume')
        elif (self._manager.active is not None
              or self._manager.background):
            self.status.emit('Task manager: Running')
            self._pauseButton.setText('Pause')
        elif self._manager.queued:
            self.status.emit('Task manager: Ready')
            self._pauseButton.setText('Pause')
        else:
            self.status.emit('Task manager: Idle')
            self._pauseButton.setText('Pause')

        # Blocking queue: all scheduled tasks with state-based styling
        self._queueList.clear()
        for task in self._manager.scheduled:
            self._queueList.addItem(self._taskItem(task))

        # Background tasks
        self._bgList.clear()
        for task in self._manager.background:
            self._bgList.addItem(self._taskItem(task))

        self._reselectTask()
