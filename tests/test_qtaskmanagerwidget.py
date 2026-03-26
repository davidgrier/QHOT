'''Unit tests for QTaskManagerWidget.'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtCore, QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager
from QHOT.lib.tasks.QTaskManagerWidget import QTaskManagerWidget, _ROLE

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class MockScreen(QtCore.QObject):
    rendered = QtCore.pyqtSignal()


def _make_manager():
    screen = MockScreen()
    return QTaskManager(screen)


def _make_manager_with_screen():
    screen = MockScreen()
    return QTaskManager(screen), screen


def _make_wired():
    screen = MockScreen()
    manager = QTaskManager(screen)
    widget = QTaskManagerWidget()
    widget.manager = manager
    return screen, manager, widget


class TestQTaskManagerWidgetInit(unittest.TestCase):

    def setUp(self):
        self.widget = QTaskManagerWidget()

    def test_manager_is_none_initially(self):
        self.assertIsNone(self.widget.manager)

    def test_play_button_disabled_without_manager(self):
        self.assertFalse(self.widget._playButton.isEnabled())

    def test_stop_button_disabled_without_manager(self):
        self.assertFalse(self.widget._stopButton.isEnabled())

    def test_clear_button_disabled_without_manager(self):
        self.assertFalse(self.widget._clearButton.isEnabled())

    def test_status_emitted_on_init(self):
        spy = QtTest.QSignalSpy(self.widget.status)
        self.widget._refresh()
        self.assertEqual(len(spy), 1)
        self.assertIn('not connected', spy[0][0])

    def test_queue_list_empty(self):
        self.assertEqual(self.widget._queueList.count(), 0)

    def test_background_list_empty(self):
        self.assertEqual(self.widget._bgList.count(), 0)


class TestQTaskManagerWidgetManagerProperty(unittest.TestCase):

    def setUp(self):
        self.widget  = QTaskManagerWidget()
        self.manager = _make_manager()

    def test_setting_manager_stores_it(self):
        self.widget.manager = self.manager
        self.assertIs(self.widget.manager, self.manager)

    def test_setting_manager_enables_clear_button(self):
        self.widget.manager = self.manager
        self.assertTrue(self.widget._clearButton.isEnabled())

    def test_play_stop_disabled_when_schedule_empty(self):
        self.widget.manager = self.manager
        self.assertFalse(self.widget._playButton.isEnabled())
        self.assertFalse(self.widget._stopButton.isEnabled())

    def test_play_stop_enabled_after_task_registered(self):
        self.widget.manager = self.manager
        self.manager.register(QTask())
        self.assertTrue(self.widget._playButton.isEnabled())
        self.assertTrue(self.widget._stopButton.isEnabled())

    def test_setting_none_disables_buttons(self):
        self.widget.manager = self.manager
        self.manager.register(QTask())
        self.widget.manager = None
        self.assertFalse(self.widget._playButton.isEnabled())
        self.assertFalse(self.widget._stopButton.isEnabled())
        self.assertFalse(self.widget._clearButton.isEnabled())

    def test_same_manager_is_noop(self):
        self.widget.manager = self.manager
        # Should not raise or double-connect
        self.widget.manager = self.manager

    def test_replacing_manager_disconnects_old(self):
        old = _make_manager()
        self.widget.manager = old
        spy = QtTest.QSignalSpy(old.changed)
        self.widget.manager = self.manager
        old.pause(True)              # old.changed fires
        self.assertEqual(len(spy), 1)
        # widget should NOT have refreshed from old manager's signal
        # (just verifying no error is raised)

    def test_setting_manager_triggers_refresh(self):
        spy = QtTest.QSignalSpy(self.widget.status)
        self.widget.manager = self.manager
        self.assertGreater(len(spy), 0)

    def test_status_idle_when_manager_set_empty(self):
        spy = QtTest.QSignalSpy(self.widget.status)
        self.widget.manager = self.manager
        self.assertTrue(any('Idle' in s[0] for s in spy))


class TestQTaskManagerWidgetDisplay(unittest.TestCase):

    def setUp(self):
        self.widget  = QTaskManagerWidget()
        self.manager, self.screen = _make_manager_with_screen()
        self.widget.manager = self.manager

    def _emit(self, n=1):
        for _ in range(n):
            self.screen.rendered.emit()

    def test_registered_task_appears_in_queue_list(self):
        task = QTask()
        self.manager.register(task)
        self.assertEqual(self.widget._queueList.count(), 1)
        self.assertEqual(self.widget._queueList.item(0).text(), 'QTask')

    def test_active_task_shown_bold(self):
        task = QTask()
        self.manager.register(task)
        self._emit()          # first frame: task becomes active
        item = self.widget._queueList.item(0)
        self.assertTrue(item.font().bold())

    def test_active_task_has_nyu_tint_background(self):
        from pyqtgraph.Qt import QtGui
        task = QTask()
        self.manager.register(task)
        self._emit()
        item = self.widget._queueList.item(0)
        self.assertEqual(item.background().color().name(), '#e8d5f5')

    def test_completed_task_remains_in_queue_list(self):
        task = QTask(duration=1)
        self.manager.register(task)
        self._emit(1)         # task completes
        self.assertEqual(self.widget._queueList.count(), 1)

    def test_completed_task_shown_gray(self):
        t1 = QTask(duration=1)
        t2 = QTask()          # won't auto-complete; keeps t1 visible as COMPLETED
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit(1)         # t1 completes, t2 activates
        item = self.widget._queueList.item(0)
        color = item.foreground().color()
        self.assertEqual(color.red(),   128)
        self.assertEqual(color.green(), 128)
        self.assertEqual(color.blue(),  128)

    def test_failed_task_shown_red(self):
        task = QTask()
        self.manager.register(task)
        task.abort('test')
        item = self.widget._queueList.item(0)
        color = item.foreground().color()
        self.assertEqual(color.red(),   192)
        self.assertEqual(color.green(),   0)
        self.assertEqual(color.blue(),    0)

    def test_pending_task_not_bold(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit()          # first frame: t1 active (index 0), t2 pending (index 1)
        item = self.widget._queueList.item(1)
        self.assertFalse(item.font().bold())

    def test_multiple_tasks_all_shown(self):
        for _ in range(3):
            self.manager.register(QTask())
        self.assertEqual(self.widget._queueList.count(), 3)

    def test_queue_list_count_stable_during_execution(self):
        t1 = QTask(duration=1)
        t2 = QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit(1)         # t1 completes, t2 activates
        self._emit(1)         # t2 stepped
        self.assertEqual(self.widget._queueList.count(), 2)

    def test_background_list_shows_task_name(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        self.assertEqual(self.widget._bgList.count(), 1)
        self.assertEqual(self.widget._bgList.item(0).text(), 'QTask')

    def test_background_list_clears_after_task_finishes(self):
        task = QTask(duration=1)
        self.manager.register(task, blocking=False)
        task._step()
        self.assertEqual(self.widget._bgList.count(), 0)

    def test_status_running_when_active_task(self):
        spy = QtTest.QSignalSpy(self.widget.status)
        self.manager.register(QTask())
        self._emit()          # first frame: task becomes active
        self.assertTrue(any('Running' in s[0] for s in spy))

    def test_status_running_with_background_only(self):
        spy = QtTest.QSignalSpy(self.widget.status)
        self.manager.register(QTask(), blocking=False)
        self.assertTrue(any('Running' in s[0] for s in spy))

    def test_status_idle_when_nothing_running(self):
        spy = QtTest.QSignalSpy(self.widget.status)
        self.widget._refresh()
        self.assertTrue(any('Idle' in s[0] for s in spy))


class TestQTaskManagerWidgetControls(unittest.TestCase):

    def setUp(self):
        self.widget  = QTaskManagerWidget()
        self.manager, self.screen = _make_manager_with_screen()
        self.widget.manager = self.manager

    def _emit(self, n=1):
        for _ in range(n):
            self.screen.rendered.emit()

    def test_play_button_shows_play_when_idle(self):
        self.assertEqual(self.widget._playButton.text(), 'Play')

    def test_play_button_shows_pause_when_running(self):
        self.manager.register(QTask())
        self._emit()          # first frame: task becomes active
        self.assertEqual(self.widget._playButton.text(), 'Pause')

    def test_play_button_shows_play_when_paused(self):
        self.manager.register(QTask())
        self.manager.pause(True)
        self.assertEqual(self.widget._playButton.text(), 'Play')

    def test_clicking_play_unpauses_manager(self):
        self.manager.register(QTask())
        self.manager.pause(True)
        self.widget._playButton.click()
        self.assertFalse(self.manager.paused)

    def test_clicking_pause_pauses_manager(self):
        self.manager.register(QTask())
        self._emit()          # task is active (not paused)
        self.widget._playButton.click()
        self.assertTrue(self.manager.paused)

    def test_status_paused_when_manager_paused(self):
        spy = QtTest.QSignalSpy(self.widget.status)
        self.manager.pause(True)
        self.assertTrue(any('Paused' in s[0] for s in spy))

    def test_stop_rewinds_to_start(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit()          # t1 active
        self.widget._stopButton.click()
        # After rewind: paused at first task, not yet stepped
        self.assertIsNone(self.manager.active)
        self.assertTrue(self.manager.paused)

    def test_stop_preserves_schedule(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.widget._stopButton.click()
        self.assertEqual(self.widget._queueList.count(), 2)

    def test_clear_button_empties_queue_list(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.widget._clearButton.click()
        self.assertEqual(self.widget._queueList.count(), 0)

    def test_clear_button_clears_background_list(self):
        self.manager.register(QTask(), blocking=False)
        self.widget._clearButton.click()
        self.assertEqual(self.widget._bgList.count(), 0)

    def test_play_button_no_op_without_manager(self):
        self.widget.manager = None
        self.widget._onPlayClicked()    # should not raise

    def test_stop_button_no_op_without_manager(self):
        self.widget.manager = None
        self.widget._onStopClicked()    # should not raise

    def test_clear_button_no_op_without_manager(self):
        self.widget.manager = None
        self.widget._onClearClicked()   # should not raise


class TestQTaskManagerWidgetParamTree(unittest.TestCase):

    def setUp(self):
        self.widget  = QTaskManagerWidget()
        self.manager, self.screen = _make_manager_with_screen()
        self.widget.manager = self.manager

    def _emit(self, n=1):
        for _ in range(n):
            self.screen.rendered.emit()

    def test_param_tree_empty_initially(self):
        self.assertIsNone(self.widget._taskTree)

    def test_clicking_active_task_populates_param_tree(self):
        from QHOT.tasks.Delay import Delay
        task = Delay(frames=100)
        self.manager.register(task)
        self._emit()          # first frame: task becomes active (index 0)
        self.manager.pause(True)
        item = self.widget._queueList.item(0)
        self.widget._onTaskItemClicked(item)
        self.assertIsNotNone(self.widget._taskTree)
        root = self.widget._taskTree.invisibleRootItem()
        self.assertEqual(root.childCount(), 1)
        n_params = len(type(task).parameters)
        self.assertEqual(root.child(0).childCount(), n_params)

    def test_clicking_pending_task_populates_param_tree(self):
        from QHOT.tasks.Delay import Delay
        t1 = Delay(frames=100)
        t2 = Delay(frames=200)
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit()          # first frame: t1 active (index 0), t2 pending (index 1)
        item = self.widget._queueList.item(1)
        self.widget._onTaskItemClicked(item)
        self.assertIsNotNone(self.widget._taskTree)
        root = self.widget._taskTree.invisibleRootItem()
        self.assertEqual(root.childCount(), 1)
        n_params = len(type(t2).parameters)
        self.assertEqual(root.child(0).childCount(), n_params)

    def test_param_tree_removed_when_task_cleared(self):
        from QHOT.tasks.Delay import Delay
        task = Delay(frames=100)
        self.manager.register(task)
        self._emit()
        self.manager.pause(True)
        item = self.widget._queueList.item(0)
        self.widget._onTaskItemClicked(item)
        # Clear removes all tasks; _reselectTask should remove the tree
        self.manager.clear()
        self.assertIsNone(self.widget._selectedTask)
        self.assertIsNone(self.widget._taskTree)

    def test_selected_task_reselected_after_refresh(self):
        t1 = QTask()
        t2 = QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit()          # first frame: t1 active (index 0), t2 pending (index 1)
        item = self.widget._queueList.item(1)
        self.widget._onTaskItemClicked(item)
        self.assertIs(self.widget._selectedTask, t2)
        self.manager.pause(True)
        self.assertIs(self.widget._selectedTask, t2)


class TestQTaskManagerWidgetRemove(unittest.TestCase):

    def setUp(self):
        self.screen, self.manager, self.widget = _make_wired()

    def test_delete_key_removes_selected_pending_task(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.widget._queueList.setCurrentRow(1)   # select t2
        self.widget._onDeletePressed()
        self.assertNotIn(t2, self.manager.scheduled)

    def test_delete_key_does_not_remove_active_task(self):
        t1 = QTask()
        self.manager.register(t1)
        self.widget._queueList.setCurrentRow(0)   # select t1 (running)
        self.widget._onDeletePressed()
        self.assertIn(t1, self.manager.scheduled)

    def test_delete_key_no_selection_is_noop(self):
        t1 = QTask()
        self.manager.register(t1)
        self.widget._queueList.clearSelection()
        self.widget._onDeletePressed()   # should not raise
        self.assertIn(t1, self.manager.scheduled)

    def test_delete_key_no_manager_is_noop(self):
        self.widget.manager = None
        self.widget._onDeletePressed()   # should not raise

    def test_context_menu_remove_action_calls_manager_remove(self):
        import sys
        from unittest.mock import patch, MagicMock
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        item = self.widget._queueList.item(1)
        fake_menu = MagicMock()
        remove_action = MagicMock()
        fake_menu.addAction.return_value = remove_action
        fake_menu.exec.return_value = remove_action
        module = sys.modules['QHOT.lib.tasks.QTaskManagerWidget']
        with patch.object(module, 'QtWidgets') as mock_qtw:
            mock_qtw.QMenu.return_value = fake_menu
            with patch.object(self.manager, 'remove') as mock_remove:
                self.widget._onQueueContextMenu(
                    self.widget._queueList.visualItemRect(item).center())
                mock_remove.assert_called_once_with(t2)

    def test_context_menu_remove_disabled_for_active_task(self):
        import sys
        from unittest.mock import patch, MagicMock
        t1 = QTask()
        self.manager.register(t1)
        item = self.widget._queueList.item(0)
        fake_menu = MagicMock()
        remove_action = MagicMock()
        fake_menu.addAction.return_value = remove_action
        fake_menu.exec.return_value = None
        module = sys.modules['QHOT.lib.tasks.QTaskManagerWidget']
        with patch.object(module, 'QtWidgets') as mock_qtw:
            mock_qtw.QMenu.return_value = fake_menu
            self.widget._onQueueContextMenu(
                self.widget._queueList.visualItemRect(item).center())
            remove_action.setEnabled.assert_called_once_with(False)

    def test_context_menu_no_item_is_noop(self):
        self.widget._onQueueContextMenu(QtCore.QPoint(0, 0))  # empty list area


class TestQTaskManagerWidgetDragReorder(unittest.TestCase):

    def setUp(self):
        self.screen, self.manager, self.widget = _make_wired()

    def _emit(self, n: int = 1) -> None:
        for _ in range(n):
            self.screen.rendered.emit()

    def test_queue_list_has_internal_move(self):
        from pyqtgraph.Qt import QtWidgets as _QtW
        self.assertEqual(
            self.widget._queueList.dragDropMode(),
            _QtW.QAbstractItemView.DragDropMode.InternalMove)

    def test_pending_items_are_draggable(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        # t1 is active (RUNNING), t2 is PENDING
        item_t2 = self.widget._queueList.item(1)
        drag_flag = QtCore.Qt.ItemFlag.ItemIsDragEnabled
        self.assertTrue(bool(item_t2.flags() & drag_flag))

    def test_running_item_is_not_draggable(self):
        t1 = QTask()
        self.manager.register(t1)
        item_t1 = self.widget._queueList.item(0)
        drag_flag = QtCore.Qt.ItemFlag.ItemIsDragEnabled
        self.assertFalse(bool(item_t1.flags() & drag_flag))

    def test_on_rows_moved_calls_reorder(self):
        from unittest.mock import MagicMock, patch
        t1, t2, t3 = QTask(), QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.manager.register(t3)
        with patch.object(self.manager, 'reorder') as mock_reorder:
            # Simulate rowsMoved: pretend t3 (row 2) moved to row 1
            self.widget._onRowsMoved(
                QtCore.QModelIndex(), 2, 2, QtCore.QModelIndex(), 1)
            mock_reorder.assert_called_once()
            args = mock_reorder.call_args[0][0]
            self.assertEqual(len(args), 3)
            self.assertTrue(all(isinstance(t, QTask) for t in args))

    def test_on_rows_moved_no_manager_does_nothing(self):
        self.widget.manager = None
        # Should not raise
        self.widget._onRowsMoved(
            QtCore.QModelIndex(), 0, 0, QtCore.QModelIndex(), 1)

    def test_reorder_reflected_in_queue_list(self):
        t1, t2, t3 = QTask(), QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.manager.register(t3)
        self.manager.reorder([t1, t3, t2])
        items = [self.widget._queueList.item(i).data(_ROLE)
                 for i in range(self.widget._queueList.count())]
        self.assertEqual(items, [t1, t3, t2])


if __name__ == '__main__':
    unittest.main()
