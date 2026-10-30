'''Unit tests for AddTweezer.'''
import unittest
from unittest.mock import MagicMock, call

from pyqtgraph.Qt import QtCore, QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.AddTweezer import AddTweezer

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestAddTweezerInit(unittest.TestCase):

    def setUp(self):
        self.overlay = MagicMock()
        self.cgh = MagicMock()
        self.cgh.xc = 320.
        self.cgh.yc = 240.

    def test_duration_is_zero(self):
        task = attached(AddTweezer(), overlay=self.overlay)
        self.assertEqual(task.duration, 0)

    def test_initial_state_is_pending(self):
        task = attached(AddTweezer(), overlay=self.overlay)
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_explicit_x_y_stored(self):
        task = attached(AddTweezer(x=100., y=200.), overlay=self.overlay)
        self.assertEqual(task.x, 100.)
        self.assertEqual(task.y, 200.)

    def test_default_position_uses_cgh_center(self):
        task = attached(AddTweezer(), overlay=self.overlay, cgh=self.cgh)
        self.assertEqual(task.x, 320.)
        self.assertEqual(task.y, 240.)

    def test_the_default_position_is_found_when_it_is_read(self):
        # the manager gives the task its CGH after the task is made
        task = attached(AddTweezer(), overlay=self.overlay)
        task.cgh = self.cgh
        self.assertEqual((task.x, task.y), (320., 240.))

    def test_the_default_position_follows_the_cgh(self):
        task = attached(AddTweezer(), overlay=self.overlay, cgh=self.cgh)
        self.cgh.xc = 300.
        self.assertEqual(task.x, 300.)

    def test_a_position_that_is_set_stays(self):
        task = attached(AddTweezer(), overlay=self.overlay, cgh=self.cgh)
        task.x = 10
        self.cgh.xc = 300.
        self.assertEqual(task.x, 10.)
        self.assertIsInstance(task.x, float)

    def test_registered_in_registry(self):
        self.assertIn('AddTweezer', QTask._registry)

    def test_parameters_declared(self):
        names = [p['name'] for p in AddTweezer.parameters]
        self.assertIn('x', names)
        self.assertIn('y', names)

    def test_position_attributes_set(self):
        task = attached(AddTweezer(x=50., y=75.), overlay=self.overlay)
        self.assertAlmostEqual(task.x, 50.)
        self.assertAlmostEqual(task.y, 75.)


class TestAddTweezerExecution(unittest.TestCase):

    def setUp(self):
        self.overlay = MagicMock()
        self.cgh = MagicMock()
        self.cgh.xc = 320.
        self.cgh.yc = 240.

    def test_add_trap_called_on_step(self):
        task = attached(AddTweezer(x=10., y=20.), overlay=self.overlay)
        task._start()
        task._step()
        self.overlay.addTrap.assert_called_once()

    def test_add_trap_called_with_correct_position(self):
        task = attached(AddTweezer(x=10., y=20.), overlay=self.overlay)
        task._start()
        task._step()
        args = self.overlay.addTrap.call_args[0]
        pos = args[0]
        self.assertIsInstance(pos, QtCore.QPointF)
        self.assertAlmostEqual(pos.x(), 10.)
        self.assertAlmostEqual(pos.y(), 20.)

    def test_completes_after_one_step(self):
        task = attached(AddTweezer(x=0., y=0.), overlay=self.overlay)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_add_trap_not_called_before_start(self):
        task = attached(AddTweezer(x=0., y=0.), overlay=self.overlay)
        task._step()
        self.overlay.addTrap.assert_not_called()

    def test_add_trap_called_exactly_once(self):
        task = attached(AddTweezer(x=0., y=0.), overlay=self.overlay)
        task._start()
        task._step()
        task._step()
        self.overlay.addTrap.assert_called_once()

    def test_process_never_called(self):
        task = attached(AddTweezer(x=0., y=0.), overlay=self.overlay)
        task.process = MagicMock()
        task._start()
        task._step()
        task.process.assert_not_called()

    def test_finished_signal_emitted(self):
        task = attached(AddTweezer(x=0., y=0.), overlay=self.overlay)
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)

    def test_overlay_exception_fails_task(self):
        self.overlay.addTrap.side_effect = RuntimeError('scene error')
        task = attached(AddTweezer(x=0., y=0.), overlay=self.overlay)
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)
        self.assertEqual(task.state, QTask.State.FAILED)


class TestAddTweezerParamSync(unittest.TestCase):

    def setUp(self):
        from QHOT.lib.tasks.QTaskTree import QTaskTree
        self.QTaskTree = QTaskTree

    def test_editing_x_param_updates_attribute(self):
        task = AddTweezer(x=10., y=20.)
        tree = self.QTaskTree(task)
        tree._params.child('x').setValue(99.)
        self.assertAlmostEqual(task.x, 99.)

    def test_editing_y_param_updates_attribute(self):
        task = AddTweezer(x=10., y=20.)
        tree = self.QTaskTree(task)
        tree._params.child('y').setValue(55.)
        self.assertAlmostEqual(task.y, 55.)

    def test_initialize_uses_updated_param_value(self):
        overlay = MagicMock()
        task = attached(AddTweezer(x=10., y=20.), overlay=overlay)
        tree = self.QTaskTree(task)
        tree._params.child('x').setValue(50.)
        tree._params.child('y').setValue(75.)
        task._start()
        task._step()
        args = overlay.addTrap.call_args[0]
        self.assertAlmostEqual(args[0].x(), 50.)
        self.assertAlmostEqual(args[0].y(), 75.)


class TestAddTweezerSerialization(unittest.TestCase):

    def test_to_dict_includes_type(self):
        task = AddTweezer(x=10., y=20.)
        d = task.toDict()
        self.assertEqual(d['type'], 'AddTweezer')

    def test_to_dict_includes_position(self):
        task = AddTweezer(x=10., y=20.)
        d = task.toDict()
        self.assertAlmostEqual(d['x'], 10.)
        self.assertAlmostEqual(d['y'], 20.)

    def test_round_trip(self):
        task = AddTweezer(x=100., y=150.)
        d = task.toDict()
        restored = QTask.fromDict(d)
        self.assertIsInstance(restored, AddTweezer)
        self.assertAlmostEqual(restored.x, 100.)
        self.assertAlmostEqual(restored.y, 150.)


if __name__ == '__main__':
    unittest.main()
