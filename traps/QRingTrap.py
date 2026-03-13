from QFab.lib.traps.QTrap import QTrap
from QFab.lib.letterSymbol import letterSymbol
import numpy as np
from scipy.special import jv


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

    def __init__(self, *args,
                 radius: float = 10.,
                 ell: float = 0.,
                 **kwargs) -> None:
        self._radius = float(radius)
        self._ell = float(ell)
        super().__init__(*args, **kwargs)

    def _registerProperties(self) -> None:
        super()._registerProperties()
        self.registerProperty('radius', tooltip=True)
        self.registerProperty('ell', decimals=0, tooltip=True)

    def appearance(self) -> dict:
        return {'symbol': letterSymbol('O')}

    @property
    def radius(self) -> float:
        '''Radius of the ring trap [pixels].'''
        return self._radius

    @radius.setter
    def radius(self, radius: float) -> None:
        self._radius = float(radius)
        self.changed.emit()

    @property
    def ell(self) -> float:
        '''Topological charge of the ring trap.'''
        return self._ell

    @ell.setter
    def ell(self, ell: float) -> None:
        self._ell = float(ell)
        self.changed.emit()

    def structure(self, cgh) -> np.ndarray:
        return jv(self.ell, self.radius * cgh.qr) * np.exp(1j * self.ell * cgh.theta)


if __name__ == '__main__':
    QRingTrap.example()
