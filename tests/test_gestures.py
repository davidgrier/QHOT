'''Unit tests for the mouse gestures on the traps of an overlay.'''
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from qtpy import QtCore, QtWidgets

from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QHOT.lib.traps.gestures import Gestures, Rotation
from QHOT.traps.QTweezer import QTweezer


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

LEFT = QtCore.Qt.MouseButton.LeftButton
RIGHT = QtCore.Qt.MouseButton.RightButton
MOD = QtCore.Qt.KeyboardModifier
NONE = MOD.NoModifier


def point(x, y):
    return QtCore.QPointF(x, y)


def press(button=LEFT, modifiers=NONE):
    event = MagicMock()
    event.button.return_value = button
    event.modifiers.return_value = modifiers
    return event


def move(buttons=LEFT):
    event = MagicMock()
    event.buttons.return_value = buttons
    return event


def wheel(delta):
    event = MagicMock()
    event.angleDelta.return_value = QtCore.QPoint(0, delta)
    return event


def overlay_with(*traps):
    '''Return an overlay with these traps, that can say what is at a point.

    An overlay that is in no view cannot be asked, because Qt finds the
    spots under a point in pixels of the screen; this one finds the spots
    that are within one unit.
    '''
    overlay = QTrapOverlay()
    for trap in traps:
        overlay.addTrap(trap)
    overlay.pointsAt = lambda pos: [
        spot for spot in overlay.points()
        if abs(spot.pos().x() - pos.x()) < 1.
        and abs(spot.pos().y() - pos.y()) < 1.]
    return overlay


def pair():
    '''A group of two traps, centered on the origin.'''
    t1 = QTweezer(r=(4., 0., 0.), phase=0.)
    t2 = QTweezer(r=(-4., 0., 0.), phase=0.)
    group = QTrapGroup(r=(0., 0., 0.))
    group.addTrap([t1, t2])
    return group, t1, t2


def brushes(overlay):
    return [spot.brush() for spot in overlay.points()]


class TestTheOverlayOwnsItsGestures(unittest.TestCase):

    def test_there_is_one_per_overlay(self):
        a, b = QTrapOverlay(), QTrapOverlay()
        self.assertIsInstance(a.gestures, Gestures)
        self.assertIsNot(a.gestures, b.gestures)

    def test_nothing_is_going_on_at_first(self):
        gestures = QTrapOverlay().gestures
        self.assertIsNone(gestures.dragged)
        self.assertIsNone(gestures.dragLast)
        self.assertIsNone(gestures.rotation)
        self.assertIsNone(gestures.anchor)
        self.assertFalse(gestures.band.isVisible())


class TestPress(unittest.TestCase):

    '''A press does what its button and modifiers are bound to.'''

    def setUp(self):
        self.trap = QTweezer(r=(5., 5., 0.), phase=0.)
        self.overlay = overlay_with(self.trap)
        self.gestures = self.overlay.gestures

    def test_a_press_is_always_taken(self):
        self.assertTrue(self.overlay.mousePress(press(), point(50., 50.)))

    def test_shift_adds_a_trap(self):
        self.overlay.mousePress(press(modifiers=MOD.ShiftModifier),
                                point(20., 20.))
        self.assertEqual(len(list(self.overlay)), 2)

    def test_what_is_done_remembers_the_cursor(self):
        pos = point(20., 20.)
        self.overlay.mousePress(press(modifiers=MOD.ShiftModifier), pos)
        self.assertEqual(self.gestures.dragLast, pos)

    def test_ctrl_shift_removes_a_trap(self):
        self.overlay.mousePress(
            press(modifiers=MOD.ControlModifier | MOD.ShiftModifier),
            point(5., 5.))
        self.assertEqual(list(self.overlay), [])

    def test_alt_shift_breaks_a_group(self):
        group, t1, t2 = pair()
        overlay = overlay_with(group)
        pos = point(t1.x, t1.y)
        overlay.mousePress(
            press(modifiers=MOD.AltModifier | MOD.ShiftModifier), pos)
        self.assertEqual(len(list(overlay)), 2)

    def test_ctrl_alt_locks_a_trap(self):
        self.overlay.mousePress(
            press(modifiers=MOD.ControlModifier | MOD.AltModifier),
            point(5., 5.))
        self.assertTrue(self.trap.locked)

    def test_ctrl_marks_a_trap(self):
        self.overlay.mousePress(press(modifiers=MOD.ControlModifier),
                                point(5., 5.))
        self.assertEqual(self.overlay.markedGroups, [self.trap])

    def test_alt_begins_to_rotate_a_group(self):
        group, t1, t2 = pair()
        overlay = overlay_with(group)
        overlay.mousePress(press(modifiers=MOD.AltModifier),
                           point(t1.x, t1.y))
        rotation = overlay.gestures.rotation
        self.assertIsNotNone(rotation)
        self.assertIs(rotation.group, group)

    def test_a_plain_press_grabs_the_trap(self):
        self.overlay.mousePress(press(), point(5., 5.))
        self.assertIs(self.gestures.dragged, self.trap)

    def test_a_plain_press_on_nothing_begins_a_rubber_band(self):
        self.overlay.mousePress(press(), point(50., 50.))
        self.assertTrue(self.gestures.band.isVisible())
        self.assertIsNone(self.gestures.dragged)

    def test_the_standalone_event_does_the_same_and_is_accepted(self):
        event = press(modifiers=MOD.ShiftModifier)
        event.pos.return_value = point(20., 20.)
        self.overlay.mousePressEvent(event)
        self.assertEqual(len(list(self.overlay)), 2)
        event.accept.assert_called_once()


class TestGrab(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay = overlay_with(self.trap)
        self.gestures = self.overlay.gestures

    def test_nothing_under_the_cursor(self):
        self.assertFalse(self.gestures.grab(point(50., 50.)))
        self.assertIsNone(self.gestures.dragged)

    def test_a_trap_under_the_cursor(self):
        self.assertTrue(self.gestures.grab(point(5., 5.)))
        self.assertIs(self.gestures.dragged, self.trap)

    def test_it_remembers_where_the_group_was(self):
        self.gestures.grab(point(5., 5.))
        np.testing.assert_array_equal(self.gestures.dragOrigin, [5., 5., 0.])

    def test_it_is_the_whole_group_that_is_grabbed(self):
        group, t1, t2 = pair()
        overlay = overlay_with(group)
        overlay.gestures.grab(point(t1.x, t1.y))
        self.assertIs(overlay.gestures.dragged, group)

    def test_the_group_shows_that_it_is_selected(self):
        self.gestures.grab(point(5., 5.))
        self.assertEqual(self.overlay.points()[0].brush(),
                         self.overlay.brush[self.overlay.State.SELECTED])

    def test_a_locked_group_is_taken_but_not_grabbed(self):
        self.trap.locked = True
        self.assertTrue(self.gestures.grab(point(5., 5.)))
        self.assertIsNone(self.gestures.dragged)


class TestDrag(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay = overlay_with(self.trap)
        self.gestures = self.overlay.gestures
        self.overlay.mousePress(press(), point(5., 5.))

    def test_the_group_follows_the_cursor(self):
        self.overlay.mouseMove(move(), point(8., 9.))
        self.assertAlmostEqual(self.trap.x, 8.)
        self.assertAlmostEqual(self.trap.y, 9.)

    def test_the_height_does_not_change(self):
        self.overlay.mouseMove(move(), point(8., 9.))
        self.assertAlmostEqual(self.trap.z, 0.)

    def test_a_step_is_the_distance_since_the_last_one(self):
        self.overlay.mouseMove(move(), point(8., 9.))
        self.overlay.mouseMove(move(), point(10., 9.))
        self.assertAlmostEqual(self.trap.x, 10.)
        self.assertAlmostEqual(self.trap.y, 9.)

    def test_it_remembers_the_cursor(self):
        pos = point(8., 9.)
        self.overlay.mouseMove(move(), pos)
        self.assertEqual(self.gestures.dragLast, pos)

    def test_a_move_is_taken(self):
        self.assertTrue(self.overlay.mouseMove(move(), point(6., 6.)))

    def test_another_button_is_not_taken_and_moves_nothing(self):
        self.assertFalse(self.overlay.mouseMove(move(RIGHT), point(8., 9.)))
        self.assertAlmostEqual(self.trap.x, 5.)

    def test_the_standalone_event_does_the_same_and_is_accepted(self):
        event = move()
        event.pos.return_value = point(8., 9.)
        self.overlay.mouseMoveEvent(event)
        self.assertAlmostEqual(self.trap.x, 8.)
        event.accept.assert_called_once()


class TestRubberBand(unittest.TestCase):

    def setUp(self):
        self.overlay = QTrapOverlay()
        self.gestures = self.overlay.gestures

    def test_it_begins_at_the_press(self):
        pos = point(5., 5.)
        self.gestures.startSelection(pos)
        self.assertEqual(self.gestures.anchor, pos)
        self.assertTrue(self.gestures.band.isVisible())

    def test_it_stretches_to_the_cursor(self):
        self.gestures.startSelection(point(0., 0.))
        self.gestures.growSelection(point(5., 5.))
        rect = self.gestures.band.rect()
        self.assertAlmostEqual(rect.width(), 5.)
        self.assertAlmostEqual(rect.height(), 5.)

    def test_it_stretches_in_any_direction(self):
        self.gestures.startSelection(point(5., 5.))
        self.gestures.growSelection(point(1., 2.))
        rect = self.gestures.band.rect()
        self.assertAlmostEqual(rect.width(), 4.)
        self.assertAlmostEqual(rect.height(), 3.)

    def test_it_shows_the_traps_that_it_encloses(self):
        self.overlay.addTrap(QTrap(r=(3., 3., 0.), phase=0.))
        self.gestures.startSelection(point(0., 0.))
        self.gestures.growSelection(point(10., 10.))
        self.assertEqual(self.overlay.points()[0].brush(),
                         self.overlay.brush[self.overlay.State.GROUPING])

    def test_it_ends_hidden(self):
        self.gestures.startSelection(point(0., 0.))
        self.gestures.growSelection(point(5., 5.))
        self.gestures.endSelection()
        self.assertFalse(self.gestures.band.isVisible())
        self.assertIsNone(self.gestures.anchor)

    def test_it_ends_with_the_traps_in_their_own_color(self):
        self.overlay.addTrap(QTrap(r=(3., 3., 0.), phase=0.))
        self.gestures.startSelection(point(0., 0.))
        self.gestures.growSelection(point(10., 10.))
        self.gestures.endSelection()
        self.assertEqual(self.overlay.points()[0].brush(),
                         self.overlay.brush[self.overlay.State.NORMAL])

    def test_it_groups_the_traps_that_it_enclosed(self):
        for r in ((3., 3., 0.), (6., 6., 0.), (50., 50., 0.)):
            self.overlay.addTrap(QTrap(r=r, phase=0.))
        self.overlay.mousePress(press(), point(0., 0.))
        self.overlay.mouseMove(move(), point(10., 10.))
        self.overlay.mouseRelease(press())
        groups = [t for t in self.overlay if isinstance(t, QTrapGroup)]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(list(groups[0])), 2)

    def test_the_move_stretches_it_when_it_is_going_on(self):
        self.gestures.startSelection(point(0., 0.))
        pos = point(5., 5.)
        with patch.object(self.gestures, 'growSelection') as grow:
            self.overlay.mouseMove(move(), pos)
        grow.assert_called_once_with(pos)

    def test_the_release_ends_it_when_it_is_going_on(self):
        self.gestures.startSelection(point(0., 0.))
        with patch.object(self.gestures, 'endSelection') as end:
            self.overlay.mouseRelease(press())
        end.assert_called_once()


class TestRelease(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay = overlay_with(self.trap)
        self.gestures = self.overlay.gestures
        self.stack = self.overlay.undoStack

    def drag(self, to):
        self.overlay.mousePress(press(), point(5., 5.))
        self.overlay.mouseMove(move(), to)

    def test_a_release_is_taken(self):
        self.assertTrue(self.overlay.mouseRelease(press()))

    def test_nothing_is_grabbed_after_it(self):
        self.drag(point(8., 9.))
        self.overlay.mouseRelease(press())
        self.assertIsNone(self.gestures.dragged)
        self.assertIsNone(self.gestures.dragOrigin)
        self.assertIsNone(self.gestures.dragLast)

    def test_the_group_is_in_its_own_color_again(self):
        self.drag(point(8., 9.))
        self.overlay.mouseRelease(press())
        self.assertEqual(self.overlay.points()[0].brush(),
                         self.overlay.brush[self.overlay.State.NORMAL])

    def test_a_move_can_be_undone(self):
        self.drag(point(8., 9.))
        self.overlay.mouseRelease(press())
        self.assertEqual(self.stack.count(), 1)
        self.stack.undo()
        self.assertAlmostEqual(self.trap.x, 5.)
        self.assertAlmostEqual(self.trap.y, 5.)

    def test_a_press_that_moved_nothing_is_not_an_edit(self):
        self.drag(point(5., 5.))
        self.overlay.mouseRelease(press())
        self.assertEqual(self.stack.count(), 0)

    def test_a_release_with_nothing_going_on_changes_nothing(self):
        self.overlay.mouseRelease(press())
        self.assertEqual(self.stack.count(), 0)

    def test_the_standalone_event_does_the_same_and_is_accepted(self):
        self.drag(point(8., 9.))
        event = MagicMock()
        self.overlay.mouseReleaseEvent(event)
        self.assertIsNone(self.gestures.dragged)
        event.accept.assert_called_once()


class TestWheel(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(5., 5., 10.), phase=0.)
        self.overlay = overlay_with(self.trap)

    def test_nothing_under_the_cursor(self):
        self.assertFalse(self.overlay.wheel(wheel(120), point(50., 50.)))

    def test_a_trap_under_the_cursor(self):
        self.assertTrue(self.overlay.wheel(wheel(120), point(5., 5.)))

    def test_a_notch_up_is_a_step_up(self):
        self.overlay.wheel(wheel(120), point(5., 5.))
        self.assertAlmostEqual(self.trap.z, 11.)

    def test_a_notch_down_is_a_step_down(self):
        self.overlay.wheel(wheel(-120), point(5., 5.))
        self.assertAlmostEqual(self.trap.z, 9.)

    def test_the_position_in_the_plane_does_not_change(self):
        self.overlay.wheel(wheel(120), point(5., 5.))
        self.assertAlmostEqual(self.trap.x, 5.)
        self.assertAlmostEqual(self.trap.y, 5.)

    def test_the_whole_group_moves(self):
        group, t1, t2 = pair()
        overlay = overlay_with(group)
        overlay.wheel(wheel(120), point(t1.x, t1.y))
        self.assertAlmostEqual(group.z, 1.)
        self.assertAlmostEqual(t1.z, 1.)
        self.assertAlmostEqual(t2.z, 1.)

    def test_it_can_be_undone(self):
        self.overlay.wheel(wheel(120), point(5., 5.))
        self.overlay.undoStack.undo()
        self.assertAlmostEqual(self.trap.z, 10.)

    def test_a_locked_trap_is_taken_and_does_not_move(self):
        self.trap.locked = True
        self.assertTrue(self.overlay.wheel(wheel(120), point(5., 5.)))
        self.assertAlmostEqual(self.trap.z, 10.)
        self.assertEqual(self.overlay.undoStack.count(), 0)


class TestStartRotation(unittest.TestCase):

    def setUp(self):
        self.group, self.t1, self.t2 = pair()
        self.overlay = overlay_with(self.group)
        self.gestures = self.overlay.gestures

    def test_nothing_under_the_cursor(self):
        self.assertFalse(self.gestures.startRotation(point(99., 99.)))
        self.assertIsNone(self.gestures.rotation)

    def test_a_group_under_the_cursor(self):
        self.assertTrue(self.gestures.startRotation(point(4., 0.)))
        self.assertIs(self.gestures.rotation.group, self.group)

    def test_it_turns_about_the_center_of_the_group(self):
        self.gestures.startRotation(point(4., 0.))
        self.assertAlmostEqual(self.gestures.rotation.center[0], 0.)
        self.assertAlmostEqual(self.gestures.rotation.center[1], 0.)

    def test_it_measures_the_angle_from_the_cursor(self):
        self.gestures.startRotation(point(4., .5))
        self.assertAlmostEqual(self.gestures.rotation.angle0,
                               np.arctan2(.5, 4.))

    def test_it_records_where_the_traps_were(self):
        self.gestures.startRotation(point(4., 0.))
        snapshot = self.gestures.rotation.snapshot
        self.assertIn(id(self.t1), snapshot)
        self.assertIn(id(self.t2), snapshot)

    def test_the_group_shows_that_it_is_selected(self):
        self.gestures.startRotation(point(4., 0.))
        for trap in (self.t1, self.t2):
            self.assertEqual(
                self.overlay.points()[trap._index].brush(),
                self.overlay.brush[self.overlay.State.SELECTED])

    def test_it_is_the_outermost_group_that_turns(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(2., 0., 0.))
        leaf = QTweezer(r=(3., 0., 0.), phase=0.)
        inner.addTrap(leaf)
        outer.addTrap(inner)
        overlay = overlay_with(outer)
        overlay.gestures.startRotation(point(3., 0.))
        self.assertIs(overlay.gestures.rotation.group, outer)

    def test_a_trap_in_no_group_does_not_turn(self):
        lone = QTweezer(r=(50., 50., 0.), phase=0.)
        self.overlay.addTrap(lone)
        self.assertTrue(self.gestures.startRotation(point(50., 50.)))
        self.assertIsNone(self.gestures.rotation)

    def test_a_locked_group_does_not_turn(self):
        self.group.locked = True
        self.assertTrue(self.gestures.startRotation(point(4., 0.)))
        self.assertIsNone(self.gestures.rotation)


class TestRotation(unittest.TestCase):

    def setUp(self):
        self.group, self.t1, self.t2 = pair()
        self.overlay = overlay_with(self.group)
        self.gestures = self.overlay.gestures
        self.overlay.mousePress(press(modifiers=MOD.AltModifier),
                                point(4., 0.))

    def test_the_traps_turn_with_the_cursor(self):
        self.overlay.mouseMove(move(), point(0., 4.))
        np.testing.assert_array_almost_equal(self.t1.r[:2], [0., 4.])
        np.testing.assert_array_almost_equal(self.t2.r[:2], [0., -4.])

    def test_the_spots_follow_the_traps(self):
        self.overlay.mouseMove(move(), point(0., 4.))
        spot = self.overlay.points()[self.t1._index]
        self.assertAlmostEqual(spot._data['x'], 0., places=5)
        self.assertAlmostEqual(spot._data['y'], 4., places=5)

    def test_the_same_cursor_gives_the_same_turn(self):
        self.overlay.mouseMove(move(), point(0., 4.))
        r = self.t1.r
        self.overlay.mouseMove(move(), point(0., 4.))
        np.testing.assert_array_almost_equal(self.t1.r, r)

    def test_a_turn_is_never_more_than_a_half_circle(self):
        self.overlay.mouseMove(move(), point(-4., -0.001))
        self.assertLessEqual(abs(self.gestures.rotation.angle), np.pi)

    def test_nested_groups_turn_about_the_center_of_the_outer_one(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(2., 0., 0.))
        leaf = QTweezer(r=(2., 0., 0.), phase=0.)
        inner.addTrap(leaf)
        outer.addTrap(inner)
        overlay = overlay_with(outer)
        overlay.mousePress(press(modifiers=MOD.AltModifier), point(2., 0.))
        overlay.mouseMove(move(), point(0., 2.))
        np.testing.assert_array_almost_equal(inner.r[:2], [0., 2.])
        np.testing.assert_array_almost_equal(leaf.r[:2], [0., 2.])

    def test_the_release_ends_it(self):
        self.overlay.mouseMove(move(), point(0., 4.))
        self.overlay.mouseRelease(press())
        self.assertIsNone(self.gestures.rotation)

    def test_the_traps_are_in_their_own_color_again(self):
        self.overlay.mouseRelease(press())
        for trap in (self.t1, self.t2):
            self.assertEqual(
                self.overlay.points()[trap._index].brush(),
                self.overlay.brush[self.overlay.State.NORMAL])

    def test_a_rotation_can_be_undone(self):
        self.overlay.mouseMove(move(), point(0., 4.))
        self.overlay.mouseRelease(press())
        self.assertEqual(self.overlay.undoStack.count(), 1)
        self.overlay.undoStack.undo()
        np.testing.assert_array_almost_equal(self.t1.r[:2], [4., 0.])

    def test_a_press_that_turned_nothing_is_not_an_edit(self):
        self.overlay.mouseRelease(press())
        self.assertEqual(self.overlay.undoStack.count(), 0)


class TestARotationIsAValue(unittest.TestCase):

    def test_it_starts_unturned(self):
        group, _, _ = pair()
        rotation = Rotation(group, (0., 0.), 0., {})
        self.assertEqual(rotation.angle, 0.)


if __name__ == '__main__':
    unittest.main()
