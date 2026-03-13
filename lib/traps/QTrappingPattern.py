from .QTrapGroup import QTrapGroup
from .QTrap import QTrap
from pyqtgraph.Qt.QtCore import (QPointF, QRect, QRectF, QSignalBlocker)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QTrappingPattern(QTrapGroup):

    '''Top-level group for organizing traps

    Inherits
    --------
    QTrapGroup
    '''

    def makeGroup(self, traps: QTrap | None) -> None:
        '''Combines traps into a group that is added to the pattern.'''
        with QSignalBlocker(self):
            if (traps is None) or (len(traps) < 2):
                logger.debug('Not enough traps to group')
                return
            group = QTrapGroup()
            for trap in traps:
                self.remove(trap)
                group.add(trap)
            group.origin = group.r = trap.r
            self.add(group)

    def breakGroup(self, group: QTrapGroup | None) -> None:
        '''Breaks group and moves traps into the pattern.'''
        with QSignalBlocker(self):
            if not isinstance(group, QTrapGroup):
                logger.debug('No group to break')
                return
            for trap in group:
                group.remove(trap)
                self.add(trap)

    def groupOf(self, trap: QTrap | None) -> QTrap | None:
        '''Returns top-level TrapGroup containing this trap.'''
        if trap is None:
            return None
        while trap.parent() is not self:
            trap = trap.parent()
        return trap

    def groupTraps(self, rect: QRect | QRectF) -> list[QTrap]:
        '''Labels traps that are being grouped and returns the list.'''
        traps = []
        for trap in self:
            if trap.isWithin(QRectF(rect)):
                trap.setState(trap.State.GROUPING)
                traps.append(trap)
            else:
                trap.setState(trap.State.NORMAL)
        return traps
