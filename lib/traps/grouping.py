'''Changing the structure of the traps of an overlay: grouping and breaking.

A trap is at the top level of the overlay, or in a group, which is at the
top level or in another group.  Observers of the overlay (the Traps tab)
know the top-level traps and groups, and what is in them, so a change of
structure tells them what went away (``trapRemoved``) before it changes
anything, and what is there now (``trapAdded``) after.
'''
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from qtpy import QtCore

from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup

if TYPE_CHECKING:
    from QHOT.lib.traps.QTrapOverlay import QTrapOverlay


__all__ = 'group_within break_group'.split()


def group_within(overlay: QTrapOverlay, rect: QtCore.QRectF) -> None:
    '''Group the top-level traps and groups that lie within a rectangle.

    A group is included only if all of its traps are inside *rect*: a
    group that straddles the boundary is left alone.  Nothing is done if
    fewer than two items are inside.  The new group is centered on the
    mean of the centers of the items.  Their marks are cleared: the items
    are no longer at the top level, which is where the marks are.

    ``trapRemoved`` is emitted for each item that goes into the group, and
    ``trapAdded`` for the group.

    Parameters
    ----------
    overlay : QTrapOverlay
        The overlay whose traps are grouped.
    rect : QRectF
        The rubber band, in the coordinates of the overlay.
    '''
    items = [item for item in overlay if item.isWithin(rect)]
    if len(items) < 2:
        return
    for item in items:
        overlay.unmark(item)
        overlay.trapRemoved.emit(item)
    group = QTrapGroup(r=np.mean([item.r for item in items], axis=0),
                       parent=overlay)
    group.addTrap(items)
    overlay.watch(group)
    overlay.trapAdded.emit(group)


def break_group(overlay: QTrapOverlay, trap: QTrap) -> bool:
    '''Take a trap, or the subgroup that it is in, out of its group.

    A trap in a group at the top level leaves the group.  A trap in a
    subgroup takes the subgroup with it, and the subgroup leaves the group
    that it was in.  Either way what leaves is a top-level item of the
    overlay now.

    A trap is a top-level item or a member of a group, and a group holds
    two traps or more: a group left with one dissolves, and the trap that is
    left stands where the group stood (in the group above it, or at the top
    level), and a group left with none disappears.  A group of one trap that
    a file made is dissolved by breaking its trap.  The marks of the traps
    that the group held are cleared.

    ``trapRemoved`` is emitted for the top-level item that changes, and
    ``trapAdded`` for what is at the top level afterwards: that item if it is
    still there, the trap that took the place of a group that dissolved, and
    what left.

    Parameters
    ----------
    overlay : QTrapOverlay
        The overlay whose traps are changed.
    trap : QTrap
        A trap of the overlay.

    Returns
    -------
    bool
        ``True`` if something was taken out, ``False`` if the trap is in no
        group.
    '''
    group = trap.parent()
    if not isinstance(group, QTrapGroup):
        return False
    outer = group.parent()
    leaver, parent = ((group, outer) if isinstance(outer, QTrapGroup)
                      else (trap, group))
    root = overlay.groupOf(parent)
    overlay.unmark(root)
    overlay.trapRemoved.emit(root)
    parent.removeTrap(leaver)
    leaver.setParent(overlay)
    if isinstance(leaver, QTrapGroup):
        overlay.watch(leaver)
    promoted: list[QTrap] = []
    _tidy(overlay, parent, promoted)
    if root.parent() is overlay:
        overlay.trapAdded.emit(root)
    for item in promoted:
        overlay.trapAdded.emit(item)
    overlay.trapAdded.emit(leaver)
    return True


def _tidy(overlay: QTrapOverlay,
          group: QTrapGroup,
          promoted: list[QTrap]) -> None:
    '''Dissolve *group* if a trap was taken out and it holds fewer than two.

    A trap that is left takes the place of the group, and joins *promoted*
    if that is the top level.  A group that is left with none goes, and the
    group above it may then be left with one.
    '''
    members = list(group)
    if len(members) >= 2:
        return
    above = group.parent()
    if members:
        (sole,) = members
        group.removeTrap(sole)
        if isinstance(above, QTrapGroup):
            above.removeTrap(group)
            above.addTrap(sole)
            return
        sole.setParent(overlay)
        if isinstance(sole, QTrapGroup):
            overlay.watch(sole)
        promoted.append(sole)
    elif isinstance(above, QTrapGroup):
        above.removeTrap(group)
        _tidy(overlay, above, promoted)
        return
    overlay.unwatch(group)
    group.setParent(None)
