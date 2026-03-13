from pyqtgraph.Qt import QtCore
from QFab.lib.traps.QTrap import QTrap
from collections.abc import Iterator
import numpy as np
import numpy.typing as npt
import logging


logger = logging.getLogger(__name__)


class QTrapGroup(QTrap):

    '''Trap composed of multiple traps or nested groups.

    Inherits
    --------
    QFab.lib.traps.QTrap

    Attributes
    ----------
    traps : list[QTrap]
        Direct children of this group (may include nested QTrapGroups).

    Methods
    -------
    addTrap(traps: QTrap | list[QTrap]) -> None
        Add one or more traps or groups as direct children.
    removeTrap(trap: QTrap) -> None
        Remove a direct child trap or group.
    leaves() -> Iterator[QTrap]
        Recursively yield all leaf traps in the subtree.

    Notes
    -----
    Iterating a ``QTrapGroup`` yields its direct children (which may
    themselves be groups). Use ``leaves()`` to iterate only the leaf
    traps at the bottom of the hierarchy.
    '''

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

    @QTrap.r.setter
    def r(self, r: npt.ArrayLike) -> None:
        new_r = np.asarray(r, dtype=float)
        delta = new_r - self._r
        with QtCore.QSignalBlocker(self):
            QTrap.r.fset(self, new_r)
        for trap in self:
            trap.r = trap._r + delta
        self.changed.emit()

    @property
    def traps(self) -> list[QTrap]:
        '''Returns the list of traps in the group.'''
        return list(self)

    def isWithin(self, rect: QtCore.QRectF) -> bool:
        '''Returns True if all traps are within the rectangle.'''
        return all(trap.isWithin(rect) for trap in self)

    @classmethod
    def example(cls) -> None:
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


if __name__ == '__main__':
    QTrapGroup.example()
