'''What the mouse does to the traps of an overlay.

A press, a drag and a release are one gesture, and a gesture has a state
while it lasts: the group that is dragged, the group that is rotated, the
rectangle of a rubber band.  The state is here, and the overlay keeps only
the traps.
'''
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
from pyqtgraph import mkBrush, mkPen

from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.commands import MoveCommand, RotateCommand, WheelCommand
from QHOT.lib.traps.grouping import group_within

if TYPE_CHECKING:
    from QHOT.lib.traps.QTrapOverlay import QTrapOverlay


__all__ = 'Gestures Rotation'.split()


@dataclass
class Rotation:

    '''A group that is turned about its center.

    Attributes
    ----------
    group : QTrapGroup
        The group.
    center : tuple[float, float]
        The center of the group when the rotation began.
    angle0 : float
        The angle of the cursor about the center when it began [rad].
    snapshot : dict
        The positions of the traps when it began (:meth:`QTrapGroup.snapshot`):
        each turn is made from these, and not from the last turn.
    angle : float
        How far the group is turned now [rad].
    '''

    group: QTrapGroup
    center: tuple[float, float]
    angle0: float
    snapshot: dict
    angle: float = 0.


class Gestures:

    '''The mouse gestures on the traps of an overlay.

    The overlay forwards what the window gives it, a press, a move, a
    release and a turn of the wheel, with the position of the cursor in
    its own coordinates.  A press that has a binding below does what the
    binding says; any other press grabs the group under the cursor, and a
    press on nothing begins a rubber band that groups the traps that it
    encloses.

    ===========================  ===========
    Gesture                      Action
    ===========================  ===========
    Shift + left click           Add trap
    Ctrl + Shift + left click    Remove trap
    Alt + Shift + left click     Break group
    Ctrl + Alt + left click      Lock / unlock trap
    Ctrl + left click            Mark / unmark trap
    Alt + left drag              Rotate group
    Left drag (no modifier)      Move group
    Left drag (no target)        Rubber-band select / group
    Scroll wheel                 Adjust trap z
    ===========================  ===========

    A move, a rotation and a turn of the wheel are put on the undo stack
    of the overlay when they end.

    Parameters
    ----------
    overlay : QTrapOverlay
        The overlay whose traps the gestures act on.

    Attributes
    ----------
    dragged : QTrap or None
        The group that is being moved.
    dragOrigin : numpy.ndarray or None
        Where the dragged group was when it was grabbed.
    dragLast : QPointF or None
        Where the cursor was at the last step of a gesture.
    rotation : Rotation or None
        The rotation that is going on.
    band : QGraphicsRectItem
        The rectangle of the rubber band, hidden unless one is going on.
    anchor : QPointF or None
        The corner of the rubber band that the press fixed.
    '''

    def __init__(self, overlay: QTrapOverlay) -> None:
        self.overlay = overlay
        self.dragged: QTrap | None = None
        self.dragOrigin: np.ndarray | None = None
        self.dragLast: QtCore.QPointF | None = None
        self.rotation: Rotation | None = None
        self.anchor: QtCore.QPointF | None = None
        self.band = QtWidgets.QGraphicsRectItem(overlay)
        self.band.setPen(mkPen(
            'b',
            width=1,
            cosmetic=True,
            style=QtCore.Qt.PenStyle.DashLine,
        ))
        self.band.setBrush(mkBrush(100, 100, 255, 30))
        self.band.hide()
        left = QtCore.Qt.MouseButton.LeftButton
        mod = QtCore.Qt.KeyboardModifier
        # (button, modifiers) of the press, and what it does
        self._handlers = {
            (left, mod.ShiftModifier): overlay.addTrap,
            (left, mod.ControlModifier | mod.ShiftModifier):
                overlay.removeTrap,
            (left, mod.AltModifier | mod.ShiftModifier): overlay.breakGroup,
            (left, mod.ControlModifier | mod.AltModifier):
                overlay.toggleLock,
            (left, mod.ControlModifier): overlay.toggleMark,
            (left, mod.AltModifier): self.startRotation,
        }

    # ------------------------------------------------------------------
    # The events

    def press(self, event: QtGui.QMouseEvent, pos: QtCore.QPointF) -> bool:
        '''Begin a gesture: do what the button and modifiers are bound to.

        A press that is not bound grabs the group under the cursor, and one
        that finds no trap begins a rubber band.

        Parameters
        ----------
        event : QMouseEvent
            The mouse event.
        pos : QPointF
            Cursor position in the coordinates of the overlay.

        Returns
        -------
        bool
            Always ``True``.
        '''
        signature = (event.button(), event.modifiers())
        handler = self._handlers.get(signature, self.grab)
        if handler(pos):
            self.dragLast = pos
        else:
            self.startSelection(pos)
        return True

    def move(self, event: QtGui.QMouseEvent, pos: QtCore.QPointF) -> bool:
        '''Carry a gesture on: turn, drag or stretch the rubber band.

        Parameters
        ----------
        event : QMouseEvent
            The mouse event.
        pos : QPointF
            Cursor position in the coordinates of the overlay.

        Returns
        -------
        bool
            ``False`` if a button other than the left one is down.
        '''
        if event.buttons() != QtCore.Qt.MouseButton.LeftButton:
            return False
        if self.rotation is not None:
            self._turn(self.rotation, pos)
        elif self.dragged is not None and self.dragLast is not None:
            self._drag(self.dragged, self.dragLast, pos)
            self.dragLast = pos
        elif self.band.isVisible():
            self.growSelection(pos)
        return True

    def release(self, event: QtGui.QMouseEvent) -> bool:
        '''End a gesture: group what the rubber band encloses, and put the
        move or the rotation on the undo stack.

        Parameters
        ----------
        event : QMouseEvent
            The mouse event.

        Returns
        -------
        bool
            Always ``True``.
        '''
        overlay = self.overlay
        if self.band.isVisible():
            self.endSelection()
        rotation, self.rotation = self.rotation, None
        if rotation is not None:
            if abs(rotation.angle) > 1e-10:
                overlay.undoStack.push(
                    RotateCommand(rotation.group, rotation.snapshot))
            overlay.rest(rotation.group)
        dragged, self.dragged = self.dragged, None
        if dragged is not None:
            origin = self.dragOrigin
            if origin is not None and not np.allclose(dragged.r, origin):
                overlay.undoStack.push(MoveCommand(dragged, origin))
            overlay.rest(dragged)
        self.dragOrigin = None
        self.dragLast = None
        return True

    def wheel(self, event: QtGui.QWheelEvent, pos: QtCore.QPointF) -> bool:
        '''Move the group under the cursor one step in z per notch.

        Parameters
        ----------
        event : QWheelEvent
            The wheel event.
        pos : QPointF
            Cursor position in the coordinates of the overlay.

        Returns
        -------
        bool
            ``True`` if there is a group under the cursor (a locked group
            does not move), ``False`` otherwise.
        '''
        group = self.overlay.groupAt(pos)
        if group is None:
            return False
        if group.locked:
            return True
        dz = event.angleDelta().y() / 120.
        r = group.r
        r[2] += dz
        group.r = r
        self.overlay.undoStack.push(WheelCommand(group, dz))
        return True

    # ------------------------------------------------------------------
    # The gestures that begin with a press

    def grab(self, pos: QtCore.QPointF) -> bool:
        '''Grab the group under the cursor, to drag it.

        A locked group is not grabbed.

        Parameters
        ----------
        pos : QPointF
            Cursor position in the coordinates of the overlay.

        Returns
        -------
        bool
            ``True`` if there is a trap under the cursor, ``False`` if not.
        '''
        group = self.overlay.groupAt(pos)
        if group is None:
            return False
        if group.locked:
            return True
        self.dragged = group
        self.dragOrigin = group.r
        self.overlay.setGroupBrush(group, self.overlay.State.ACTIVE)
        return True

    def startRotation(self, pos: QtCore.QPointF) -> bool:
        '''Begin to rotate the group under the cursor about its center.

        A trap that is in no group, and a locked group, are not rotated,
        and the press is still taken: dragging from them does nothing.

        Parameters
        ----------
        pos : QPointF
            Cursor position in the coordinates of the overlay.

        Returns
        -------
        bool
            ``True`` if there is a trap under the cursor, ``False`` if not
            (the press then begins a rubber band).
        '''
        group = self.overlay.groupAt(pos)
        if group is None:
            return False
        if not isinstance(group, QTrapGroup) or group.locked:
            return True
        x, y, _ = group.r
        self.rotation = Rotation(
            group=group,
            center=(x, y),
            angle0=np.arctan2(pos.y() - y, pos.x() - x),
            snapshot=group.snapshot(),
        )
        self.overlay.setGroupBrush(group, self.overlay.State.ACTIVE)
        return True

    def startSelection(self, pos: QtCore.QPointF) -> None:
        '''Begin a rubber band anchored at *pos*.

        Parameters
        ----------
        pos : QPointF
            Anchor corner of the rectangle in the coordinates of the
            overlay.
        '''
        self.anchor = pos
        self.band.setRect(QtCore.QRectF(pos, QtCore.QSizeF(0., 0.)))
        self.band.show()

    def growSelection(self, pos: QtCore.QPointF) -> None:
        '''Stretch the rubber band to *pos*, and show what it encloses.

        Parameters
        ----------
        pos : QPointF
            Current cursor position in the coordinates of the overlay.
        '''
        anchor = cast(QtCore.QPointF, self.anchor)
        rect = QtCore.QRectF(anchor, pos).normalized()
        self.band.setRect(rect)
        state = self.overlay.State
        for item in self.overlay:
            if item.isWithin(rect):
                self.overlay.setGroupBrush(item, state.GROUPING)
            else:
                self.overlay.rest(item)

    def endSelection(self) -> None:
        '''Hide the rubber band, and group the traps that it enclosed.'''
        rect = self.band.rect()
        self.band.hide()
        self.anchor = None
        for item in self.overlay:
            self.overlay.rest(item)
        group_within(self.overlay, rect)

    # ------------------------------------------------------------------
    # The steps of a drag

    @staticmethod
    def _drag(group: QTrap,
              last: QtCore.QPointF,
              pos: QtCore.QPointF) -> None:
        '''Move *group* by the distance that the cursor has gone.'''
        r = group.r
        r[0] += pos.x() - last.x()
        r[1] += pos.y() - last.y()
        group.r = r

    @staticmethod
    def _turn(rotation: Rotation, pos: QtCore.QPointF) -> None:
        '''Turn the group to the angle of the cursor about its center.'''
        cx, cy = rotation.center
        angle = np.arctan2(pos.y() - cy, pos.x() - cx) - rotation.angle0
        angle = (angle + np.pi) % (2. * np.pi) - np.pi
        rotation.angle = angle
        rotation.group.rotate(angle, rotation.snapshot)
