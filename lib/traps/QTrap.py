import logging

import numpy as np
import numpy.typing as npt
from pyqtgraph.Qt import QtCore
from collections.abc import Iterator

from QHOT.lib.types import Position


logger = logging.getLogger(__name__)


class QTrap(QtCore.QObject):

    _registry: dict[str, type] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        QTrap._registry[cls.__name__] = cls
    '''Abstract representation of an optical trap.

    Subclass of ``QtCore.QObject``.

    Attributes
    ----------
    r : npt.NDArray[np.float64]
        Three-dimensional location of the trap [pixels].
    x : float
        x-coordinate of the trap [pixels].
    y : float
        y-coordinate of the trap [pixels].
    z : float
        z-coordinate of the trap [pixels].
    amplitude : float
        Relative amplitude of the trap field.
    phase : float
        Relative phase of the trap field [radians].

    Signals
    -------
    changed
        Emitted when any property of the trap changes.
    '''

    #: Emitted when any trap property changes.
    changed = QtCore.Signal()

    def __init__(self,
                 r: npt.ArrayLike = (0., 0., 0.),
                 amplitude: float = 1.,
                 phase: float | None = None,
                 locked: bool = False,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._r = np.array(r, dtype=float)
        self._amplitude = float(amplitude)
        self._phase = (np.random.uniform(0., 2.*np.pi)
                       if phase is None else float(phase))
        self._locked = bool(locked)
        self._index: int | None = None
        self._registerProperties()

    def __len__(self) -> int:
        return 1

    def __iter__(self) -> Iterator['QTrap']:
        yield self

    def __repr__(self) -> str:
        name = type(self).__name__
        x, y, z = self._r
        return (f'{name}(r=({x:.1f}, {y:.1f}, {z:.1f}), '
                f'amplitude={self.amplitude:.2f}, phase={self.phase:.2f})')

    def _registerProperties(self) -> None:
        '''Register the properties exposed to QTrapWidget for editing.

        Called once from ``__init__``. Subclasses should call
        ``super()._registerProperties()`` and then call
        ``self.registerProperty(name)`` for each additional property
        they wish to expose.
        '''
        self.properties = dict()
        self.registerProperty('x')
        self.registerProperty('y')
        self.registerProperty('z')
        self.registerProperty('amplitude')
        self.registerProperty('phase')

    @property
    def r(self) -> Position:
        '''Three-dimensional location of the trap [pixels]'''
        return self._r.copy()

    @r.setter
    def r(self, r: npt.ArrayLike) -> None:
        self._r[:] = r
        self.changed.emit()

    @property
    def x(self) -> float:
        return self._r[0]

    @x.setter
    def x(self, x: float) -> None:
        self._r[0] = x
        self.changed.emit()

    @property
    def y(self) -> float:
        return self._r[1]

    @y.setter
    def y(self, y: float) -> None:
        self._r[1] = y
        self.changed.emit()

    @property
    def z(self) -> float:
        return self._r[2]

    @z.setter
    def z(self, z: float) -> None:
        self._r[2] = z
        self.changed.emit()

    @property
    def amplitude(self) -> float:
        '''Relative amplitude of the trap field'''
        return self._amplitude

    @amplitude.setter
    def amplitude(self, amplitude: float) -> None:
        self._amplitude = amplitude
        self.changed.emit()

    @property
    def phase(self) -> float:
        '''Relative phase of the trap field [radians]'''
        return self._phase

    @phase.setter
    def phase(self, phase: float) -> None:
        self._phase = phase
        self.changed.emit()

    @property
    def locked(self) -> bool:
        '''Whether this trap is locked (immovable).

        Locked traps cannot be moved, scrolled, or rotated via mouse
        gestures.  The overlay displays them with the ``STATIC`` brush.
        The lock state is preserved when saving and loading trap
        configurations.
        '''
        return self._locked

    @locked.setter
    def locked(self, value: bool) -> None:
        self._locked = bool(value)

    def leaves(self) -> Iterator['QTrap']:
        '''Yield this trap as its own sole leaf.

        Provides a uniform interface with ``QTrapGroup.leaves()`` so that
        callers needing only leaf traps can call ``leaves()`` on any trap
        without checking its type.

        Yields
        ------
        QTrap
            This trap itself.
        '''
        yield self

    def appearance(self) -> dict:
        '''Returns the visual properties of the trap

        Override in subclasses to return keywords for
        pyqtgraph SpotItem (symbol, size, pen, brush, etc.)
        '''
        return {}

    def isWithin(self, rect: QtCore.QRectF) -> bool:
        '''Returns True if the trap is within the rectangle'''
        return rect.contains(self.x, self.y)

    # Methods for editing properties with QTrapWidget

    def registerProperty(self,
                         name: str,
                         decimals: int = 2,
                         tooltip: bool = False) -> None:
        self.properties[name] = {'decimals': decimals,
                                 'tooltip': tooltip}

    @QtCore.pyqtSlot(str, float)
    def setTrapProperty(self, name: str, value: float) -> None:
        if name in self.properties:
            setattr(self, name, value)

    @property
    def settings(self) -> dict[str, float]:
        '''Current values of all registered properties.

        Returns
        -------
        dict[str, float]
            Mapping of property name to current value for every property
            registered via ``registerProperty``.
        '''
        return {p: getattr(self, p) for p in self.properties.keys()}

    def to_dict(self) -> dict:
        '''Serialise this trap to a plain dict suitable for JSON export.

        Returns
        -------
        dict
            A dict with a ``'type'`` key (the class name), one key per
            registered property, and ``'locked': True`` when the trap is
            locked (omitted when unlocked to keep JSON compact).
        '''
        d = {'type': type(self).__name__, **self.settings}
        if self._locked:
            d['locked'] = True
        return d

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        trap = cls(r=(10, 20, 30))
        print(trap)


if __name__ == '__main__':  # pragma: no cover
    QTrap.example()
