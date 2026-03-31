from __future__ import annotations

from qtpy import QtCore
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.letterSymbol import letterSymbol
from typing import TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from QHOT.lib.holograms.CGH import CGH
    from QHOT.lib.types import Field


class QVortex(QTrap):

    '''Optical vortex trap.

    Applies a helical phase ramp ``exp(i ell θ)`` to the trapping beam,
    producing a ring-shaped focus with a phase singularity at the center.

    Parameters
    ----------
    ell : int
        Topological charge (winding number) of the vortex. Default: 0.
    *args, **kwargs
        Forwarded to ``QTrap``.

    Attributes
    ----------
    ell : int
        Topological charge of the optical vortex.
    '''

    #: Emitted when the topological charge changes.
    structureChanged = QtCore.Signal()

    def __init__(self, *args, ell: int = 10, **kwargs) -> None:
        self._ell = int(ell)
        super().__init__(*args, **kwargs)

    def _registerProperties(self) -> None:
        '''Register ``ell`` as an editable property in addition to
        base properties.'''
        super()._registerProperties()
        self.registerProperty('ell', decimals=0, tooltip=True)

    def appearance(self) -> dict:
        '''Return the letter ``V`` as the scatter-plot symbol for this trap.'''
        return {'symbol': letterSymbol('V')}

    @property
    def ell(self) -> int:
        '''Topological charge of the optical vortex.'''
        return self._ell

    @ell.setter
    def ell(self, ell: int) -> None:
        self._ell = int(ell)
        self.structureChanged.emit()

    def structure(self, cgh: CGH) -> Field:
        '''Compute the helical phase structure ``exp(i ell θ)``.

        Parameters
        ----------
        cgh : CGH
            The hologram engine providing the angular coordinate
            array ``theta``.

        Returns
        -------
        Field
            Complex phase mask of shape ``cgh.shape``.
        '''
        return np.exp(1j * self.ell * cgh.theta)


if __name__ == '__main__':  # pragma: no cover
    QVortex.example()
