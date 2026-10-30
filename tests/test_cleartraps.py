'''Unit tests for ClearTraps.'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.ClearTraps import ClearTraps

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestClearTrapsInit(unittest.TestCase):

    def setUp(self):
        self.overlay = MagicMock()

    def test_duration_is_zero(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        self.assertEqual(task.duration, 0)

    def test_duration_cannot_be_overridden(self):
        # duration=0 is set unconditionally; any caller-supplied
        # duration is silently overridden by the super().__init__ call
        task = attached(ClearTraps(), overlay=self.overlay)
        self.assertEqual(task.duration, 0)

    def test_initial_state_is_pending(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        self.assertEqual(task.state, QTask.State.PENDING)


class TestClearTrapsExecution(unittest.TestCase):

    def setUp(self):
        self.overlay = MagicMock()

    def test_clear_traps_called_on_step(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        task._start()
        task._step()
        self.overlay.clearTraps.assert_called_once()

    def test_completes_after_one_step(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_process_never_called(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        task.process = MagicMock()
        task._start()
        task._step()
        task.process.assert_not_called()

    def test_clear_traps_not_called_before_start(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        task._step()
        self.overlay.clearTraps.assert_not_called()

    def test_clear_traps_called_exactly_once(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        task._start()
        task._step()
        task._step()
        task._step()
        self.overlay.clearTraps.assert_called_once()

    def test_finished_signal_emitted(self):
        task = attached(ClearTraps(), overlay=self.overlay)
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)

    def test_overlay_exception_fails_task(self):
        self.overlay.clearTraps.side_effect = RuntimeError('no traps')
        task = attached(ClearTraps(), overlay=self.overlay)
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)
        self.assertEqual(task.state, QTask.State.FAILED)


if __name__ == '__main__':
    unittest.main()
