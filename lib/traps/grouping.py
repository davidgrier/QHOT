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
    overlay now.  A group that is left with one trap dissolves (the trap
    that is left joins the top level) and a group that is left with none
    disappears.  The marks of the traps that the group held are cleared.

    ``trapRemoved`` is emitted for the group that changes, and ``trapAdded``
    for what is there afterwards.

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
    overlay.unmark(overlay.groupOf(group))
    if isinstance(outer, QTrapGroup):
        _leave_subgroup(overlay, outer, group)
    else:
        _leave_group(overlay, group, trap)
    return True


def _leave_subgroup(overlay: QTrapOverlay,
                    outer: QTrapGroup,
                    group: QTrapGroup) -> None:
    '''Move the subgroup *group* out of the group *outer*.

    *outer* disappears if nothing is left in it.
    '''
    overlay.trapRemoved.emit(outer)
    outer.removeTrap(group)
    group.setParent(overlay)
    overlay.watch(group)
    if not list(outer) and outer.parent() is overlay:
        overlay.unwatch(outer)
        outer.setParent(None)
    else:
        overlay.trapAdded.emit(outer)
    overlay.trapAdded.emit(group)


def _leave_group(overlay: QTrapOverlay,
                 group: QTrapGroup,
                 trap: QTrap) -> None:
    '''Move *trap* out of the top-level group *group*.

    A group left with one trap dissolves, and with none disappears.
    '''
    others = [member for member in group if member is not trap]
    overlay.trapRemoved.emit(group)
    group.removeTrap(trap)
    trap.setParent(overlay)
    if len(others) == 1:
        (sole,) = others
        group.removeTrap(sole)
        sole.setParent(overlay)
        overlay.unwatch(group)
        group.setParent(None)
        overlay.trapAdded.emit(sole)
    elif others:
        overlay.trapAdded.emit(group)
    else:
        overlay.unwatch(group)
        group.setParent(None)
    overlay.trapAdded.emit(trap)
