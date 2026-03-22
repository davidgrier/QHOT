from pyqtgraph.Qt import QtCore
from QHOT.lib.traps.QTrap import QTrap
from collections.abc import Iterator
import numpy as np
import numpy.typing as npt
import logging


logger = logging.getLogger(__name__)


class QTrapGroup(QTrap):

    '''Trap composed of multiple traps or nested groups.

    Subclass of ``QTrap``. Iterating a ``QTrapGroup`` yields its direct
    children, which may themselves be groups. Use ``leaves()`` to
    iterate only the leaf traps at the bottom of the hierarchy.

    Attributes
    ----------
    traps : list[QTrap]
        Direct children of this group (may include nested QTrapGroups).

    Signals
    -------
    groupMoved : QtCore.pyqtSignal(object, object)
        Emitted when the group is translated. Carries the list of all
        leaf traps in the subtree and the translation delta as an
        ``np.ndarray``. Emitted before the individual leaf ``changed``
        signals so that observers can perform bulk invalidation.
    '''

    #: Emitted with (leaves, delta) when the group is translated.
    groupMoved = QtCore.pyqtSignal(object, object)

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __iter__(self) -> Iterator[QTrap]:
        for child in self.children():
            if isinstance(child, QTrap):
                yield child

    def leaves(self) -> Iterator[QTrap]:
        '''Recursively yield all leaf QTraps in this group.

        Yields
        ------
        QTrap
            Each leaf (non-group) trap in the subtree rooted here.
        '''
        for child in self:
            yield from child.leaves()

    def __repr__(self) -> str:
        name = type(self).__name__
        x, y, z = self._r
        return (f'{name}(r=({x:.1f}, {y:.1f}, {z:.1f}), '
                f'ntraps={len(self)})')

    def addTrap(self, traps: QTrap) -> None:
        '''Adds one or more traps or groups to this group.

        Parameters
        ----------
        traps : QTrap or list[QTrap]
            A single trap or group, or a list of traps/groups.
            Each item is added as a direct child of this group.
        '''
        if isinstance(traps, list):
            for trap in traps:
                self.addTrap(trap)
        else:
            traps.setParent(self)

    def removeTrap(self, trap: QTrap) -> None:
        '''Removes a trap from the group.'''
        if trap.parent() is self:
            trap.setParent(None)

    def _translateSilently(self, delta: np.ndarray) -> None:
        '''Translate this node and all descendants by delta without emitting signals.'''
        self._r += delta
        for child in self:
            if isinstance(child, QTrapGroup):
                child._translateSilently(delta)
            else:
                child._r += delta

    @QTrap.r.setter
    def r(self, r: npt.ArrayLike) -> None:
        '''Translate the group so its center moves to ``r``.

        Moves the group node and all descendants by the same delta,
        emits ``groupMoved`` for bulk cache invalidation, then emits
        ``changed`` on every leaf and on the group itself.
        '''
        new_r = np.asarray(r, dtype=float)
        delta = new_r - self._r
        leaves = list(self.leaves())
        self._translateSilently(delta)
        self.groupMoved.emit(leaves, delta)
        for leaf in leaves:
            leaf.changed.emit()
        self.changed.emit()

    def to_dict(self) -> dict:
        '''Serialise this group and all its children to a plain dict.

        Returns
        -------
        dict
            A dict with ``'type'``, the registered properties, and a
            ``'children'`` list of recursively serialised child traps.
        '''
        d = {'type': type(self).__name__, **self.settings}
        d['children'] = [child.to_dict() for child in self]
        return d

    @property
    def traps(self) -> list[QTrap]:
        '''Returns the list of traps in the group.'''
        return list(self)

    def isWithin(self, rect: QtCore.QRectF) -> bool:
        '''Returns True if all traps are within the rectangle.'''
        return all(trap.isWithin(rect) for trap in self)

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Demonstrate group construction, translation, and removal.'''
        group = cls()
        print(len(group))
        a = QTrap(r=(1, 2, 3))
        b = QTrap(r=(10, 20, 30))
        group.addTrap([a, b])
        print(group)
        group.r = (100, 200, 300)
        group.removeTrap(b)
        print(group)
        for trap in group:
            print(trap)


if __name__ == '__main__':  # pragma: no cover
    QTrapGroup.example()
