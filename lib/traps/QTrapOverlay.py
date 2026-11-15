'''The overlay on which the optical traps are shown, picked and moved.'''
import contextlib
import logging
from collections.abc import Callable, Iterable, Iterator
from enum import Enum
from typing import Any, ClassVar, cast

from qtpy import QtCore, QtGui
from pyqtgraph import ScatterPlotItem
from pyqtgraph import mkBrush

from QHOT.lib.traps.commands import QUndoStack  # re-exported from commands
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.gestures import Gestures
from QHOT.lib.traps.trapspec import TrapSpec
from QHOT.lib.traps.commands import AddTrapCommand, PropertyCommand


logger = logging.getLogger(__name__)


class QTrapOverlay(ScatterPlotItem):

    '''The traps, shown as colored scatter-plot spots.

    Traps and trap groups are Qt children of the overlay; iterating over
    the overlay yields its top-level QTrap/QTrapGroup children.  The overlay
    keeps them, their spots and brushes, the marks and the undo stack.  What
    the mouse does to them is in a
    :class:`~QHOT.lib.traps.gestures.Gestures` that the overlay owns
    (``gestures``) and that the screen that hosts the overlay
    (:class:`~QHOT.lib.QHOTScreen.QHOTScreen`) gives the mouse events.

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
        '''Visual state of a trap spot, controlling its fill color.

        ``ACTIVE`` is a group that the mouse is moving or rotating, and
        ``MARKED`` one that is marked for the tasks; they are not alike on
        purpose, because a marked group is dragged too.  ``STATIC`` is a
        locked group, ``GROUPING`` one that a rubber band encloses, and
        ``NORMAL`` the rest.
        '''
        STATIC = 0
        NORMAL = 1
        ACTIVE = 2
        GROUPING = 3
        MARKED = 4

    brush: ClassVar[dict[State, QtGui.QBrush]] = {
        State.STATIC: mkBrush(255, 255, 255, 120),
        State.NORMAL: mkBrush(100, 255, 100, 120),
        State.ACTIVE: mkBrush(255, 105, 180, 120),
        State.GROUPING: mkBrush(255, 255, 100, 120),
        State.MARKED: mkBrush(80, 160, 255, 120)}

    #: Height at which a marker is twice as large as in the focal plane
    #: [pixels].
    ZSCALE: float = 100.

    def __init__(self, *args, size: int = 16, **kwargs) -> None:
        '''Initialize the overlay.

        Parameters
        ----------
        *args, **kwargs
            Forwarded to ``ScatterPlotItem``.
        '''
        super().__init__(*args, size=size, **kwargs)
        self._spots: dict[QTrap, int] = {}      # leaf: index of its spot
        self._watched: set[QTrapGroup] = set()  # top-level groups followed
        self._arrays: set[QTrapGroup] = set()   # groups that reshape
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

    def _followSpot(self, spot, trap: QTrap) -> None:
        '''Move and resize the marker of a trap to where the trap is.'''
        spot._data['x'] = trap.x
        spot._data['y'] = trap.y
        spot._data['size'] = self._markerSize(trap)
        spot.updateItem()

    def leaves(self) -> Iterator[QTrap]:
        '''Yield every trap that is not a group, in the order of the spots.'''
        for item in self:
            yield from item.leaves()

    def spotOf(self, trap: QTrap) -> Any:
        '''Return the spot that shows a leaf trap.'''
        return self.points()[self._spots[trap]]

    def refresh(self) -> None:
        '''Make the spots, and what follows the traps, agree with the traps.

        The traps and groups, which are Qt children of the overlay and of
        one another, are all that there is; the spots, and the signals that
        keep them where the traps are, follow from them.  Call it after
        anything that changes which traps are there or how they are grouped
        (the overlay does so itself when it adds or removes traps).  Every
        spot is shown at rest, as :meth:`restingState` says.
        '''
        leaves = list(self.leaves())
        top = {item for item in self if isinstance(item, QTrapGroup)}
        groups = list(self._groups())
        arrays = {group for group in groups if hasattr(group, 'reshaping')}
        spots = self._spots.keys()
        self._track(spots, leaves, 'changed', self._onTrapChanged)
        self._track(self._watched, top, 'changed', self._onGroupChanged)
        self._track(self._arrays, arrays, 'reshaping', self._onReshaping)
        self._track(self._arrays, arrays, 'reshaped', self._onReshaped)
        self._watched, self._arrays = top, arrays
        self._spots = {trap: n for n, trap in enumerate(leaves)}
        self.clear()
        self.addPoints([
            self._spot(trap,
                       self.brush[self.restingState(self.groupOf(trap))])
            for trap in leaves])

    @staticmethod
    def _track(before: Iterable[Any],
               after: Iterable[Any],
               signal: str,
               slot: Callable[[], None]) -> None:
        '''Connect the signal of each object that is new, and disconnect
        that of each that has gone (an object that is deleted has no
        connections left to disconnect).'''
        before, after = set(before), set(after)
        for gone in before - after:
            with contextlib.suppress(TypeError, RuntimeError):
                getattr(gone, signal).disconnect(slot)
        for new in after - before:
            getattr(new, signal).connect(slot)

    def _groups(self) -> Iterator[QTrapGroup]:
        '''Yield every group of the overlay, at any depth.'''
        pending = [item for item in self if isinstance(item, QTrapGroup)]
        while pending:
            group = pending.pop()
            yield group
            pending += [child for child in group
                        if isinstance(child, QTrapGroup)]

    def _addTrap(self, traps: QTrap) -> None:
        '''Add a trap or a group to the overlay (internal).

        It becomes a Qt child of the overlay, the spots are made again, and
        ``trapAdded`` is emitted.  :meth:`addTrap` calls it, which is what
        the undo commands do.

        Parameters
        ----------
        traps : QTrap
            A single trap or a group.
        '''
        traps.setParent(self)
        self.refresh()
        self.trapAdded.emit(traps)

    def addTrap(self, traps: QTrap | list[QTrap]) -> None:
        '''Add a trap or a group, or a list of them, to the overlay.

        This does not go on the undo stack: the undo commands call it.

        Parameters
        ----------
        traps : QTrap or list[QTrap]
            A single trap or group, or a list of them.
        '''
        items = traps if isinstance(traps, list) else [traps]
        for trap in items:
            trap.setParent(self)
        self.refresh()
        for trap in items:
            self.trapAdded.emit(trap)

    def addTweezer(self, x: float, y: float) -> None:
        '''Add a tweezer at a position, so that the user can undo it.

        Parameters
        ----------
        x, y : float
            Where to put it, in the coordinates of the overlay.
        '''
        self._undoStack.push(AddTrapCommand(self, x, y))

    def _removeTrap(self, group: QTrap) -> None:
        '''Remove a top-level trap or group from the overlay (internal).

        It stops being a Qt child of the overlay, the spots are made again,
        and ``trapRemoved`` is emitted.  The members stay in the group, so
        that undoing the removal restores it.  :meth:`removeTrap` calls it,
        which is what the undo commands do.

        Parameters
        ----------
        group : QTrap
            The top-level trap or group to remove.
        '''
        self._marked.discard(group)
        self.trapRemoved.emit(group)
        group.setParent(None)
        self.refresh()
        self.patternChanged.emit()   # ``trapRemoved`` was emitted at the start

    def removeTrap(self, trap: QTrap) -> None:
        '''Remove a trap from the overlay; if it belongs to a group, the
        whole group goes.

        This does not go on the undo stack: the undo commands call it.

        Parameters
        ----------
        trap : QTrap
            The trap or group to remove.
        '''
        self._removeTrap(self.groupOf(trap))

    def clearTraps(self) -> None:
        '''Remove all traps, and their marks, and clear the undo stack.'''
        top_level = list(self)
        self._marked.clear()
        for item in top_level:
            item.setParent(None)
        self.refresh()
        for item in top_level:
            self.trapRemoved.emit(item)
        self._undoStack.clear()
        self.patternChanged.emit()

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

    @QtCore.Slot()
    def _onReshaping(self) -> None:
        '''Say that the top-level item of an array is about to change.'''
        array = cast(QTrapGroup, self.sender())
        self.trapRemoved.emit(self.groupOf(array))

    @QtCore.Slot()
    def _onReshaped(self) -> None:
        '''Make the spots again, and say that the item has changed.'''
        array = cast(QTrapGroup, self.sender())
        self.refresh()
        self.trapAdded.emit(self.groupOf(array))

    @QtCore.Slot()
    def _onTrapChanged(self) -> None:
        '''Slot called when a trap's position changes; updates its spot.'''
        trap = cast(QTrap, self.sender())
        self._followSpot(self.spotOf(trap), trap)
        self.patternChanged.emit()

    @QtCore.Slot()
    def _onGroupChanged(self) -> None:
        '''Slot called when a group is translated; updates all leaf spots.'''
        group = cast(QTrapGroup, self.sender())
        spots = self.points()
        for trap in group.leaves():
            self._followSpot(spots[self._spots[trap]], trap)
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
            spot = spots[self._spots[trap]]
            spot.setBrush(self.brush[state])
            spot.updateItem()

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
        return pts[0].data()

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

    # ------------------------------------------------------------------
    # Marking traps for task operations

    @property
    def markedGroups(self) -> list[QTrap]:
        '''The marked traps and groups, each as a whole.

        A task that moves them moves the group, which keeps its own
        center, and not the traps of the group one by one.
        '''
        return list(self._marked)

    def restingState(self, group: QTrap) -> State:
        '''Return the state of a top-level trap or group at rest: ``MARKED``
        if it is marked, else ``STATIC`` if it is locked, else ``NORMAL``.

        What a gesture changes, it changes back to this, and not to
        ``NORMAL``, so that a marked group stays marked in the eyes of the
        user when it has been dragged.
        '''
        if group in self._marked:
            return self.State.MARKED
        return self.State.STATIC if group.locked else self.State.NORMAL

    def rest(self, group: QTrap) -> None:
        '''Show a top-level trap or group in its resting state.'''
        self.setGroupBrush(group, self.restingState(group))

    def mark(self, group: QTrap) -> None:
        '''Mark a top-level trap or group, and show it with the ``MARKED``
        brush.'''
        self._marked.add(group)
        self.rest(group)

    def unmark(self, group: QTrap) -> None:
        '''Remove the mark of a top-level trap or group, if it has one.

        Its brush is ``STATIC`` if it is locked and ``NORMAL`` if not.
        '''
        if group in self._marked:
            self._marked.discard(group)
            self.rest(group)

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
        self.addTrap([self._makeTrap(d) for d in data])
