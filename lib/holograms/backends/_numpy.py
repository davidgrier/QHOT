from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from QHOT.lib.types import Hologram
from ._base import Backend
from ..optics import Optics


__all__ = ['NumpyBackend']


class NumpyBackend(Backend):

    r'''Computes holograms on the CPU with NumPy.

    The sum of the fields of the plain tweezers is one complex matrix
    product, :math:`\psi = YX`, which NumPy hands to the BLAS library of
    the platform.  This is the backend that works everywhere, and the one
    to compare the others with.  It works in single precision.
    '''

    name = 'numpy'

    def calibrate(self, optics: Optics) -> SimpleNamespace:
        '''Return the vectors of the optics in single precision.'''
        f32 = np.float32
        return SimpleNamespace(
            shape=optics.shape,
            qx=optics.qx.astype(f32),
            qy=optics.qy.astype(f32),
            x2=(optics.x**2).astype(f32),
            y2=(optics.y**2).astype(f32),
            qpar=f32(optics.qpar),
        )

    def zeros(self, c: SimpleNamespace) -> np.ndarray:
        '''Return an empty ``complex64`` field.'''
        return np.zeros(c.shape, dtype=np.complex64)

    def phasors(self,
                c: SimpleNamespace,
                positions: np.ndarray,
                amplitudes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        r'''Return :math:`(Y, X)` as ``complex64`` arrays.

        :math:`Y` is returned transposed from the array that is made, which
        is the layout that the matrix product wants.
        '''
        r = positions.astype(np.float32)
        px = c.qx * r[:, 0:1] + c.qpar * c.x2 * r[:, 2:3]    # n x width
        py = -c.qy * r[:, 1:2] + c.qpar * c.y2 * r[:, 2:3]   # n x height
        x = np.exp(1j * px).astype(np.complex64)
        y = np.exp(1j * py).astype(np.complex64)
        y *= amplitudes.astype(np.complex64)[:, None]
        return y.T, x

    def superpose(self,
                  psi: np.ndarray,
                  phasors: tuple[np.ndarray, np.ndarray],
                  structure: np.ndarray | None = None) -> np.ndarray:
        '''Add the traps to ``psi`` in place and return it.

        One trap is an outer product and is made without BLAS; more are a
        matrix product.
        '''
        y, x = phasors
        term = y * x if y.shape[1] == 1 else y @ x
        if structure is not None:
            term *= structure
        psi += term
        return psi

    def quantize(self, psi: np.ndarray) -> Hologram:
        '''Return the phase of ``psi`` as ``uint8``.'''
        return ((128. / np.pi) * np.angle(psi) + 127.).astype(np.uint8)

    def upload(self, field: np.ndarray) -> np.ndarray:
        '''Return the structuring field as ``complex64``.'''
        return field.astype(np.complex64)
