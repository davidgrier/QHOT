'''Unit tests for MoveTraps.'''
import math
import unittest

import numpy as np
from pyqtgraph.Qt import QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.MoveTraps import MoveTraps

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ------------------------------------------------------------------
# Test helpers

class FakeTrap:
    '''Minimal stand-in for QTrap: stores 3-D position as ndarray.'''

    def __init__(self, r=(0., 0., 0.)):
        self._r = np.array(r, dtype=float)

    @property
    def r(self):
        return self._r.copy()

    @r.setter
    def r(self, value):
        self._r[:] = value

    def leaves(self):
        yield self


class FakeOverlay:
    '''Minimal stand-in for QTrapOverlay: iterates over its traps.'''

    def __init__(self, *traps):
        self._traps = list(traps)

    def __iter__(self):
        return iter(self._traps)


# ------------------------------------------------------------------

class TestMoveTrapsInit(unittest.TestCase):

    def test_default_displacements_zero(self):
        task = MoveTraps()
        self.assertEqual(task.dx, 0.)
        self.assertEqual(task.dy, 0.)
        self.assertEqual(task.dz, 0.)

    def test_default_step(self):
        task = MoveTraps()
        self.assertEqual(task.step, 1.)

    def test_explicit_params_stored(self):
        task = MoveTraps(dx=10., dy=20., dz=5., step=2.)
        self.assertEqual(task.dx, 10.)
        self.assertEqual(task.dy, 20.)
        self.assertEqual(task.dz,  5.)
        self.assertEqual(task.step, 2.)

    def test_duration_keyword_raises(self):
        with self.assertRaises(TypeError):
            MoveTraps(dx=10., duration=5)

    def test_registered_in_registry(self):
        self.assertIn('MoveTraps', QTask._registry)

    def test_parameters_declared(self):
        names = [p['name'] for p in MoveTraps.parameters]
        self.assertIn('dx',   names)
        self.assertIn('dy',   names)
        self.assertIn('dz',   names)
        self.assertIn('step', names)

    def test_initial_state_pending(self):
        self.assertEqual(MoveTraps().state, QTask.State.PENDING)


class TestMoveTrapsDuration(unittest.TestCase):

    def test_zero_displacement_gives_duration_one(self):
        task = MoveTraps(dx=0., dy=0., dz=0.)
        self.assertEqual(task.duration, 1)

    def test_dx_only_duration(self):
        task = MoveTraps(dx=10., step=2.)
        self.assertEqual(task.duration, 5)

    def test_dy_only_duration(self):
        task = MoveTraps(dy=9., step=3.)
        self.assertEqual(task.duration, 3)

    def test_dz_only_duration(self):
        task = MoveTraps(dz=7., step=2.)
        self.assertEqual(task.duration, 4)   # ceil(7/2) = 4

    def test_3d_displacement_uses_l2_norm(self):
        dx, dy, dz, step = 3., 4., 0., 1.
        expected = math.ceil(math.sqrt(dx**2 + dy**2 + dz**2) / step)
        task = MoveTraps(dx=dx, dy=dy, dz=dz, step=step)
        self.assertEqual(task.duration, expected)

    def test_fractional_distance_rounds_up(self):
        task = MoveTraps(dx=5., step=3.)
        self.assertEqual(task.duration, 2)   # ceil(5/3) = 2

    def test_setting_dx_updates_duration(self):
        task = MoveTraps(dx=0., dy=0., dz=0., step=1.)
        task.dx = 10.
        self.assertEqual(task.duration, 10)

    def test_setting_dy_updates_duration(self):
        task = MoveTraps(step=2.)
        task.dy = 6.
        self.assertEqual(task.duration, 3)

    def test_setting_dz_updates_duration(self):
        task = MoveTraps(step=5.)
        task.dz = 10.
        self.assertEqual(task.duration, 2)

    def test_setting_step_updates_duration(self):
        task = MoveTraps(dx=10., step=1.)
        self.assertEqual(task.duration, 10)
        task.step = 5.
        self.assertEqual(task.duration, 2)

    def test_duration_minimum_is_one(self):
        task = MoveTraps(dx=0., step=1.)
        self.assertGreaterEqual(task.duration, 1)


class TestMoveTrapsExecution(unittest.TestCase):

    def setUp(self):
        self.trap = FakeTrap(r=(10., 20., 0.))
        self.overlay = FakeOverlay(self.trap)

    def _run(self, task):
        '''Start and step task to completion.'''
        task._start()
        for _ in range(task.duration):
            task._step()

    def test_initialize_records_start_positions(self):
        task = MoveTraps(overlay=self.overlay, dx=5.)
        task._start()
        task._step()          # calls initialize then process(0)
        self.assertIn(self.trap, task._starts)
        np.testing.assert_array_almost_equal(
            task._starts[self.trap], [10., 20., 0.])

    def test_final_position_equals_r0_plus_displacement(self):
        task = MoveTraps(overlay=self.overlay, dx=5., dy=-3., dz=2., step=1.)
        self._run(task)
        np.testing.assert_array_almost_equal(
            self.trap._r, [15., 17., 2.])

    def test_position_interpolates_linearly(self):
        task = MoveTraps(overlay=self.overlay, dx=10., step=5.)
        # duration = 2 frames; after frame 0 t=0.5, after frame 1 t=1.0
        task._start()
        task._step()          # initialize + process(0): t = 1/2
        np.testing.assert_array_almost_equal(
            self.trap._r, [15., 20., 0.])
        task._step()          # process(1): t = 2/2 = 1.0
        np.testing.assert_array_almost_equal(
            self.trap._r, [20., 20., 0.])

    def test_multiple_traps_all_moved(self):
        t1 = FakeTrap(r=(0., 0., 0.))
        t2 = FakeTrap(r=(10., 10., 0.))
        overlay = FakeOverlay(t1, t2)
        task = MoveTraps(overlay=overlay, dx=5., step=5.)
        self._run(task)
        np.testing.assert_array_almost_equal(t1._r, [5., 0., 0.])
        np.testing.assert_array_almost_equal(t2._r, [15., 10., 0.])

    def test_empty_overlay_does_not_raise(self):
        task = MoveTraps(overlay=FakeOverlay(), dx=5.)
        self._run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_completes_after_duration_frames(self):
        task = MoveTraps(overlay=self.overlay, dx=10., step=2.)
        self._run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_zero_displacement_completes_without_moving(self):
        task = MoveTraps(overlay=self.overlay, dx=0., dy=0., dz=0.)
        r_before = self.trap._r.copy()
        self._run(task)
        np.testing.assert_array_equal(self.trap._r, r_before)

    def test_finished_signal_emitted(self):
        task = MoveTraps(overlay=self.overlay, dx=5., step=5.)
        spy = QtTest.QSignalSpy(task.finished)
        self._run(task)
        self.assertEqual(len(spy), 1)


class TestMoveTrapsParamSync(unittest.TestCase):

    def setUp(self):
        from QHOT.lib.tasks.QTaskTree import QTaskTree
        self.QTaskTree = QTaskTree

    def test_editing_dx_updates_attribute_and_duration(self):
        task = MoveTraps(dx=0., step=1.)
        tree = self.QTaskTree(task)
        tree._params.child('dx').setValue(10.)
        self.assertAlmostEqual(task.dx, 10.)
        self.assertEqual(task.duration, 10)

    def test_editing_step_updates_duration(self):
        task = MoveTraps(dx=10., step=1.)
        tree = self.QTaskTree(task)
        tree._params.child('step').setValue(2.)
        self.assertAlmostEqual(task.step, 2.)
        self.assertEqual(task.duration, 5)


class TestMoveTrapsSerialization(unittest.TestCase):

    def test_to_dict_includes_type(self):
        d = MoveTraps(dx=5., dy=3., dz=1., step=2.).to_dict()
        self.assertEqual(d['type'], 'MoveTraps')

    def test_to_dict_includes_all_params(self):
        d = MoveTraps(dx=5., dy=3., dz=1., step=2.).to_dict()
        self.assertAlmostEqual(d['dx'],   5.)
        self.assertAlmostEqual(d['dy'],   3.)
        self.assertAlmostEqual(d['dz'],   1.)
        self.assertAlmostEqual(d['step'], 2.)

    def test_round_trip(self):
        task = MoveTraps(dx=5., dy=3., dz=1., step=2.)
        d = task.to_dict()
        restored = QTask.from_dict(d)
        self.assertIsInstance(restored, MoveTraps)
        self.assertAlmostEqual(restored.dx,   5.)
        self.assertAlmostEqual(restored.dy,   3.)
        self.assertAlmostEqual(restored.dz,   1.)
        self.assertAlmostEqual(restored.step, 2.)

    def test_round_trip_preserves_duration(self):
        task = MoveTraps(dx=5., dy=3., dz=1., step=2.)
        restored = QTask.from_dict(task.to_dict())
        self.assertEqual(restored.duration, task.duration)


if __name__ == '__main__':
    unittest.main()
