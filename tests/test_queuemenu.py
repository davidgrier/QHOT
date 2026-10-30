'''Unit tests for QueueMenu.'''
import unittest
from unittest.mock import MagicMock, patch

from pyqtgraph.Qt import QtCore, QtWidgets

import QHOT.tasks
from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager
from QHOT.lib.tasks.QueueMenu import QueueMenu

try:
    from taskmanagers import Screen, manager_for
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import Screen, manager_for

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _make_manager():
    screen = Screen()
    return manager_for(screen)


class TestQueueMenuInit(unittest.TestCase):

    def setUp(self):
        self.menu = QueueMenu()

    def test_default_title(self):
        self.assertEqual(self.menu.title(), 'Queue')

    def test_custom_title(self):
        menu = QueueMenu(title='My Queue')
        self.assertEqual(menu.title(), 'My Queue')

    def test_manager_none_initially(self):
        self.assertIsNone(self.menu.manager)

    def test_actions_populated_from_registry(self):
        names = {a.text() for a in self.menu.actions()}
        for name in QTask._registry:
            self.assertIn(name, names)

    def test_has_at_least_one_action(self):
        self.assertGreater(len(self.menu.actions()), 0)


class TestQueueMenuProperties(unittest.TestCase):

    def setUp(self):
        self.menu = QueueMenu()

    def test_set_manager(self):
        mgr = _make_manager()
        self.menu.manager = mgr
        self.assertIs(self.menu.manager, mgr)

    def test_set_manager_to_none(self):
        self.menu.manager = _make_manager()
        self.menu.manager = None
        self.assertIsNone(self.menu.manager)

    def test_the_menu_holds_no_resources_of_its_own(self):
        # the manager owns the resources, and gives them to its tasks
        for name in ('overlay', 'cgh', 'dvr', 'save'):
            self.assertFalse(hasattr(self.menu, name), name)


class TestQueueMenuSelection(unittest.TestCase):

    def setUp(self):
        self.menu = QueueMenu()
        self.manager = _make_manager()

    def test_selecting_task_registers_with_manager(self):
        name = next(iter(QTask._registry))
        self.menu.manager = self.manager
        self.menu._onTaskSelected(name)
        # Either activeRaw or in background — something was registered
        registered = (self.manager.activeRaw is not None or
                      len(self.manager.background) > 0)
        self.assertTrue(registered)

    def test_no_manager_logs_warning(self):
        name = next(iter(QTask._registry))
        with self.assertLogs('QHOT.lib.tasks.QueueMenu', level='WARNING') as cm:
            self.menu._onTaskSelected(name)
        self.assertTrue(any('No manager' in line for line in cm.output))

    def test_unknown_task_logs_warning(self):
        self.menu.manager = self.manager
        with self.assertLogs('QHOT.lib.tasks.QueueMenu', level='WARNING') as cm:
            self.menu._onTaskSelected('NonExistentTask')
        self.assertTrue(any('Unknown task' in line for line in cm.output))

    def test_auto_pause_when_registering_into_idle_manager(self):
        self.menu.manager = self.manager
        name = next(iter(QTask._registry))
        self.menu._onTaskSelected(name)
        self.assertTrue(self.manager.paused)

    def test_no_auto_pause_when_manager_already_has_active_task(self):
        blocking = QTask()
        self.manager.register(blocking)
        self.menu.manager = self.manager
        name = next(iter(QTask._registry))
        self.menu._onTaskSelected(name)
        self.assertFalse(self.manager.paused)

    def test_no_auto_pause_when_background_task_running(self):
        bg = QTask()
        self.manager.register(bg, blocking=False)
        self.menu.manager = self.manager
        name = next(iter(QTask._registry))
        self.menu._onTaskSelected(name)
        self.assertFalse(self.manager.paused)

    def test_a_task_from_the_menu_gets_every_resource_of_the_manager(self):
        resources = dict(
            overlay=MagicMock(),
            cgh=MagicMock(),
            dvr=MagicMock(),
            save=MagicMock(),
        )
        manager = manager_for(Screen(), **resources)
        self.menu.manager = manager
        self.menu._onTaskSelected('SaveTraps')
        task = manager.scheduled[-1]
        for name, resource in resources.items():
            self.assertIs(getattr(task, name), resource, name)
        self.assertIs(task.manager, manager)

    def test_a_task_that_saves_can_save_when_queued_from_the_menu(self):
        # The menu once passed on the overlay, the CGH and the recorder
        # but not the file helper, so SaveTraps had nothing to save with.
        save, overlay = MagicMock(), MagicMock()
        manager = manager_for(Screen(), overlay=overlay, save=save)
        self.menu.manager = manager
        self.menu._onTaskSelected('SaveTraps')
        task = manager.scheduled[-1]
        task.initialize()
        save.writeJson.assert_called_once()
        self.assertIs(save.writeJson.call_args.args[0], overlay.toList.return_value)


if __name__ == '__main__':
    unittest.main()
