'''Unit tests for QueueMenu.'''
import unittest
from unittest.mock import MagicMock, patch

from pyqtgraph.Qt import QtCore, QtWidgets

import QHOT.tasks
from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager
from QHOT.lib.tasks.QueueMenu import QueueMenu

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class MockScreen(QtCore.QObject):
    rendered = QtCore.pyqtSignal()


def _make_manager():
    screen = MockScreen()
    return QTaskManager(screen)


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

    def test_overlay_none_initially(self):
        self.assertIsNone(self.menu.overlay)

    def test_cgh_none_initially(self):
        self.assertIsNone(self.menu.cgh)

    def test_dvr_none_initially(self):
        self.assertIsNone(self.menu.dvr)

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

    def test_set_overlay(self):
        overlay = MagicMock()
        self.menu.overlay = overlay
        self.assertIs(self.menu.overlay, overlay)

    def test_set_cgh(self):
        cgh = MagicMock()
        self.menu.cgh = cgh
        self.assertIs(self.menu.cgh, cgh)

    def test_set_dvr(self):
        dvr = MagicMock()
        self.menu.dvr = dvr
        self.assertIs(self.menu.dvr, dvr)


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

    def test_dependencies_injected_into_task(self):
        overlay = MagicMock()
        cgh = MagicMock()
        dvr = MagicMock()
        self.menu.manager = self.manager
        self.menu.overlay = overlay
        self.menu.cgh = cgh
        self.menu.dvr = dvr

        name = next(iter(QTask._registry))
        cls = QTask._registry[name]
        created = []
        original_init = cls.__init__

        def capture_init(self_task, *args, **kwargs):
            created.append(kwargs)
            original_init(self_task, *args, **kwargs)

        with patch.object(cls, '__init__', capture_init):
            self.menu._onTaskSelected(name)

        self.assertTrue(len(created) > 0)
        self.assertIs(created[0].get('overlay'), overlay)
        self.assertIs(created[0].get('cgh'), cgh)
        self.assertIs(created[0].get('dvr'), dvr)


if __name__ == '__main__':
    unittest.main()
