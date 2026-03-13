from QFab.lib.traps.QTrap import QTrap
from QFab.lib.letterSymbol import letterSymbol
import numpy as np


class QVortex(QTrap):

    '''Optical vortex trap.

    Applies a helical phase ramp ``exp(i ell θ)`` to the trapping beam,
    producing a ring-shaped focus with a phase singularity at the centre.

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

    def __init__(self, *args, ell: int = 0, **kwargs) -> None:
        self._ell = int(ell)
        super().__init__(*args, **kwargs)

    def _registerProperties(self) -> None:
        super()._registerProperties()
        self.registerProperty('ell', decimals=0, tooltip=True)

    def appearance(self) -> dict:
        return {'symbol': letterSymbol('V')}

    @property
    def ell(self) -> int:
        '''Topological charge of the optical vortex.'''
        return self._ell

    @ell.setter
    def ell(self, ell: int) -> None:
        self._ell = int(ell)
        self.changed.emit()

    def structure(self, cgh) -> np.ndarray:
        return np.exp(1j * self.ell * cgh.theta)


if __name__ == '__main__':
    QVortex.example()
