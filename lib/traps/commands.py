from __future__ import annotations

from pyqtgraph.Qt import QtGui, QtWidgets

# Qt 6: QUndoCommand/QUndoStack live in QtGui.
# Qt 5: they live in QtWidgets.
if hasattr(QtGui, 'QUndoStack'):
    QUndoCommand = QtGui.QUndoCommand
    QUndoStack = QtGui.QUndoStack
else:
    QUndoCommand = QtWidgets.QUndoCommand
    QUndoStack = QtWidgets.QUndoStack

from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.traps.QTweezer import QTweezer

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from QHOT.lib.traps.QTrapOverlay import QTrapOverlay


__all__ = ('QUndoCommand QUndoStack '
           'AddTrapCommand RemoveTrapCommand '
           'MoveCommand RotateCommand WheelCommand '
           'LockCommand').split()

_WHEEL_ID = 0xC0DE_0001


class AddTrapCommand(QUndoCommand):

    '''Undoable command to add a QTweezer at a given position.

    Parameters
    ----------
    overlay : QTrapOverlay
        The overlay that owns the trap.
    x : float
        x-coordinate of the new trap [pixels].
    y : float
        y-coordinate of the new trap [pixels].
    parent : QUndoCommand or None
        Optional parent command.
    '''

    def __init__(self, overlay: QTrapOverlay,
                 x: float, y: float,
                 parent: QUndoCommand | None = None) -> None:
        super().__init__('Add trap', parent)
        self._overlay = overlay
        self._trap = QTweezer(r=(x, y, 0.))

    def redo(self) -> None:
        '''Add the trap to the overlay.'''
        self._overlay._addTrap(self._trap)

    def undo(self) -> None:
        '''Remove the trap from the overlay.'''
        self._overlay._removeTrap(self._trap)


class RemoveTrapCommand(QUndoCommand):

    '''Undoable command to remove a top-level trap or group.

    Parameters
    ----------
    overlay : QTrapOverlay
        The overlay that owns the trap.
    group : QTrap
        The top-level trap or group to remove.
    parent : QUndoCommand or None
        Optional parent command.
    '''

    def __init__(self, overlay: QTrapOverlay,
                 group: QTrap,
                 parent: QUndoCommand | None = None) -> None:
        super().__init__('Remove trap', parent)
        self._overlay = overlay
        self._group = group

    def redo(self) -> None:
        '''Remove the trap from the overlay.'''
        self._overlay._removeTrap(self._group)

    def undo(self) -> None:
        '''Add the trap back to the overlay.'''
        self._overlay._addTrap(self._group)


class MoveCommand(QUndoCommand):

    '''Undoable command to move a trap group to a new position.

    The command is pre-executed: the group is already at its
    destination when the command is pushed.  The first call to
    ``redo()`` is a no-op.

    Parameters
    ----------
    group : QTrap
        The trap or group that was moved.
    origin : numpy array
        Position before the move (copy of ``group._r``).
    parent : QUndoCommand or None
        Optional parent command.
    '''

    def __init__(self, group: QTrap,
                 origin,
                 parent: QUndoCommand | None = None) -> None:
        super().__init__('Move trap', parent)
        self._group = group
        self._origin = origin.copy()
        self._destination = group._r.copy()
        self._first = True

    def redo(self) -> None:
        '''Restore the group to its destination (no-op on first call).'''
        if self._first:
            self._first = False
            return
        self._group.r = self._destination

    def undo(self) -> None:
        '''Restore the group to its origin.'''
        self._group.r = self._origin


class RotateCommand(QUndoCommand):

    '''Undoable command to rotate a trap group.

    The command is pre-executed: the group is already at its
    post-rotation positions when the command is pushed.  The first
    call to ``redo()`` is a no-op.

    Parameters
    ----------
    group : QTrapGroup
        The group that was rotated.
    snapshot_before : dict
        Position snapshot taken before the rotation gesture began,
        as returned by ``QTrapGroup._snapshot()``.
    parent : QUndoCommand or None
        Optional parent command.
    '''

    def __init__(self, group: QTrapGroup,
                 snapshot_before: dict,
                 parent: QUndoCommand | None = None) -> None:
        super().__init__('Rotate group', parent)
        self._group = group
        self._before = snapshot_before
        self._after = group._snapshot()
        self._first = True

    def redo(self) -> None:
        '''Restore the group to its post-rotation positions
        (no-op on first call).'''
        if self._first:
            self._first = False
            return
        self._group.rotate(0., self._after)

    def undo(self) -> None:
        '''Restore the group to its pre-rotation positions.'''
        self._group.rotate(0., self._before)


class WheelCommand(QUndoCommand):

    '''Undoable command to scroll a trap group along z.

    Consecutive wheel commands on the same group are merged so that
    a single undo reverses the entire scroll sequence.

    The command is pre-executed: the z-offset has already been applied
    when the command is pushed.  The first call to ``redo()`` is a
    no-op.

    Parameters
    ----------
    group : QTrap
        The trap or group that was scrolled.
    dz : float
        z increment that was applied (positive = away from objective).
    parent : QUndoCommand or None
        Optional parent command.
    '''

    def __init__(self, group: QTrap,
                 dz: float,
                 parent: QUndoCommand | None = None) -> None:
        super().__init__('Scroll trap z', parent)
        self._group = group
        self._dz = dz
        self._first = True

    def id(self) -> int:  # noqa: A003
        '''Return a stable integer ID to enable merging.'''
        return _WHEEL_ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        '''Merge a subsequent scroll on the same group into this command.

        Parameters
        ----------
        other : QUndoCommand
            The command to merge.

        Returns
        -------
        bool
            ``True`` if ``other`` was merged, ``False`` otherwise.
        '''
        if not isinstance(other, WheelCommand):
            return False
        if other._group is not self._group:
            return False
        self._dz += other._dz
        return True

    def redo(self) -> None:
        '''Scroll z forward by ``dz`` (no-op on first call).'''
        if self._first:
            self._first = False
            return
        new_r = self._group._r.copy()
        new_r[2] += self._dz
        self._group.r = new_r

    def undo(self) -> None:
        '''Scroll z back by ``dz``.'''
        new_r = self._group._r.copy()
        new_r[2] -= self._dz
        self._group.r = new_r


class LockCommand(QUndoCommand):

    '''Undoable command to toggle the locked state of a trap or group.

    Locking prevents a trap from being moved, scrolled, or rotated via
    mouse gestures.  The same command toggles back (undo = redo = toggle).

    Parameters
    ----------
    overlay : QTrapOverlay
        The overlay that owns the trap.
    group : QTrap
        The top-level trap or group whose locked state will be toggled.
    parent : QUndoCommand or None
        Optional parent command.
    '''

    def __init__(self, overlay: QTrapOverlay,
                 group: QTrap,
                 parent: QUndoCommand | None = None) -> None:
        text = 'Unlock trap' if group.locked else 'Lock trap'
        super().__init__(text, parent)
        self._overlay = overlay
        self._group = group

    def redo(self) -> None:
        '''Toggle the locked state.'''
        self._toggle()

    def undo(self) -> None:
        '''Toggle the locked state back.'''
        self._toggle()

    def _toggle(self) -> None:
        self._group.locked = not self._group.locked
        state = (self._overlay.State.STATIC if self._group.locked
                 else self._overlay.State.NORMAL)
        self._overlay._setGroupBrush(self._group, state)
