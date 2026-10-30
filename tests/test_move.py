'''Unit tests for Move.'''
import math
import unittest

import numpy as np
from pyqtgraph.Qt import QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.Move import Move

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ------------------------------------------------------------------
# Helpers (shared with test_movetraps.py pattern)

class FakeTrap:
    def __init__(self, r=(0., 0., 0.)):
        self._r = np.array(r, dtype=float)

    @property
    def r(self):
        return self._r.copy()

    @r.setter
    def r(self, value):
        self._r[:] = value


class FakeOverlay:
    def __init__(self, *traps):
        self._traps = list(traps)
        self.marked = list(traps)   # default: all traps marked

    def __iter__(self):
        return iter(self._traps)


def _run(task, max_steps=10_000):
    '''Step task to completion; duration may be set inside initialize().'''
    task._start()
    for _ in range(max_steps):
        task._step()
        if task.state != QTask.State.RUNNING:
            break


# ------------------------------------------------------------------
# Init

class TestMoveInit(unittest.TestCase):

    def test_default_target_zero(self):
        task = Move()
        self.assertEqual(task.x, 0.)
        self.assertEqual(task.y, 0.)
        self.assertEqual(task.z, 0.)

    def test_default_step(self):
        self.assertEqual(Move().step, 1.)

    def test_explicit_params_stored(self):
        task = Move(x=10., y=20., z=5., step=2.)
        self.assertEqual(task.x, 10.)
        self.assertEqual(task.y, 20.)
        self.assertEqual(task.z,  5.)
        self.assertEqual(task.step, 2.)

    def test_duration_keyword_raises(self):
        with self.assertRaises(TypeError):
            Move(x=10., duration=5)

    def test_registered_in_registry(self):
        self.assertIn('Move', QTask._registry)

    def test_parameters_declared(self):
        names = [p['name'] for p in Move.parameters]
        for name in ('x', 'y', 'z', 'step'):
            self.assertIn(name, names)

    def test_initial_state_pending(self):
        self.assertEqual(Move().state, QTask.State.PENDING)


# ------------------------------------------------------------------
# Execution

class TestMoveExecution(unittest.TestCase):

    def setUp(self):
        self.trap = FakeTrap(r=(10., 20., 0.))
        self.overlay = FakeOverlay(self.trap)

    def test_trap_reaches_target(self):
        task = Move(overlay=self.overlay, x=50., y=80., z=0., step=1.)
        _run(task)
        np.testing.assert_array_almost_equal(self.trap._r, [50., 80., 0.])

    def test_3d_target(self):
        task = Move(overlay=self.overlay, x=10., y=20., z=5., step=1.)
        _run(task)
        np.testing.assert_array_almost_equal(self.trap._r, [10., 20., 5.])

    def test_multiple_traps_maintain_relative_config(self):
        t1 = FakeTrap(r=(0.,  0., 0.))
        t2 = FakeTrap(r=(10., 0., 0.))
        overlay = FakeOverlay(t1, t2)
        # centroid = (5, 0, 0); target = (15, 0, 0); shift = (+10, 0, 0)
        task = Move(overlay=overlay, x=15., y=0., z=0., step=1.)
        _run(task)
        np.testing.assert_array_almost_equal(t1._r, [10.,  0., 0.])
        np.testing.assert_array_almost_equal(t2._r, [20.,  0., 0.])

    def test_no_marked_traps_completes_immediately(self):
        overlay = FakeOverlay(self.trap)
        overlay.marked = []
        task = Move(overlay=overlay, x=50., y=50.)
        task._start()
        task._step()   # initialize sets duration=0; _step completes it
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_no_marked_traps_does_not_move(self):
        overlay = FakeOverlay(self.trap)
        overlay.marked = []
        r_before = self.trap._r.copy()
        task = Move(overlay=overlay, x=50., y=50.)
        task._start()
        task._step()
        np.testing.assert_array_equal(self.trap._r, r_before)

    def test_target_already_at_current_position_completes(self):
        task = Move(overlay=self.overlay, x=10., y=20., z=0.)
        _run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_finished_signal_emitted(self):
        task = Move(overlay=self.overlay, x=20., y=20., step=10.)
        spy = QtTest.QSignalSpy(task.finished)
        _run(task)
        self.assertEqual(len(spy), 1)

    def test_duration_scales_with_displacement(self):
        trap = FakeTrap(r=(10., 20., 0.))
        overlay = FakeOverlay(trap)
        task = Move(overlay=overlay, x=10., y=30., z=0., step=2.)
        # centroid at (10, 20, 0), target at (10, 30, 0), displacement = 10
        task._start()
        task._step()   # calls initialize, which sets duration
        self.assertEqual(task.duration, math.ceil(10. / 2.))


# ------------------------------------------------------------------
# Serialization

class TestMoveSerialization(unittest.TestCase):

    def test_to_dict_includes_type(self):
        self.assertEqual(Move(x=5.).toDict()['type'], 'Move')

    def test_round_trip(self):
        task = Move(x=5., y=3., z=1., step=2.)
        restored = QTask.fromDict(task.toDict())
        self.assertIsInstance(restored, Move)
        self.assertAlmostEqual(restored.x,    5.)
        self.assertAlmostEqual(restored.y,    3.)
        self.assertAlmostEqual(restored.z,    1.)
        self.assertAlmostEqual(restored.step, 2.)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
