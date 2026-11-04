'''The tasks that move traps move a group as a whole.

A group keeps its own center.  A task that moved the traps of a group one
by one left the center where it was, and an array, whose traps are made
again from its center when it is saved and loaded, went back.
'''
import unittest

import numpy as np
from qtpy import QtWidgets

from QHOT.lib.traps import QTrapOverlay
from QHOT.tasks import Move, MoveTraps
from QHOT.traps import QTrapArray, QTweezer

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def run(task):
    task._start()
    for _ in range(10_000):
        if task.state is not task.State.RUNNING:
            break
        task._step()


def centroid(group):
    return np.mean([trap.r for trap in group.leaves()], axis=0)


class MovingCase(unittest.TestCase):

    def setUp(self):
        self.overlay = QTrapOverlay()
        self.array = QTrapArray(
            shape=(2, 2),
            separation=20.,
            r=(100., 100., 0.),
        )
        self.overlay.addTrap(self.array)


class TestMoveTraps(MovingCase):

    def test_the_center_of_an_array_moves_with_it(self):
        run(attached(MoveTraps(dx=50., step=10.), overlay=self.overlay))
        np.testing.assert_allclose(self.array.r, [150., 100., 0.])
        np.testing.assert_allclose(centroid(self.array), self.array.r)

    def test_a_moved_array_is_saved_where_it_is(self):
        run(attached(MoveTraps(dx=50., step=10.), overlay=self.overlay))
        loaded = QTrapArray.fromDict(self.array.toDict())
        np.testing.assert_allclose(centroid(loaded), [150., 100., 0.])

    def test_a_single_trap_moves(self):
        trap = QTweezer(r=(10., 20., 0.))
        self.overlay.addTrap(trap)
        run(attached(MoveTraps(dy=5., step=1.), overlay=self.overlay))
        np.testing.assert_allclose(trap.r, [10., 25., 0.])

    def test_selected_only_moves_the_marked_group_and_not_the_rest(self):
        trap = QTweezer(r=(10., 20., 0.))
        self.overlay.addTrap(trap)
        self.overlay._marked.add(self.array)
        task = MoveTraps(dx=50., step=10., selected_only=True)
        run(attached(task, overlay=self.overlay))
        np.testing.assert_allclose(self.array.r, [150., 100., 0.])
        np.testing.assert_allclose(trap.r, [10., 20., 0.])


class TestMove(MovingCase):

    def test_the_marked_array_arrives_at_the_target_with_its_center(self):
        self.overlay._marked.add(self.array)
        run(attached(Move(x=200., y=50., step=10.), overlay=self.overlay))
        np.testing.assert_allclose(centroid(self.array), [200., 50., 0.])
        np.testing.assert_allclose(self.array.r, [200., 50., 0.])

    def test_a_moved_array_is_saved_where_it_is(self):
        self.overlay._marked.add(self.array)
        run(attached(Move(x=200., y=50., step=10.), overlay=self.overlay))
        loaded = QTrapArray.fromDict(self.array.toDict())
        np.testing.assert_allclose(centroid(loaded), [200., 50., 0.])


class TestMarkedGroups(MovingCase):

    def test_the_marked_groups_are_the_groups_not_their_traps(self):
        self.overlay._marked.add(self.array)
        self.assertEqual(self.overlay.markedGroups, [self.array])
        self.assertEqual(len(list(self.overlay.marked)), 4)

    def test_nothing_is_marked_at_first(self):
        self.assertEqual(self.overlay.markedGroups, [])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
