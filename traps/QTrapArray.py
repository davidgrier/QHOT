'''A rectangular array of tweezers.'''
from __future__ import annotations

import numpy as np
import numpy.typing as npt
from qtpy import QtCore

from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.types import Shape
from .QTweezer import QTweezer


class QTrapArray(QTrapGroup):

    '''Rectangular array of optical tweezers, with optional mask.

    Subclass of ``QTrapGroup``. Creates a uniform grid of ``QTweezer``
    traps centered on the group's own position.  An optional boolean mask
    of shape ``(nx, ny)`` can suppress individual grid positions: ``True``
    means the tweezer is present, ``False`` means it is absent.

    The grid dimensions, spacing, and mask are all settable
    programmatically.  Changing ``nx``, ``ny``, or ``shape`` resets the
    mask to ``None`` (full grid).  Changing ``separation`` or ``mask``
    preserves the shape.

    Parameters
    ----------
    shape : tuple[int, int]
        Number of grid positions along the (x, y) directions.
        Default: (4, 4).
    separation : float
        Center-to-center spacing between adjacent positions [pixels].
        Default: 50.
    mask : array_like of bool, shape (nx, ny), optional
        Boolean mask selecting which grid positions are active.
        ``None`` (default) activates all positions.
    fuzz : float
        Standard deviation of the random displacement of each trap
        [pixels].  Default: 0.
    seed : int, optional
        Seed of the random displacements.  With a seed, the same array has
        the same displacements whenever it is made: after it is saved and
        loaded, reshaped, or an edit is undone.  Without one, a seed is
        drawn at random when the array first needs it, and kept (and
        saved) so that the array stays as it was made.  Give the same seed
        to get the same displacements in another array.
    *args, **kwargs
        Forwarded to ``QTrapGroup``.

    Attributes
    ----------
    shape : tuple[int, int]
        Grid dimensions (nx, ny).
    nx : int
        Grid size along x.  Registered property.
    ny : int
        Grid size along y.  Registered property.
    separation : float
        Tweezer spacing [pixels].  Registered property.
    fuzz : float
        Standard deviation of Gaussian random displacement applied to
        each trap position at population time [pixels].  Registered property.
        Default: 0. (exact grid positions).
    seed : int or None
        Seed of the displacements, or ``None`` until the array has any.
    mask : np.ndarray or None
        Active-position mask, shape (nx, ny), or None for full grid.

    Signals
    -------
    reshaping : ()
        Emitted immediately before the existing tweezers are cleared.
    reshaped : ()
        Emitted after the new tweezers have been added.
    '''

    #: Emitted when the array begins to reshape.
    reshaping = QtCore.Signal()
    #: Emitted when the array has finished reshaping.
    reshaped = QtCore.Signal()

    def __init__(self,
                 *args,
                 shape: Shape = (4, 4),
                 separation: float = 50.,
                 mask: npt.ArrayLike | None = None,
                 fuzz: float = 0.,
                 seed: int | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._nx, self._ny = (max(1, int(n)) for n in shape)
        self._separation = max(1., float(separation))
        self._fuzz = max(0., float(fuzz))
        self._seed = None if seed is None else int(seed)
        if mask is not None:
            mask = np.asarray(mask, dtype=bool)
            if mask.shape != (self._nx, self._ny):
                raise ValueError(
                    f'mask shape {mask.shape} does not match '
                    f'array shape ({self._nx}, {self._ny})')
        self._mask = mask
        self._populate()

    def _registerProperties(self) -> None:
        super()._registerProperties()
        self.registerProperty('nx', decimals=0, tooltip=True)
        self.registerProperty('ny', decimals=0, tooltip=True)
        self.registerProperty('separation', decimals=1, tooltip=True)
        self.registerProperty('fuzz', decimals=1, tooltip=True)

    # --- shape/nx/ny/separation properties ---

    @property
    def shape(self) -> Shape:
        '''Grid dimensions (nx, ny).'''
        return (self._nx, self._ny)

    @shape.setter
    def shape(self, shape: Shape) -> None:
        self._nx, self._ny = (max(1, int(n)) for n in shape)
        self._mask = None
        self._repopulate()

    @property
    def nx(self) -> int:
        '''Number of grid positions along x.'''
        return self._nx

    @nx.setter
    def nx(self, nx: float) -> None:
        self._nx = max(1, int(nx))
        self._mask = None
        self._repopulate()

    @property
    def ny(self) -> int:
        '''Number of grid positions along y.'''
        return self._ny

    @ny.setter
    def ny(self, ny: float) -> None:
        self._ny = max(1, int(ny))
        self._mask = None
        self._repopulate()

    @property
    def separation(self) -> float:
        '''Center-to-center position spacing [pixels].'''
        return self._separation

    @separation.setter
    def separation(self, separation: float) -> None:
        self._separation = max(1., float(separation))
        self._repopulate()

    # --- fuzz property ---

    @property
    def fuzz(self) -> float:
        '''Standard deviation of random trap displacement [pixels].'''
        return self._fuzz

    @fuzz.setter
    def fuzz(self, fuzz: float) -> None:
        self._fuzz = max(0., float(fuzz))
        self._repopulate()

    @property
    def seed(self) -> int | None:
        '''Seed of the random displacements, or ``None`` before any.'''
        return self._seed

    @seed.setter
    def seed(self, seed: int | None) -> None:
        self._seed = None if seed is None else int(seed)
        self._repopulate()

    def _displacements(self) -> np.ndarray:
        '''Return the displacement of each grid position, shape (nx, ny, 2).

        A multiple of the same standard normal numbers for a given seed, so
        that the pattern keeps its shape as ``fuzz`` changes, and a position
        of the grid keeps its displacement when the mask changes.  The
        seed is drawn the first time that it is needed.
        '''
        if self._seed is None:
            self._seed = int(np.random.default_rng().integers(2**31))
        rng = np.random.default_rng(self._seed)
        return self._fuzz * rng.standard_normal((self._nx, self._ny, 2))

    # --- mask property ---

    @property
    def mask(self) -> np.ndarray | None:
        '''Boolean active-position mask of shape (nx, ny), or None.'''
        return self._mask

    @mask.setter
    def mask(self, mask: npt.ArrayLike | None) -> None:
        if mask is not None:
            mask = np.asarray(mask, dtype=bool)
            if mask.shape != (self._nx, self._ny):
                raise ValueError(
                    f'mask shape {mask.shape} does not match '
                    f'array shape ({self._nx}, {self._ny})')
        self._mask = mask
        self._repopulate()

    # --- population ---

    def _populate(self) -> None:
        '''Create tweezers at active grid positions, centered on the group.

        When ``fuzz`` is non-zero each trap is displaced by an independent
        Gaussian random offset (std = ``fuzz``) in x and y, which the
        ``seed`` fixes.
        '''
        cx, cy, cz = self._r
        xs = cx + self._separation * (np.arange(self._nx)
                                      - (self._nx - 1) / 2.)
        ys = cy + self._separation * (np.arange(self._ny)
                                      - (self._ny - 1) / 2.)
        jitter = (self._displacements() if self._fuzz > 0.
                  else np.zeros((self._nx, self._ny, 2)))
        traps = []
        for ix, x in enumerate(xs):
            for iy, y in enumerate(ys):
                if self._mask is None or self._mask[ix, iy]:
                    jx, jy = jitter[ix, iy]
                    traps.append(QTweezer(r=(x + jx, y + jy, cz)))
        if traps:
            self.addTrap(traps)

    def toDict(self) -> dict:
        '''Serialize this array's parameters to a plain dict.

        Overrides ``QTrapGroup.toDict()`` to omit children, which are
        reconstructed automatically from ``shape``, ``separation``,
        ``fuzz``, and ``mask`` when the object is re-created.

        Returns
        -------
        dict
            A dict with ``'type'``, registered properties, ``'seed'`` (if
            the array has displacements), and ``'mask'`` (a nested list of
            bools, or ``None``).
        '''
        d = {'type': type(self).__name__, **self.settings}
        if self.locked:
            d['locked'] = True
        if self._seed is not None:
            d['seed'] = self._seed
        d['mask'] = self._mask.tolist() if self._mask is not None else None
        return d

    @classmethod
    def fromDict(cls, d: dict) -> QTrapArray:
        '''Reconstruct a QTrapArray from a serialized dict.

        Overrides ``QTrap.fromDict`` to convert the serialized ``nx``
        and ``ny`` values back into the ``shape`` constructor argument,
        and to convert ``mask`` from a nested list to a numpy array.

        Parameters
        ----------
        d : dict
            A dict as produced by ``QTrapArray.toDict()``.

        Returns
        -------
        QTrapArray
            A new instance initialized from ``d``.
        '''
        r = (d['x'], d['y'], d['z'])
        shape = (int(d['nx']), int(d['ny']))
        mask = d.get('mask')
        if mask is not None:
            mask = np.array(mask, dtype=bool)
        kwargs = {k: v for k, v in d.items()
                  if k not in ('type', 'x', 'y', 'z', 'nx', 'ny', 'mask')}
        return cls(r=r, shape=shape, mask=mask, **kwargs)

    def _repopulate(self) -> None:
        '''Signal, clear direct children, repopulate, and signal again.'''
        self.reshaping.emit()
        for child in list(self):
            child.setParent(None)
        self._populate()
        self.reshaped.emit()

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Demonstrate creation and reshaping of a tweezer array.'''
        arr = cls(shape=(3, 3), separation=30.)
        print(arr)
        for trap in arr.leaves():
            print(f'  {trap}')
        arr.nx = 2
        print(f'After nx=2: {arr}')


if __name__ == '__main__':  # pragma: no cover
    QTrapArray.example()
