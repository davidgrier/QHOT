from __future__ import annotations

from qtpy import QtCore
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.letterSymbol import letterSymbol
from typing import TYPE_CHECKING
import numpy as np
from scipy.special import jv

if TYPE_CHECKING:
    from QHOT.lib.holograms.CGH import CGH
    from QHOT.lib.types import Field


class QRingTrap(QTrap):

    '''Ring trap.

    Focuses light into a ring of radius ``radius`` using a Bessel-function
    amplitude profile combined with a helical phase ramp.

    Parameters
    ----------
    radius : float
        Radius of the ring [pixels]. Default: 10.
    ell : float
        Topological charge of the ring trap. Default: 0.
    *args, **kwargs
        Forwarded to ``QTrap``.

    Attributes
    ----------
    radius : float
        Radius of the ring trap [pixels].
    ell : float
        Topological charge of the ring trap.
    '''

    #: Emitted when the topological charge or radius changes.
    structureChanged = QtCore.Signal()

    def __init__(self, *args,
                 radius: float = 10.,
                 ell: float = 10.,
                 **kwargs) -> None:
        self._radius = float(radius)
        self._ell = float(ell)
        super().__init__(*args, **kwargs)

    def _registerProperties(self) -> None:
        '''Register ``radius`` and ``ell`` as editable properties.'''
        super()._registerProperties()
        self.registerProperty('radius', tooltip=True)
        self.registerProperty('ell', decimals=0, tooltip=True)

    def appearance(self) -> dict:
        '''Return the letter ``O`` as the scatter-plot symbol for this trap.'''
        return {'symbol': letterSymbol('O')}

    @property
    def radius(self) -> float:
        '''Radius of the ring trap [pixels].'''
        return self._radius

    @radius.setter
    def radius(self, radius: float) -> None:
        self._radius = float(radius)
        self.structureChanged.emit()

    @property
    def ell(self) -> float:
        '''Topological charge of the ring trap.'''
        return self._ell

    @ell.setter
    def ell(self, ell: float) -> None:
        self._ell = float(ell)
        self.structureChanged.emit()

    def structure(self, cgh: CGH) -> Field:
        '''Compute the Bessel-function amplitude and helical phase structure.

        Parameters
        ----------
        cgh : CGH
            The hologram engine providing the radial coordinate array
            ``qr`` and angular coordinate array ``theta``.

        Returns
        -------
        Field
            Complex structure mask of shape ``cgh.shape``.
        '''
        return (jv(self.ell, self.radius * cgh.qr)
                * np.exp(1j * self.ell * cgh.theta))


if __name__ == '__main__':  # pragma: no cover
    QRingTrap.example()
