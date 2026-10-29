'''Private copies of traps for the thread that computes holograms.

A CGH engine that runs in a thread of its own cannot read the traps of
the overlay, which change under it.  It computes from replicas instead:
traps of the same kinds, built from the plain descriptions that
:class:`~QHOT.lib.holograms.QTrapSync.QTrapSync` sends, and owned by the
engine alone.  The replicas are real traps, so the engine caches their
fields and structures, and invalidates the caches when they change, just
as it does for the traps of an overlay.
'''
from __future__ import annotations

import logging
from collections.abc import Iterator

from QHOT.lib.traps import QTrap, QTrapGroup


logger = logging.getLogger(__name__)

__all__ = 'build walk apply'.split()


def build(node: dict, registry: dict[int, QTrap]) -> QTrap:
    '''Build the replica of a trap or group and of all that it contains.

    Parameters
    ----------
    node : dict
        Description of a trap, as sent by ``QTrapSync``: its ``key``,
        its class name as ``type``, its ``settings`` and, for a group,
        its ``children``.
    registry : dict[int, QTrap]
        Replicas by key.  Every replica built is entered here.

    Returns
    -------
    QTrap
        The replica.
    '''
    settings = node['settings']
    if 'children' in node:
        trap = QTrapGroup(r=(settings['x'], settings['y'], settings['z']))
        for child in node['children']:
            trap.addTrap(build(child, registry))
    else:
        trap = _leaf(node['type'], settings)
    trap._syncKey = node['key']
    registry[node['key']] = trap
    return trap


def _leaf(name: str, settings: dict) -> QTrap:
    '''Build a trap of class *name* with *settings*.'''
    cls = QTrap._registry.get(name)
    try:
        if cls is None:
            raise KeyError(name)
        return cls.from_dict({'type': name, **settings})
    except Exception:
        logger.warning(f'cannot replicate {name}; using a plain trap')
        r = (settings['x'], settings['y'], settings['z'])
        return QTrap(r=r, amplitude=settings['amplitude'],
                     phase=settings['phase'])


def walk(trap: QTrap) -> Iterator[QTrap]:
    '''Yield *trap* and, for a group, everything that it contains.'''
    yield trap
    if isinstance(trap, QTrapGroup):
        for child in trap:
            yield from walk(child)


def apply(trap: QTrap, settings: dict) -> None:
    '''Set the properties of *trap* without any signal being emitted.

    The caller emits the signal that tells the engine what kind of change
    this was, as the trap that is replicated did.
    '''
    trap.blockSignals(True)
    try:
        for name, value in settings.items():
            setattr(trap, name, value)
    finally:
        trap.blockSignals(False)
