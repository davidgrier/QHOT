from __future__ import annotations

import logging
from collections.abc import Iterable

from qtpy import QtCore

from QHOT.lib.traps import TrapSpec
from .Backend import Backend
from .Optics import Optics


logger = logging.getLogger(__name__)

__all__ = ['QHologramWorker']


class QHologramWorker(QtCore.QObject):

    '''Computes holograms in the thread that it lives in.

    The worker is given a pattern of traps and the optics, both plain
    values that nothing else changes, and returns the hologram.  It owns
    its backend and touches nothing that the interface owns, so it needs
    no locks.

    Parameters
    ----------
    backend : Backend
        What computes the holograms.
    parent : QtCore.QObject or None
        Qt parent object.

    Signals
    -------
    done : Signal(object)
        The hologram, an array of ``uint8``.
    failed : Signal(str)
        The reason that a hologram could not be computed.
    '''

    #: Emitted with the hologram, an array of ``uint8``.
    done = QtCore.Signal(object)
    #: Emitted with the reason that a hologram could not be computed.
    failed = QtCore.Signal(str)

    def __init__(self, backend: Backend,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.backend = backend

    @QtCore.Slot(object, object)
    def compute(self, pattern: Iterable[TrapSpec], optics: Optics) -> None:
        '''Compute the hologram of a pattern and emit ``done``.

        Emits ``failed`` with the reason if the computation raises an
        exception.
        '''
        try:
            hologram = self.backend.hologram(pattern, optics)
        except Exception as ex:
            logger.error(f'hologram computation failed: {ex}')
            self.failed.emit(str(ex))
            return
        self.done.emit(hologram)
