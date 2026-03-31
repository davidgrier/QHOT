from qtpy import QtCore
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.types import Displacement
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

    def _translateSilently(self, delta: Displacement) -> None:
        '''Translate this node and all descendants by delta
        without emitting signals.'''
        self._r += delta
        for child in self:
            if isinstance(child, QTrapGroup):
                child._translateSilently(delta)
            else:
                child._r += delta

    def _snapshot(self) -> dict:
        '''Record current positions of all descendants, keyed by id.

        Returns
        -------
        dict
            Mapping of ``id(child)`` to a copy of ``child._r`` for
            every direct child and all deeper descendants.
        '''
        s = {}
        for child in self:
            s[id(child)] = child._r.copy()
            if isinstance(child, QTrapGroup):
                s.update(child._snapshot())
        return s

    def _rotateSilently(self, angle: float,
                        cx: float, cy: float,
                        snapshot: dict) -> None:
        '''Rotate all descendants around (cx, cy) using snapshot positions.

        Updates ``_r`` in place without emitting any signals.

        Parameters
        ----------
        angle : float
            Rotation angle in radians.
        cx, cy : float
            Center of rotation in item coordinates.
        snapshot : dict
            Mapping of ``id(child)`` to initial position, as returned
            by ``_snapshot()``.
        '''
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)
        for child in self:
            orig = snapshot[id(child)]
            dx = orig[0] - cx
            dy = orig[1] - cy
            child._r[0] = cx + cos_a * dx - sin_a * dy
            child._r[1] = cy + sin_a * dx + cos_a * dy
            if isinstance(child, QTrapGroup):
                child._rotateSilently(angle, cx, cy, snapshot)

    def _broadcastChanged(self) -> None:
        '''Emit ``changed`` for every descendant and then self.

        Leaf ``changed`` signals drive CGH displacement-field cache
        invalidation (``_field_cache[leaf]``) and propagate structure
        invalidation up through all ancestor groups via
        ``_invalidateStructureChain``.  Sub-group ``changed`` signals
        additionally clear each inner group's displacement cache
        (``_field_cache[inner]``).  ``self.changed`` at the end drives
        the visual update in ``QTrapOverlay._onGroupChanged``.
        '''
        for child in self:
            if isinstance(child, QTrapGroup):
                child._broadcastChanged()
            else:
                child.changed.emit()
        self.changed.emit()

    def rotate(self, angle: float, snapshot: dict) -> None:
        '''Rotate all children by angle around the group center.

        Applies the rotation from the snapshotted positions to avoid
        floating-point drift during interactive drag.  All sub-group
        centers are updated recursively.  Calls ``_broadcastChanged``
        so that the CGH displacement-field caches for every descendant
        are invalidated and ``QTrapOverlay`` updates its spots.

        Parameters
        ----------
        angle : float
            Rotation angle in radians, measured from the positions
            stored in ``snapshot``.
        snapshot : dict
            Mapping of ``id(child)`` to initial position array,
            as returned by ``_snapshot()``.
        '''
        cx, cy = self._r[0], self._r[1]
        self._rotateSilently(angle, cx, cy, snapshot)
        self._broadcastChanged()

    @QTrap.r.setter
    def r(self, r: npt.ArrayLike) -> None:
        '''Translate the group so its center moves to ``r``.

        Moves the group node and all descendants by the same delta,
        then emits ``changed`` on the group itself.  Individual leaf
        ``changed`` signals are not emitted; observers that need a
        per-leaf notification should connect to the group's ``changed``.
        '''
        new_r = np.asarray(r, dtype=float)
        delta = new_r - self._r
        self._translateSilently(delta)
        self.changed.emit()

    def to_dict(self) -> dict:
        '''Serialise this group and all its children to a plain dict.

        Returns
        -------
        dict
            A dict with ``'type'``, the registered properties,
            ``'locked': True`` when the group is locked, and a
            ``'children'`` list of recursively serialised child traps.
        '''
        d = super().to_dict()
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
