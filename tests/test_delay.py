'''Unit tests for Delay.'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.Delay import Delay

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestDelayInit(unittest.TestCase):

    def test_duration_set_from_frames(self):
        task = Delay(10)
        self.assertEqual(task.duration, 10)

    def test_setting_frames_updates_duration(self):
        task = Delay(10)
        task.frames = 50
        self.assertEqual(task.duration, 50)

    def test_initial_state_is_pending(self):
        task = Delay(5)
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_duration_kwarg_raises(self):
        with self.assertRaises(TypeError):
            Delay(5, duration=10)

    def test_zero_frames_accepted(self):
        task = Delay(0)
        self.assertEqual(task.duration, 0)


class TestDelayExecution(unittest.TestCase):

    def test_running_after_start(self):
        task = Delay(5)
        task._start()
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_still_running_before_duration_expires(self):
        task = Delay(5)
        task._start()
        for _ in range(4):
            task._step()
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_completes_after_exact_frames(self):
        task = Delay(5)
        task._start()
        for _ in range(5):
            task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_does_not_complete_one_step_early(self):
        task = Delay(10)
        task._start()
        for _ in range(9):
            task._step()
        self.assertNotEqual(task.state, QTask.State.COMPLETED)

    def test_process_never_overridden(self):
        # process() in Delay is the base no-op; verify it does nothing
        task = Delay(3)
        task._start()
        for _ in range(3):
            task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_delay_one_frame(self):
        task = Delay(1)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_zero_frame_delay_completes_immediately(self):
        task = Delay(0)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_finished_signal_emitted(self):
        task = Delay(2)
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        task._step()
        task._step()
        self.assertEqual(len(spy), 1)

    def test_finished_emitted_exactly_once(self):
        task = Delay(2)
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        for _ in range(5):
            task._step()
        self.assertEqual(len(spy), 1)


if __name__ == '__main__':
    unittest.main()
