import pyqtgraph as pg
from pyqtgraph import ScatterPlotItem
from pyqtgraph.Qt import QtCore, QtWidgets, QtGui
from pyqtgraph import mkBrush, mkPen
from QHOT.lib.traps.commands import QUndoStack  # re-exported from commands
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.commands import (
    AddTrapCommand, RemoveTrapCommand,
    MoveCommand, RotateCommand, WheelCommand)
from QHOT.traps import QTweezer
from enum import Enum
import json
import numpy as np
from collections.abc import Callable, Iterator
import functools
import operator
import logging


logger = logging.getLogger(__name__)


class QTrapOverlay(ScatterPlotItem):

    '''Graphical overlay for interacting with optical traps.

    Renders each trap as a colored scatter-plot spot and dispatches mouse
    events to trap operations (add, remove, select, drag, group, break).
    Traps and trap groups are Qt children of the overlay; iterating over
    the overlay yields its top-level QTrap/QTrapGroup children.

    Mouse gestures are configurable via the ``descriptions`` constructor
    argument, which maps (button, modifier) pairs to named handler methods.
    The default bindings are:

    =========================  ===========
    Gesture                    Action
    =========================  ===========
    Shift + left click         Add trap
    Ctrl + Shift + left click  Remove trap
    Alt + Shift + left click   Break group
    Alt + left drag            Rotate group
    Left drag (no modifier)    Move group
    Left drag (no target)      Rubber-band select / group
    Scroll wheel               Adjust trap z
    =========================  ===========

    The overlay supports two event-delivery modes:

    * **Standalone** – embedded directly in a ``pyqtgraph.PlotWidget``;
      Qt calls ``mousePressEvent`` / ``mouseMoveEvent`` /
      ``mouseReleaseEvent`` automatically.
    * **Hosted** – embedded in a ``QHOTScreen``; the screen calls
      ``mousePress`` / ``mouseMove`` / ``mouseRelease`` / ``wheel``
      explicitly with pre-transformed coordinates.

    Attributes
    ----------
    brush : dict[State, QBrush]
        Fill brushes keyed by visual state.
    button : dict[str, Qt.MouseButton]
        Mouse-button name → Qt enum mapping.
    modifier : dict[str, Qt.KeyboardModifier]
        Modifier name → Qt enum mapping (supports ``|``-separated combos).
    default : Descriptions
        Default gesture→handler bindings used when none are supplied.

    Signals
    -------
    trapAdded : QTrap
        Emitted with the top-level trap or group after it is added.
    trapRemoved : QTrap
        Emitted with the top-level trap or group after it is removed.
    '''

    #: Emitted with the trap when a trap is added to the scene.
    trapAdded = QtCore.pyqtSignal(QTrap)
    #: Emitted with the trap when a trap is removed from the scene.
    trapRemoved = QtCore.pyqtSignal(QTrap)

    class State(Enum):
        '''Visual state of a trap spot, controlling its fill color.'''
        STATIC = 0
        NORMAL = 1
        SELECTED = 2
        GROUPING = 3
        SPECIAL = 4

    brush: dict[State, QtGui.QBrush] = {
        State.STATIC: mkBrush(255, 255, 255, 120),
        State.NORMAL: mkBrush(100, 255, 100, 120),
        State.SELECTED: mkBrush(255, 105, 180, 120),
        State.GROUPING: mkBrush(255, 255, 100, 120),
        State.SPECIAL: mkBrush(238, 130, 238, 120)}

    button: dict[str, QtCore.Qt.MouseButton] = {
        'left': QtCore.Qt.MouseButton.LeftButton,
        'middle': QtCore.Qt.MouseButton.MiddleButton,
        'right': QtCore.Qt.MouseButton.RightButton}

    modifier: dict[str, QtCore.Qt.KeyboardModifier] = {
        'shift': QtCore.Qt.KeyboardModifier.ShiftModifier,
        'alt': QtCore.Qt.KeyboardModifier.AltModifier,
        'ctrl': QtCore.Qt.KeyboardModifier.ControlModifier,
        'meta': QtCore.Qt.KeyboardModifier.MetaModifier,
        'none': QtCore.Qt.KeyboardModifier.NoModifier}

    Signature = tuple[QtCore.Qt.MouseButton, QtCore.Qt.KeyboardModifier]
    Handler = Callable[[QtCore.QPointF], bool]
    Mapping = tuple[Signature, Handler]
    Description = tuple[tuple[str, str], str]
    Descriptions = tuple[Description, ...]

    default: Descriptions = ((('left', 'shift'), 'addTrap'),
                             (('left', 'ctrl|shift'), 'removeTrap'),
                             (('left', 'alt|shift'), 'breakGroup'),
                             (('left', 'alt'), 'startRotation'))

    def __init__(self, *args,
                 size: int = 16,
                 parent: QtCore.QObject | None = None,
                 descriptions: Descriptions = default,
                 **kwargs) -> None:
        '''Initialize the overlay.

        Parameters
        ----------
        descriptions : Descriptions
            Sequence of ``((button_name, modifier_name), handler_name)``
            tuples that map mouse gestures to trap operations.
            Defaults:
                shift+left → addTrap
                ctrl+shift+left → removeTrap
                alt+shift+left → breakGroup.
        *args, **kwargs
            Forwarded to ``ScatterPlotItem``.
        '''
        super().__init__(*args, size=size, **kwargs)
        self._setupUi()
        self._traps: list[QTrap] = []
        self._selected: QTrap | None = None
        self._move_origin = None
        self._drag_last: QtCore.QPointF | None = None
        self._selection_origin: QtCore.QPointF | None = None
        self._rotating: QTrapGroup | None = None
        self._rotation_center: tuple[float, float] = (0., 0.)
        self._rotation_angle0: float = 0.
        self._rotation_angle: float = 0.
        self._rotation_snapshot: dict = {}
        self._undoStack = QUndoStack()
        self._handler = dict(self._mapping(d) for d in descriptions)

    def __iter__(self) -> Iterator[QTrap]:
        '''Yield the top-level QTrap/QTrapGroup children of this overlay.

        Yields
        ------
        QTrap
            Each direct QTrap or QTrapGroup child of the overlay.
        '''
        for child in self.children():
            if isinstance(child, QTrap):
                yield child

    def _setupUi(self) -> None:
        '''Set up UI elements.

        Rubberband selection is hidden until used.
        '''
        self._selection = QtWidgets.QGraphicsRectItem(self)
        self._selection.setPen(mkPen('b', width=1, cosmetic=True,
                                     style=QtCore.Qt.PenStyle.DashLine))
        self._selection.setBrush(mkBrush(100, 100, 255, 30))
        self._selection.hide()

    def _mapping(self, description: Description) -> Mapping:
        '''Convert a description tuple to a (signature, handler) pair.

        Parameters
        ----------
        description : Description
            A ``((button_name, modifier_name), handler_name)`` tuple.

        Returns
        -------
        Mapping
            A ``(signature, handler)`` pair where signature is
            ``(Qt.MouseButton, Qt.KeyboardModifier)`` and handler is
            the bound method named by ``handler_name``.
        '''
        (bname, mname), hname = description
        button = self.button[bname]
        mods = [self.modifier[m] for m in mname.split('|')]
        modifiers = functools.reduce(operator.or_, mods)
        signature = (button, modifiers)
        handler = getattr(self, hname)
        return signature, handler

    # Operations on traps

    def _addTrap(self, traps: QTrap) -> None:
        '''Register a trap or group with the overlay (internal).

        Attaches ``traps`` as a Qt child of the overlay, registers all
        leaf spots, and emits ``trapAdded``.  Called directly by
        ``addTrap`` for programmatic additions, and by ``AddTrapCommand``
        and ``RemoveTrapCommand`` during undo/redo.

        Parameters
        ----------
        traps : QTrap
            A single trap or a group to register.
        '''
        traps.setParent(self)
        for trap in traps.leaves():
            trap._index = len(self._traps)
            self._traps.append(trap)
            spot = {'pos': (trap.x, trap.y),
                    'brush': self.brush[self.State.NORMAL],
                    'data': trap,
                    **trap.appearance()}
            self.addPoints([spot])
            trap.changed.connect(self._onTrapChanged)
        if hasattr(traps, 'reshaping'):
            traps.reshaping.connect(
                functools.partial(self._onGroupReshaping, traps))
            traps.reshaped.connect(
                functools.partial(self._onGroupReshaped, traps))
        if isinstance(traps, QTrapGroup):
            traps.changed.connect(self._onGroupChanged)
        self.trapAdded.emit(traps)

    def addTrap(self, traps: QTrap | list[QTrap] | QtCore.QPointF) -> bool:
        '''Register a trap or group with the overlay.

        When called as a mouse handler with a ``QPointF``, pushes an
        ``AddTrapCommand`` onto the undo stack so the operation can be
        undone.

        Parameters
        ----------
        traps : QTrap or list[QTrap] or QPointF
            A single trap or group, a list of traps, or a position at
            which to create a new ``QTweezer``.

        Returns
        -------
        bool
            ``True`` on success.
        '''
        if isinstance(traps, QtCore.QPointF):
            self._undoStack.push(
                AddTrapCommand(self, traps.x(), traps.y()))
            return True
        if isinstance(traps, list):
            for trap in traps:
                self._addTrap(trap)
            return True
        self._addTrap(traps)
        return True

    def _removeTrap(self, group: QTrap) -> None:
        '''Deregister a top-level trap or group from the overlay (internal).

        Disconnects signals, removes leaf spots, detaches the group from
        Qt's object hierarchy, and emits ``trapRemoved``.  Called by
        ``removeTrap`` for programmatic removal, and by
        ``RemoveTrapCommand`` and ``AddTrapCommand`` during undo/redo.

        Parameters
        ----------
        group : QTrap
            The top-level trap or group to remove.
        '''
        self.trapRemoved.emit(group)
        for t in list(group.leaves()):
            try:
                t.changed.disconnect(self._onTrapChanged)
            except (TypeError, RuntimeError):
                pass
            if t in self._traps:
                self._traps.remove(t)
            t._index = None
            t.setParent(None)
        if isinstance(group, QTrapGroup):
            try:
                group.changed.disconnect(self._onGroupChanged)
            except (TypeError, RuntimeError):
                pass
        group.setParent(None)
        self._rebuildSpots()

    def removeTrap(self, trap: QTrap | QtCore.QPointF) -> bool:
        '''Remove a trap from the overlay.

        If the trap belongs to a group, the entire group is removed.
        When called as a mouse handler with a ``QPointF``, pushes a
        ``RemoveTrapCommand`` onto the undo stack so the operation can
        be undone.

        Parameters
        ----------
        trap : QTrap or QPointF
            The trap to remove, or a position identifying the nearest trap.

        Returns
        -------
        bool
            ``True`` if a trap was removed, ``False`` if no trap was found.
        '''
        if isinstance(trap, QtCore.QPointF):
            pts = self.pointsAt(trap)
            if len(pts) == 0:
                return False
            group = self.groupOf(pts[0].data())
            self._undoStack.push(RemoveTrapCommand(self, group))
            return True
        self._removeTrap(self.groupOf(trap))
        return True

    def clearTraps(self) -> None:
        '''Remove all traps from the overlay and clear the undo stack.'''
        top_level = list(self)
        for trap in list(self._traps):
            trap.changed.disconnect(self._onTrapChanged)
            trap._index = None
        self._traps.clear()
        self.clear()
        for item in top_level:
            if isinstance(item, QTrapGroup):
                try:
                    item.changed.disconnect(self._onGroupChanged)
                except (TypeError, RuntimeError):
                    pass
            item.setParent(None)
            self.trapRemoved.emit(item)
        self._undoStack.clear()

    def _rebuildSpots(self) -> None:
        '''Rebuild all SpotItems after a removal, resequencing ``_index``.'''
        self.clear()
        spots = []
        for n, trap in enumerate(self._traps):
            trap._index = n
            spots.append({'pos': (trap.x, trap.y),
                          'brush': self.brush[self.State.NORMAL],
                          'data': trap,
                          **trap.appearance()})
        self.addPoints(spots)

    @staticmethod
    def groupOf(trap: QTrap) -> QTrap:
        '''Return the topmost parent of a trap, or the trap itself.

        Parameters
        ----------
        trap : QTrap
            A leaf trap or group.

        Returns
        -------
        QTrap
            The root of the group hierarchy containing ``trap``.
        '''
        while isinstance(trap.parent(), QTrapGroup):
            trap = trap.parent()
        return trap

    def _onGroupReshaping(self, group: QTrap) -> None:
        '''Disconnect old leaves and emit trapRemoved before repopulation.

        Called when a reshapeable group (e.g. QTrapArray) is about to
        discard its current tweezers.  Old leaves are still children of
        the group at this point, so ``group.leaves()`` returns them.

        Parameters
        ----------
        group : QTrap
            The group that is about to repopulate.
        '''
        for t in list(group.leaves()):
            try:
                t.changed.disconnect(self._onTrapChanged)
            except (TypeError, RuntimeError):
                pass
            if t in self._traps:
                self._traps.remove(t)
                t._index = None
        self.trapRemoved.emit(group)

    def _onGroupReshaped(self, group: QTrap) -> None:
        '''Connect new leaves and emit trapAdded after repopulation.

        Called after a reshapeable group has populated its new tweezers.
        New leaves are already children of the group at this point.

        Parameters
        ----------
        group : QTrap
            The group that has just repopulated.
        '''
        for t in group.leaves():
            t._index = len(self._traps)
            self._traps.append(t)
            t.changed.connect(self._onTrapChanged)
        self._rebuildSpots()
        self.trapAdded.emit(group)

    @QtCore.pyqtSlot()
    def _onTrapChanged(self) -> None:
        '''Slot called when a trap's position changes; updates its spot.'''
        trap: QTrap = self.sender()
        spot = self.points()[trap._index]
        spot._data['x'] = trap.x
        spot._data['y'] = trap.y
        spot.updateItem()

    @QtCore.pyqtSlot()
    def _onGroupChanged(self) -> None:
        '''Slot called when a group is translated; updates all leaf spots.'''
        group: QTrapGroup = self.sender()
        for trap in group.leaves():
            if trap._index is not None:
                spot = self.points()[trap._index]
                spot._data['x'] = trap.x
                spot._data['y'] = trap.y
                spot.updateItem()

    def _setGroupBrush(self, group: QTrap, state: State) -> None:
        '''Set the brush of every leaf spot in a group to the given state.

        Parameters
        ----------
        group : QTrap
            Root trap or group whose leaf spots will be updated.
        state : State
            Visual state to apply.
        '''
        for trap in group.leaves():
            if trap._index is not None:
                spot = self.points()[trap._index]
                spot.setBrush(self.brush[state])
                spot.updateItem()

    # Rubber-band selection

    def _finalizeSelection(self, rect: QtCore.QRectF) -> None:
        '''Group all top-level items that lie entirely within rect.

        A top-level group is included only if all of its leaf traps are
        inside ``rect``; groups that straddle the boundary are excluded.
        Emits ``trapRemoved`` for each absorbed top-level item and
        ``trapAdded`` for the resulting group.

        Parameters
        ----------
        rect : QRectF
            The completed rubber-band rectangle in item coordinates.
        '''
        candidates = [item for item in self if item.isWithin(rect)]
        if len(candidates) < 2:
            return
        for candidate in candidates:
            self.trapRemoved.emit(candidate)
        centroid = np.mean([t._r for t in candidates], axis=0)
        grp = QTrapGroup(r=centroid, parent=self)
        grp.addTrap(candidates)
        grp.changed.connect(self._onGroupChanged)
        self.trapAdded.emit(grp)

    def startSelection(self, pos: QtCore.QPointF) -> None:
        '''Begin a rubber-band selection anchored at pos.

        Parameters
        ----------
        pos : QPointF
            Anchor corner of the selection rectangle in item coordinates.
        '''
        self._selection_origin = pos
        self._selection.setRect(QtCore.QRectF(pos, QtCore.QSizeF(0., 0.)))
        self._selection.show()

    def growSelection(self, pos: QtCore.QPointF) -> None:
        '''Extend the rubber-band to pos, highlighting enclosed traps.

        Parameters
        ----------
        pos : QPointF
            Current cursor position in item coordinates.
        '''
        rect = QtCore.QRectF(self._selection_origin, pos).normalized()
        self._selection.setRect(rect)
        for item in self:
            state = (self.State.GROUPING if item.isWithin(rect)
                     else self.State.NORMAL)
            self._setGroupBrush(item, state)

    def endSelection(self) -> None:
        '''Finish the rubber-band selection and group the enclosed traps.'''
        rect = self._selection.rect()
        self._selection.hide()
        self._selection_origin = None
        for item in self:
            self._setGroupBrush(item, self.State.NORMAL)
        self._finalizeSelection(rect)

    # Identifying traps by position

    def trapAt(self, pos: QtCore.QPointF) -> QTrap | None:
        '''Return the trap nearest to a position.

        Parameters
        ----------
        pos : QPointF
            Query position in item coordinates.

        Returns
        -------
        QTrap or None
            Nearest trap, or ``None`` if no trap is nearby.
        '''
        pts = self.pointsAt(pos)
        if len(pts) == 0:
            return None
        return self._traps[pts[0].index()]

    def trapsIn(self, rect: QtCore.QRectF) -> list[QTrap]:
        '''Return all traps within a rectangle.

        Parameters
        ----------
        rect : QRectF
            Query rectangle in item coordinates.

        Returns
        -------
        list[QTrap]
            Traps whose spots fall within ``rect``, or ``[]`` if none.
        '''
        pts = self.pointsAt(rect)
        return [self._traps[p.index()] for p in pts]

    def groupAt(self, pos: QtCore.QPointF) -> QTrap | None:
        '''Return the topmost group containing the trap nearest to a position.

        Parameters
        ----------
        pos : QPointF
            Query position in item coordinates.

        Returns
        -------
        QTrap or None
            Root of the group hierarchy, or ``None`` if no trap is nearby.
        '''
        trap = self.trapAt(pos)
        if trap is None:
            return None
        return self.groupOf(trap)

    # Mouse action handlers (dispatched by Signature mapping)

    def breakGroup(self, pos: QtCore.QPointF) -> bool:
        '''Detach the clicked trap (or its subgroup) from its parent group.

        Emits ``trapRemoved`` and ``trapAdded`` as needed to keep
        observers (e.g. QTrapWidget) consistent with the new structure.

        Parameters
        ----------
        pos : QPointF
            Click position in item coordinates.

        Returns
        -------
        bool
            ``True`` if a trap was detached, ``False`` if no trap was found
            or the trap is not part of a group.
        '''
        trap = self.trapAt(pos)
        if trap is None:
            return False
        direct = trap.parent()
        if not isinstance(direct, QTrapGroup):
            return False
        outer = direct.parent()
        if isinstance(outer, QTrapGroup):
            self.trapRemoved.emit(outer)
            outer.removeTrap(direct)
            direct.setParent(self)
            direct.changed.connect(self._onGroupChanged)
            if not list(outer) and outer.parent() is self:
                outer.setParent(None)
            else:
                self.trapAdded.emit(outer)
            self.trapAdded.emit(direct)
        else:
            all_members = list(direct)
            self.trapRemoved.emit(direct)
            direct.removeTrap(trap)
            trap.setParent(self)
            remaining = [m for m in all_members if m is not trap]
            if len(remaining) == 1:
                sole = remaining[0]
                direct.removeTrap(sole)
                sole.setParent(self)
                direct.setParent(None)
                self.trapAdded.emit(sole)
            elif remaining:
                self.trapAdded.emit(direct)
            else:
                direct.setParent(None)
            self.trapAdded.emit(trap)
        return True

    def selectGroup(self, pos: QtCore.QPointF) -> bool:
        '''Select the trap group at pos for dragging.

        Parameters
        ----------
        pos : QPointF
            Click position in item coordinates.

        Returns
        -------
        bool
            ``True`` if a group was selected, ``False`` if no trap is nearby.
        '''
        pts = self.pointsAt(pos)
        if len(pts) == 0:
            return False
        trap = pts[0].data()
        self._selected = self.groupOf(trap)
        self._move_origin = self._selected._r.copy()
        self._setGroupBrush(self._selected, self.State.SELECTED)
        return True

    def startRotation(self, pos: QtCore.QPointF) -> bool:
        '''Begin rotating the group under the cursor around its center.

        If no trap is found at ``pos``, returns ``False`` to allow
        rubber-band fallback.  If the trap is ungrouped, returns ``True``
        but does not start rotation (Alt+drag on a lone trap is a no-op).

        Parameters
        ----------
        pos : QPointF
            Click position in item coordinates.

        Returns
        -------
        bool
            ``True`` if a trap was found (rotation started or no-op),
            ``False`` if no trap is nearby.
        '''
        trap = self.trapAt(pos)
        if trap is None:
            return False
        group = self.groupOf(trap)
        if not isinstance(group, QTrapGroup):
            return True
        cx, cy = group._r[0], group._r[1]
        self._rotating = group
        self._rotation_center = (cx, cy)
        self._rotation_angle0 = np.arctan2(pos.y() - cy, pos.x() - cx)
        self._rotation_snapshot = group._snapshot()
        self._setGroupBrush(group, self.State.SELECTED)
        return True

    # QGraphicsItem event overrides (used when embedded in a PlotWidget)

    def mousePressEvent(self, event) -> None:
        '''Handle press via QGraphicsItem dispatch (standalone / demo use).

        Parameters
        ----------
        event : QGraphicsSceneMouseEvent
            The mouse press event from Qt.
        '''
        signature = (event.button(), event.modifiers())
        handler = self._handler.get(signature, self.selectGroup)
        pos = event.pos()  # already in item coordinates
        if handler(pos):
            self._drag_last = pos
        else:
            self.startSelection(pos)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        '''Handle move via QGraphicsItem dispatch (standalone / demo use).

        Parameters
        ----------
        event : QGraphicsSceneMouseEvent
            The mouse move event from Qt.
        '''
        pos = event.pos()
        if self._rotating is not None:
            cx, cy = self._rotation_center
            angle_now = np.arctan2(pos.y() - cy, pos.x() - cx)
            angle = angle_now - self._rotation_angle0
            angle = (angle + np.pi) % (2. * np.pi) - np.pi
            self._rotation_angle = angle
            self._rotating.rotate(angle, self._rotation_snapshot)
        elif self._selected is not None and self._drag_last is not None:
            dx = pos.x() - self._drag_last.x()
            dy = pos.y() - self._drag_last.y()
            new_r = self._selected._r.copy()
            new_r[0] += dx
            new_r[1] += dy
            self._selected.r = new_r
            self._drag_last = pos
        elif self._selection.isVisible():
            self.growSelection(pos)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        '''Handle release via QGraphicsItem dispatch (standalone / demo use).

        Parameters
        ----------
        event : QGraphicsSceneMouseEvent
            The mouse release event from Qt.
        '''
        if self._selection.isVisible():
            self.endSelection()
        if self._rotating is not None:
            if abs(self._rotation_angle) > 1e-10:
                self._undoStack.push(
                    RotateCommand(self._rotating,
                                  self._rotation_snapshot))
            self._setGroupBrush(self._rotating, self.State.NORMAL)
            self._rotating = None
            self._rotation_snapshot = {}
            self._rotation_angle = 0.
        if self._selected is not None:
            if (self._move_origin is not None
                    and not np.allclose(self._selected._r,
                                        self._move_origin)):
                self._undoStack.push(
                    MoveCommand(self._selected, self._move_origin))
            self._setGroupBrush(self._selected, self.State.NORMAL)
        self._selected = None
        self._move_origin = None
        self._drag_last = None
        event.accept()

    # Event handlers (called by QHOTScreen)

    def mousePress(self, event: QtGui.QMouseEvent,
                   pos: QtCore.QPointF) -> bool:
        '''Handle a press event forwarded by QHOTScreen.

        Dispatches to the registered handler for the event's button/modifier
        signature, falling back to ``selectGroup``. Starts a rubber-band
        selection if no handler claims the event.

        Parameters
        ----------
        event : QtGui.QMouseEvent
            The original mouse event.
        pos : QPointF
            Cursor position in item coordinates.

        Returns
        -------
        bool
            Always ``True``.
        '''
        signature = (event.buttons(), event.modifiers())
        handler = self._handler.get(signature, self.selectGroup)
        if not handler(pos):
            self.startSelection(pos)
        else:
            self._drag_last = pos
        return True

    def mouseMove(self, event: QtGui.QMouseEvent,
                  pos: QtCore.QPointF) -> bool:
        '''Handle a move event forwarded by QHOTScreen.

        Drags the selected group when the left button is held, or grows the
        rubber-band selection if one is active. Ignores non-left-button moves.

        Parameters
        ----------
        event : QtGui.QMouseEvent
            The original mouse event.
        pos : QPointF
            Cursor position in item coordinates.

        Returns
        -------
        bool
            ``True`` if the event was handled, ``False`` otherwise.
        '''
        if event.buttons() != self.button['left']:
            return False
        if self._rotating is not None:
            cx, cy = self._rotation_center
            angle_now = np.arctan2(pos.y() - cy, pos.x() - cx)
            angle = angle_now - self._rotation_angle0
            angle = (angle + np.pi) % (2. * np.pi) - np.pi
            self._rotation_angle = angle
            self._rotating.rotate(angle, self._rotation_snapshot)
        elif self._selected is not None and self._drag_last is not None:
            dx = pos.x() - self._drag_last.x()
            dy = pos.y() - self._drag_last.y()
            new_r = self._selected._r.copy()
            new_r[0] += dx
            new_r[1] += dy
            self._selected.r = new_r
            self._drag_last = pos
        elif self._selection.isVisible():
            self.growSelection(pos)
        return True

    def mouseRelease(self, event: QtGui.QMouseEvent) -> bool:
        '''Handle a release event forwarded by QHOTScreen.

        Finalizes any active rubber-band selection, pushes undo commands
        for completed moves and rotations, and clears drag state.

        Parameters
        ----------
        event : QtGui.QMouseEvent
            The original mouse event.

        Returns
        -------
        bool
            Always ``True``.
        '''
        if self._selection.isVisible():
            self.endSelection()
        if self._rotating is not None:
            if abs(self._rotation_angle) > 1e-10:
                self._undoStack.push(
                    RotateCommand(self._rotating,
                                  self._rotation_snapshot))
            self._setGroupBrush(self._rotating, self.State.NORMAL)
            self._rotating = None
            self._rotation_snapshot = {}
            self._rotation_angle = 0.
        if self._selected is not None:
            if (self._move_origin is not None
                    and not np.allclose(self._selected._r,
                                        self._move_origin)):
                self._undoStack.push(
                    MoveCommand(self._selected, self._move_origin))
            self._setGroupBrush(self._selected, self.State.NORMAL)
        self._selected = None
        self._move_origin = None
        self._drag_last = None
        return True

    def wheel(self, event: QtGui.QWheelEvent,
              pos: QtCore.QPointF) -> bool:
        '''Handle a wheel event forwarded by QHOTScreen.

        Adjusts the z-coordinate of the nearest trap group by one step
        per notch of wheel rotation.

        Parameters
        ----------
        event : QtGui.QWheelEvent
            The original wheel event.
        pos : QPointF
            Cursor position in item coordinates.

        Returns
        -------
        bool
            ``True`` if a group was found and moved, ``False`` otherwise.
        '''
        group = self.groupAt(pos)
        if group is None:
            return False
        dz = event.angleDelta().y() / 120.
        new_r = group._r.copy()
        new_r[2] += dz
        group.r = new_r
        self._undoStack.push(WheelCommand(group, dz))
        return True

    # Serialization

    def _make_trap(self, d: dict) -> QTrap:
        '''Reconstruct a trap or group from a serialised dict.

        Parameters
        ----------
        d : dict
            A dict produced by ``QTrap.to_dict()`` or
            ``QTrapGroup.to_dict()``.

        Returns
        -------
        QTrap
            The reconstructed trap or group, with children attached.
        '''
        d = dict(d)
        trap_type = d.pop('type')
        children = d.pop('children', None)
        mask = d.pop('mask', None)
        r = (d.pop('x'), d.pop('y'), d.pop('z'))
        cls = QTrap._registry.get(trap_type)
        if cls is None:
            raise KeyError(f'Unknown trap type {trap_type!r}. '
                           f'Import its module before calling load().')

        kwargs: dict = {'r': r, **d}
        if mask is not None:
            kwargs['mask'] = np.array(mask, dtype=bool)
        if trap_type == 'QTrapArray':
            nx = int(kwargs.pop('nx'))
            ny = int(kwargs.pop('ny'))
            kwargs['shape'] = (nx, ny)
        trap = cls(**kwargs)
        if children is not None:
            for child_d in children:
                trap.addTrap(self._make_trap(child_d))
        return trap

    def save(self, path: str) -> None:
        '''Save all traps to a JSON file.

        Parameters
        ----------
        path : str
            Destination file path.
        '''
        data = [trap.to_dict() for trap in self]
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> None:
        '''Load traps from a JSON file, replacing the current configuration.

        Parameters
        ----------
        path : str
            Source file path produced by ``save()``.
        '''
        with open(path) as f:
            data = json.load(f)
        self.clearTraps()
        for d in data:
            self.addTrap(self._make_trap(d))

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Display an interactive trap overlay demo.

        Opens a plot window with several individual traps and a grouped
        triple of traps. Supports adding, removing, grouping, and
        dragging traps interactively.
        '''
        pg.mkQApp()

        win = pg.PlotWidget(title='QTrapOverlay Demo')
        win.setWindowTitle('QTrap Demo')
        win.setBackground('w')
        win.showGrid(x=True, y=True, alpha=0.3)

        overlay = cls(size=18, pen=pg.mkPen('k', width=1))

        positions = [(2., 3.), (4., 7.), (6., 2.),
                     (7., 6.), (3., 5.), (8., 4.)]
        for x, y in positions:
            overlay.addTrap(QTweezer(r=(x, y, 100.)))

        tg1 = QTweezer(r=(5., 5.5, 150.))
        tg2 = QTweezer(r=(4.1, 4.2, 150.))
        tg3 = QTweezer(r=(5.9, 4.2, 150.))
        grp = QTrapGroup(r=(5., 5., 150.))
        for t in (tg1, tg2, tg3):
            grp.addTrap(t)
        overlay.addTrap(grp)

        win.addItem(overlay)
        win.setXRange(0, 10)
        win.setYRange(0, 9)
        win.show()
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QTrapOverlay.example()
