'''The overlay on which the optical traps are shown, picked and moved.'''
import contextlib
import functools
import logging
from collections.abc import Iterator
from enum import Enum
from typing import Any, ClassVar, cast

from qtpy import QtCore, QtGui
import pyqtgraph as pg
from pyqtgraph import ScatterPlotItem
from pyqtgraph import mkBrush

from QHOT.lib.traps.commands import QUndoStack  # re-exported from commands
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.gestures import Gestures
from QHOT.lib.traps.grouping import break_group
from QHOT.lib.traps.trapspec import TrapSpec
from QHOT.lib.traps.commands import (
    AddTrapCommand, RemoveTrapCommand, LockCommand, PropertyCommand)
from QHOT.traps import QTweezer


logger = logging.getLogger(__name__)


class QTrapOverlay(ScatterPlotItem):

    '''Graphical overlay for interacting with optical traps.

    Renders each trap as a colored scatter-plot spot and dispatches mouse
    events to trap operations (add, remove, select, drag, group, break).
    Traps and trap groups are Qt children of the overlay; iterating over
    the overlay yields its top-level QTrap/QTrapGroup children.

    The mouse is handled by a :class:`~QHOT.lib.traps.gestures.Gestures`
    that the overlay owns (``gestures``) and forwards its events to.  The
    overlay supports two event-delivery modes:

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
    gestures : Gestures
        What the mouse does to the traps.

    Signals
    -------
    trapAdded : QTrap
        Emitted with the top-level trap or group after it is added.
    trapRemoved : QTrap
        Emitted with the top-level trap or group after it is removed.
    patternChanged : None
        Emitted when the hologram of the traps would change: a trap is
        added or removed, or a trap or a group changes.
    '''

    #: Emitted with the trap when a trap is added to the scene.
    trapAdded = QtCore.Signal(QTrap)
    #: Emitted with the trap when a trap is removed from the scene.
    trapRemoved = QtCore.Signal(QTrap)
    #: Emitted when anything changes that the hologram depends on.
    patternChanged = QtCore.Signal()

    class State(Enum):
        '''Visual state of a trap spot, controlling its fill color.'''
        STATIC = 0
        NORMAL = 1
        SELECTED = 2
        GROUPING = 3
        SPECIAL = 4

    brush: ClassVar[dict[State, QtGui.QBrush]] = {
        State.STATIC: mkBrush(255, 255, 255, 120),
        State.NORMAL: mkBrush(100, 255, 100, 120),
        State.SELECTED: mkBrush(255, 105, 180, 120),
        State.GROUPING: mkBrush(255, 255, 100, 120),
        State.SPECIAL: mkBrush(238, 130, 238, 120)}

    #: Height at which a marker is twice as large as in the focal plane
    #: [pixels].
    ZSCALE: float = 100.

    def __init__(self,
                 *args,
                 size: int = 16,
                 parent: QtCore.QObject | None = None,
                 **kwargs) -> None:
        '''Initialize the overlay.

        Parameters
        ----------
        *args, **kwargs
            Forwarded to ``ScatterPlotItem``.
        '''
        super().__init__(*args, size=size, **kwargs)
        self._traps: list[QTrap] = []
        self._marked: set[QTrap] = set()
        self._undoStack = QUndoStack()
        self.gestures = Gestures(self)
        # Putting traps in or taking them out, however it comes about
        # (adding, grouping, breaking a group), changes the pattern.
        self.trapAdded.connect(self.patternChanged)
        self.trapRemoved.connect(self.patternChanged)

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

    @property
    def undoStack(self) -> QUndoStack:
        '''The stack of undoable edits that the user has made.'''
        return self._undoStack

    @QtCore.Slot(object, str, float)
    def editTrap(self, trap: QTrap, name: str, value: float) -> None:
        '''Set a property of a trap, as the trap panel does, undoably.

        Parameters
        ----------
        trap : QTrap
            The trap or group that is edited.
        name : str
            Name of one of its registered properties.
        value : float
            The new value.  Nothing is done, and nothing is put on the
            undo stack, if the trap has it already.
        '''
        if getattr(trap, name) != value:
            self._undoStack.push(PropertyCommand(trap, name, value))

    def pattern(self) -> tuple[TrapSpec, ...]:
        '''Return a snapshot of the traps, as a pattern of specs.

        The pattern is a tuple of the specs of the top-level traps and
        groups, with all that the groups contain.  It is a plain value,
        and nothing that happens to the traps afterwards changes it, so it
        may be handed to the thread that computes the hologram.

        Returns
        -------
        tuple[TrapSpec, ...]
            The specs, in the order of the overlay.
        '''
        return tuple(trap.spec() for trap in self)

    # Operations on traps

    def _markerSize(self, trap: QTrap) -> float:
        '''Return the size of the marker of a trap [pixels].

        A focus out of the focal plane is defocused, and so is the marker:
        its size is that of the markers in the plane, ``size``, times
        :math:`1 + |z| / z_0` with the height :math:`z_0` of ``ZSCALE``.
        '''
        return self.opts['size'] * (1. + abs(trap.z) / self.ZSCALE)

    def _spot(self, trap: QTrap, brush: QtGui.QBrush) -> dict:
        '''Return the description of the marker of a trap.'''
        return {'pos': (trap.x, trap.y),
                'size': self._markerSize(trap),
                'brush': brush,
                'data': trap,
                **trap.appearance()}

    def _follow(self, spot, trap: QTrap) -> None:
        '''Move and resize the marker of a trap to where the trap is.'''
        spot._data['x'] = trap.x
        spot._data['y'] = trap.y
        spot._data['size'] = self._markerSize(trap)
        spot.updateItem()

    def _addTrap(self, traps: QTrap) -> None:
        '''Register a trap or group with the overlay (internal).

        Attaches ``traps`` as a Qt child of the overlay, registers all
        leaf spots, and emits ``trapAdded``.  :meth:`addTrap` calls it
        for a trap or a group, which is what the undo commands do.

        Parameters
        ----------
        traps : QTrap
            A single trap or a group to register.
        '''
        traps.setParent(self)
        brush_state = (self.State.STATIC if traps.locked
                       else self.State.NORMAL)
        for trap in traps.leaves():
            trap._index = len(self._traps)
            self._traps.append(trap)
            self.addPoints([self._spot(trap, self.brush[brush_state])])
            trap.changed.connect(self._onTrapChanged)
        if hasattr(traps, 'reshaping'):     # an array can change its shape
            array: Any = traps
            array.reshaping.connect(
                functools.partial(self._onGroupReshaping, traps))
            array.reshaped.connect(
                functools.partial(self._onGroupReshaped, traps))
        if isinstance(traps, QTrapGroup):
            self.watch(traps)
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
        Qt's object hierarchy, and emits ``trapRemoved``.  The members
        stay in the group, so that undoing the removal restores it.
        :meth:`removeTrap` calls it, which is what the undo commands do.

        Parameters
        ----------
        group : QTrap
            The top-level trap or group to remove.
        '''
        self._marked.discard(group)
        self.trapRemoved.emit(group)
        for t in list(group.leaves()):
            try:
                t.changed.disconnect(self._onTrapChanged)
            except (TypeError, RuntimeError):
                logger.debug(f'could not disconnect changed from {t!r}')
            if t in self._traps:
                self._traps.remove(t)
            t._index = None
        if isinstance(group, QTrapGroup):
            self.unwatch(group)
        group.setParent(None)
        self._rebuildSpots()
        self.patternChanged.emit()   # ``trapRemoved`` was emitted at the start

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
                self.unwatch(item)
            item.setParent(None)
            self.trapRemoved.emit(item)
        self._undoStack.clear()
        self.patternChanged.emit()

    def _rebuildSpots(self) -> None:
        '''Rebuild all SpotItems after a removal, resequencing ``_index``.'''
        self.clear()
        spots = []
        for n, trap in enumerate(self._traps):
            trap._index = n
            group = self.groupOf(trap)
            brush_state = (self.State.STATIC if group.locked
                           else self.State.NORMAL)
            spots.append(self._spot(trap, self.brush[brush_state]))
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
        while isinstance(parent := trap.parent(), QTrapGroup):
            trap = parent
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
            with contextlib.suppress(TypeError, RuntimeError):
                t.changed.disconnect(self._onTrapChanged)
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

    @QtCore.Slot()
    def _onTrapChanged(self) -> None:
        '''Slot called when a trap's position changes; updates its spot.'''
        trap = cast(QTrap, self.sender())
        self._follow(self.points()[trap._index], trap)
        self.patternChanged.emit()

    @QtCore.Slot()
    def _onGroupChanged(self) -> None:
        '''Slot called when a group is translated; updates all leaf spots.'''
        group = cast(QTrapGroup, self.sender())
        spots = self.points()
        for trap in group.leaves():
            if trap._index is not None:
                self._follow(spots[trap._index], trap)
        self.patternChanged.emit()

    def setGroupBrush(self, group: QTrap, state: State) -> None:
        '''Set the brush of every leaf spot in a group to the given state.

        The undo command of a lock calls it, and so do the gestures.

        Parameters
        ----------
        group : QTrap
            Root trap or group whose leaf spots will be updated.
        state : State
            Visual state to apply.
        '''
        spots = self.points()
        for trap in group.leaves():
            if trap._index is not None:
                spot = spots[trap._index]
                spot.setBrush(self.brush[state])
                spot.updateItem()

    def watch(self, group: QTrapGroup) -> None:
        '''Keep the spots of a top-level group where the group is.'''
        group.changed.connect(self._onGroupChanged)

    def unwatch(self, group: QTrapGroup) -> None:
        '''Stop keeping the spots of a group where the group is.'''
        with contextlib.suppress(TypeError, RuntimeError):
            group.changed.disconnect(self._onGroupChanged)

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

    # Mouse action handlers (the bindings of the gestures)

    def breakGroup(self, pos: QtCore.QPointF) -> bool:
        '''Take the clicked trap, or its subgroup, out of its group.

        See :func:`~QHOT.lib.traps.grouping.break_group`.

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
        return trap is not None and break_group(self, trap)

    # ------------------------------------------------------------------
    # Marking traps for task operations

    @property
    def marked(self) -> Iterator[QTrap]:
        '''Yield all leaf traps in marked groups.

        Yields
        ------
        QTrap
            Each leaf trap belonging to a group in the marked set.
        '''
        for group in self._marked:
            yield from group.leaves()

    @property
    def markedGroups(self) -> list[QTrap]:
        '''The marked traps and groups, each as a whole.

        A task that moves them moves the group, which keeps its own
        center, and not the traps of the group one by one.
        '''
        return list(self._marked)

    def mark(self, group: QTrap) -> None:
        '''Mark a top-level trap or group, and show it with the SPECIAL
        brush.'''
        self._marked.add(group)
        self.setGroupBrush(group, self.State.SPECIAL)

    def unmark(self, group: QTrap) -> None:
        '''Remove the mark of a top-level trap or group, if it has one.

        Its brush is ``STATIC`` if it is locked and ``NORMAL`` if not.
        '''
        if group in self._marked:
            self._marked.discard(group)
            self.setGroupBrush(group, self.State.STATIC if group.locked
                               else self.State.NORMAL)

    def toggleMark(self, pos: QtCore.QPointF) -> bool:
        '''Toggle the SPECIAL (marked) state of the group at pos.

        Marked groups are highlighted with the ``SPECIAL`` brush.
        Clicking a marked group a second time clears its mark.
        Used as the ``Ctrl+left`` mouse handler so the user can
        designate traps for scripted task operations.  A change of the
        structure of a marked group (:mod:`~QHOT.lib.traps.grouping`)
        clears its mark.

        Parameters
        ----------
        pos : QPointF
            Click position in item coordinates.

        Returns
        -------
        bool
            ``True`` if a trap was found, ``False`` otherwise.
        '''
        trap = self.trapAt(pos)
        if trap is None:
            return False
        group = self.groupOf(trap)
        if group in self._marked:
            self.unmark(group)
        else:
            self.mark(group)
        return True

    def toggleLock(self, pos: QtCore.QPointF) -> bool:
        '''Toggle the locked state of the trap group under the cursor.

        Locked traps are displayed with the ``STATIC`` (white) brush and
        cannot be moved, scrolled, or rotated.  Clicking again unlocks
        them.  If no trap is found at ``pos``, returns ``False``.

        Parameters
        ----------
        pos : QPointF
            Click position in item coordinates.

        Returns
        -------
        bool
            ``True`` if a trap was found (lock toggled), ``False``
            if no trap is nearby.
        '''
        trap = self.trapAt(pos)
        if trap is None:
            return False
        group = self.groupOf(trap)
        self._undoStack.push(LockCommand(self, group))
        return True

    # QGraphicsItem event overrides (used when embedded in a PlotWidget)

    def mousePressEvent(self, event) -> None:
        self.gestures.press(event, event.pos())
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self.gestures.move(event, event.pos())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.gestures.release(event)
        event.accept()

    # Event handlers (called by QHOTScreen)

    def mousePress(self,
                   event: QtGui.QMouseEvent,
                   pos: QtCore.QPointF) -> bool:
        '''Handle a press forwarded by QHOTScreen.

        See :meth:`~QHOT.lib.traps.gestures.Gestures.press`.
        '''
        return self.gestures.press(event, pos)

    def mouseMove(self, event: QtGui.QMouseEvent, pos: QtCore.QPointF) -> bool:
        '''Handle a move forwarded by QHOTScreen.

        See :meth:`~QHOT.lib.traps.gestures.Gestures.move`.
        '''
        return self.gestures.move(event, pos)

    def mouseRelease(self, event: QtGui.QMouseEvent) -> bool:
        '''Handle a release forwarded by QHOTScreen.

        See :meth:`~QHOT.lib.traps.gestures.Gestures.release`.
        '''
        return self.gestures.release(event)

    def wheel(self, event: QtGui.QWheelEvent, pos: QtCore.QPointF) -> bool:
        '''Handle a turn of the wheel forwarded by QHOTScreen.

        See :meth:`~QHOT.lib.traps.gestures.Gestures.wheel`.
        '''
        return self.gestures.wheel(event, pos)

    # Serialization

    def _makeTrap(self, d: dict) -> QTrap:
        '''Reconstruct a trap or group from a serialized dict.

        Parameters
        ----------
        d : dict
            A dict produced by ``QTrap.toDict()`` or
            ``QTrapGroup.toDict()``.

        Returns
        -------
        QTrap
            The reconstructed trap or group, with children attached.
        '''
        kind = d['type']
        cls = QTrap._registry.get(kind)
        if cls is None:
            message = (f'Unknown trap type {kind!r}. '
                       'Import its module before calling load().')
            logger.error(message)
            raise KeyError(message)
        trap = cls.fromDict(d)
        for child_d in d.get('children', []):
            trap.addTrap(self._makeTrap(child_d))
        return trap

    def toList(self) -> list[dict]:
        '''Serialize all traps to a list of plain dicts.

        Returns
        -------
        list[dict]
            One dict per top-level trap or group, as produced by
            ``QTrap.toDict()`` / ``QTrapGroup.toDict()``.
        '''
        return [trap.toDict() for trap in self]

    def fromList(self, data: list[dict]) -> None:
        '''Replace the current traps with those described by ``data``.

        Parameters
        ----------
        data : list[dict]
            A list of dicts as produced by ``toList()``.
        '''
        self.clearTraps()
        for d in data:
            self.addTrap(self._makeTrap(d))

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
