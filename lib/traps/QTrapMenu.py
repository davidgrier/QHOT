import functools
from qtpy import QtCore, QtWidgets
from QHOT.lib.traps.QTrap import QTrap
import QHOT.traps
import logging


logger = logging.getLogger(__name__)


class QTrapMenu(QtWidgets.QMenu):

    '''Context menu for adding a trap of a chosen type to the overlay.

    Populates itself from ``QHOT.traps.__all__`` and emits
    ``trapRequested`` when the user picks an entry.  Set ``pos``
    before executing the menu so the emitted trap is positioned where
    the user clicked.

    Parameters
    ----------
    title : str
        Menu title shown in the menu bar.  Defaults to ``'Add Trap'``.
    *args, **kwargs
        Forwarded to ``QMenu``.

    Attributes
    ----------
    pos : QtCore.QPointF
        Screen-space position that will be assigned to the new trap.
        Defaults to the origin; set this before calling ``exec()``.

    Signals
    -------
    trapRequested : QtCore.Signal(QtCore.QPointF, QTrap)
        Emitted with the configured ``pos`` and a freshly constructed
        trap instance when the user selects a trap type.
    '''

    #: Emitted with (position, trap) when the user selects a trap type.
    trapRequested = QtCore.Signal(QtCore.QPointF, QTrap)

    def __init__(self, *args, title: str = 'Add Trap', **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setTitle(title)
        self._pos = QtCore.QPointF(0., 0.)
        self._populateMenu()

    @property
    def pos(self) -> QtCore.QPointF:
        '''Position passed to the emitted trap.'''
        return self._pos

    @pos.setter
    def pos(self, pos: QtCore.QPointF) -> None:
        self._pos = pos

    def _populateMenu(self) -> None:
        '''Add one action per trap type listed in ``QHOT.traps.__all__``.'''
        for trapname in QHOT.traps.__all__:
            action = self.addAction(trapname)
            action.triggered.connect(
                functools.partial(self._onTrapSelected, trapname))

    @QtCore.Slot()
    def _onTrapSelected(self, trapname: str) -> None:
        '''Construct the chosen trap and emit ``trapRequested``.

        Parameters
        ----------
        trapname : str
            Name of the trap class to instantiate, as listed in
            ``QHOT.traps.__all__``.
        '''
        trap_class = getattr(QHOT.traps, trapname, None)
        if trap_class is None:
            logger.warning(f'Unknown trap type: {trapname}')
            return
        trap = trap_class(parent=self)
        self.trapRequested.emit(self._pos, trap)


def main() -> None:  # pragma: no cover
    import pyqtgraph as pg

    @QtCore.Slot(QtCore.QPointF, QTrap)
    def handler(pos: QtCore.QPointF, trap: QTrap) -> None:
        print(f'Adding trap {trap}')

    pg.mkQApp('QTrapMenu Example')
    demo = QtWidgets.QMainWindow()
    demo.menuBar().setNativeMenuBar(False)
    trapmenu = QTrapMenu(demo)
    trapmenu.trapRequested.connect(handler)
    demo.menuBar().addMenu(trapmenu)
    demo.show()
    pg.exec()


if __name__ == '__main__':  # pragma: no cover
    main()
