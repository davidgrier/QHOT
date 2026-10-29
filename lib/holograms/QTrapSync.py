from __future__ import annotations

import itertools
import logging
import weakref

import numpy as np
from qtpy import QtCore

from QHOT.lib.traps import QTrap, QTrapGroup


logger = logging.getLogger(__name__)

__all__ = ['QTrapSync']


def _plain(value: object) -> object:
    '''Return *value* as a plain Python number, if it is a NumPy scalar.'''
    return value.item() if isinstance(value, np.generic) else value


class QTrapSync(QtCore.QObject):

    '''Keep a CGH engine informed of the traps in an overlay.

    A CGH engine lives in a thread of its own and must never read the
    traps of the overlay, which the user changes at any moment from the
    GUI thread.  Instead, ``QTrapSync`` sends the engine a stream of
    messages that describe the traps, and the engine keeps a private
    replica of the trap tree that it computes from (see
    :meth:`~QHOT.lib.holograms.CGH.CGH.addReplica`).

    Every message is a signal carrying only plain, immutable data, so
    the engine sees a consistent state however fast the traps change.
    Qt delivers the messages of one sender to one receiver in the order
    in which they were sent, so a request to compute a hologram sent
    after a message always finds the engine updated by that message.
    When the engine lives in the thread of the sender, the messages are
    delivered at once, which is how the engine is used without threads.

    Connect :meth:`addTrap` and :meth:`removeTrap` to the ``trapAdded``
    and ``trapRemoved`` signals of the overlay.  Changes to the traps are
    followed from there on.

    Parameters
    ----------
    cgh : CGH
        The engine to inform.
    parent : QtCore.QObject or None
        Qt parent object.

    Signals
    -------
    added : Signal(object, object)
        A description of a new trap or group and the key of the group
        that contains it (``None`` for a top-level trap).
    removed : Signal(int)
        The key of a trap or group that was removed with its members.
    changed : Signal(int, object)
        The key of a trap or group and its new state.
    structureChanged : Signal(int, object)
        The key of a trap whose structure changed and its new state.
    '''

    added = QtCore.Signal(object, object)
    removed = QtCore.Signal(int)
    changed = QtCore.Signal(int, object)
    structureChanged = QtCore.Signal(int, object)

    def __init__(self, cgh, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._keys: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self._counter = itertools.count(1)
        self.added.connect(cgh.addReplica)
        self.removed.connect(cgh.removeReplica)
        self.changed.connect(cgh.updateReplica)
        self.structureChanged.connect(cgh.updateReplicaStructure)

    def keyOf(self, trap: QTrap) -> int | None:
        '''Return the key that identifies *trap* to the engine.

        Returns
        -------
        int or None
            The key, or ``None`` if the trap is not being followed.
        '''
        return self._keys.get(trap)

    def keysOf(self, traps) -> list[int]:
        '''Return the keys of those of *traps* that are being followed.'''
        keys = (self._keys.get(trap) for trap in traps)
        return [key for key in keys if key is not None]

    @QtCore.Slot(QTrap)
    def addTrap(self, trap: QTrap) -> None:
        '''Start following a trap or group and tell the engine about it.

        A trap that is a member of a group that is being followed is
        attached to that group in the engine, as it is in the overlay.
        '''
        parent = trap.parent()
        parentKey = self._keys.get(parent)
        self.removeTrap(trap)
        self.added.emit(self._describe(trap), parentKey)

    @QtCore.Slot(QTrap)
    def removeTrap(self, trap: QTrap) -> None:
        '''Stop following a trap or group and tell the engine.

        Does nothing if the trap is not being followed.
        '''
        key = self._keys.get(trap)
        if key is None:
            return
        for member in self._members(trap):
            self._untrack(member)
        self.removed.emit(key)

    def _members(self, trap: QTrap):
        '''Yield *trap* and, for a group, all that it contains.'''
        yield trap
        if isinstance(trap, QTrapGroup):
            for child in trap:
                yield from self._members(child)

    def _describe(self, trap: QTrap) -> dict:
        '''Follow *trap* and return a description of it and its members.'''
        key = self._track(trap)
        node = {'key': key,
                'type': type(trap).__name__,
                'settings': {name: _plain(value)
                             for name, value in trap.settings.items()}}
        if isinstance(trap, QTrapGroup):
            node['children'] = [self._describe(child) for child in trap]
        return node

    def _track(self, trap: QTrap) -> int:
        '''Give *trap* a key and listen for its changes.'''
        key = next(self._counter)
        self._keys[trap] = key
        trap.changed.connect(self._onChanged)
        if (not isinstance(trap, QTrapGroup)
                and hasattr(trap, 'structureChanged')):
            trap.structureChanged.connect(self._onStructureChanged)
        return key

    def _untrack(self, trap: QTrap) -> None:
        '''Stop listening to *trap*.'''
        self._keys.pop(trap, None)
        for signal, slot in ((trap.changed, self._onChanged),
                             (getattr(trap, 'structureChanged', None),
                              self._onStructureChanged)):
            if signal is None:
                continue
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                logger.debug('could not disconnect from %r', trap)

    def _positions(self, group: QTrapGroup) -> dict[int, tuple]:
        '''Return the position of a group and of each trap within it.'''
        return {self._keys[member]: tuple(float(v) for v in member._r)
                for member in self._members(group)
                if member in self._keys}

    @QtCore.Slot()
    def _onChanged(self) -> None:
        '''Send the new state of the trap that changed.

        A group moves all of its members without telling them, so a
        group sends the position of everything it contains.
        '''
        trap = self.sender()
        key = self._keys.get(trap)
        if key is None:
            return
        if isinstance(trap, QTrapGroup):
            state = {'positions': self._positions(trap)}
        else:
            state = self._state(trap)
        self.changed.emit(key, state)

    @QtCore.Slot()
    def _onStructureChanged(self) -> None:
        '''Send the new state of the trap whose structure changed.'''
        trap = self.sender()
        key = self._keys.get(trap)
        if key is not None:
            self.structureChanged.emit(key, self._state(trap))

    @staticmethod
    def _state(trap: QTrap) -> dict:
        '''Return the registered properties of *trap* as plain numbers.'''
        return {'settings': {name: _plain(value)
                             for name, value in trap.settings.items()}}
