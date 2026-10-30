'''Unit tests for BeginRepeat.'''
import unittest

from pyqtgraph.Qt import QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.BeginRepeat import BeginRepeat

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestBeginRepeatInit(unittest.TestCase):

    def test_registered_in_registry(self):
        self.assertIn('BeginRepeat', QTask._registry)

    def test_duration_is_zero(self):
        self.assertEqual(BeginRepeat().duration, 0)

    def test_duration_keyword_raises(self):
        with self.assertRaises(TypeError):
            BeginRepeat(duration=1)

    def test_no_parameters(self):
        self.assertEqual(BeginRepeat.parameters, ())

    def test_initial_state_pending(self):
        self.assertEqual(BeginRepeat().state, QTask.State.PENDING)


class TestBeginRepeatExecution(unittest.TestCase):

    def test_completes_after_one_step(self):
        task = BeginRepeat()
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_finished_signal_emitted(self):
        task = BeginRepeat()
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)


class TestBeginRepeatSerialization(unittest.TestCase):

    def test_to_dict_includes_type(self):
        self.assertEqual(BeginRepeat().toDict()['type'], 'BeginRepeat')

    def test_round_trip(self):
        task = BeginRepeat()
        restored = QTask.fromDict(task.toDict())
        self.assertIsInstance(restored, BeginRepeat)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
