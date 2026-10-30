from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from QHOT.lib.types import Hologram
from .Backend import Backend
from .Optics import Optics


__all__ = ['NumpyBackend']


class NumpyBackend(Backend):

    '''Computes holograms on the CPU with NumPy.

    The sum of the fields of the plain tweezers is one complex matrix
    product, which NumPy hands to the BLAS library of the platform.  This
    is the backend that works everywhere, and it is the one to compare
    the others with.
    '''

    name = 'numpy'

    def calibrate(self, optics: Optics) -> SimpleNamespace:
        f32 = np.float32
        return SimpleNamespace(
            shape=optics.shape,
            qx=optics.qx.astype(f32), qy=optics.qy.astype(f32),
            x2=(optics.x**2).astype(f32), y2=(optics.y**2).astype(f32),
            qpar=f32(optics.qpar))

    def zeros(self, c: SimpleNamespace) -> np.ndarray:
        return np.zeros(c.shape, dtype=np.complex64)

    def phasors(self, c: SimpleNamespace, R: np.ndarray,
              amplitudes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        R = R.astype(np.float32)
        px = c.qx * R[:, 0:1] + c.qpar * c.x2 * R[:, 2:3]    # n x width
        py = -c.qy * R[:, 1:2] + c.qpar * c.y2 * R[:, 2:3]   # n x height
        ex = np.exp(1j * px).astype(np.complex64)
        ey = np.exp(1j * py).astype(np.complex64)
        ey *= amplitudes.astype(np.complex64)[:, None]
        return ey.T, ex

    def superpose(self, psi: np.ndarray, phasors: tuple,
                   structure: np.ndarray | None = None) -> np.ndarray:
        rows, columns = phasors
        if rows.shape[1] == 1:                       # one trap: an outer
            term = rows * columns                    # product, no BLAS
        else:
            term = rows @ columns
        if structure is not None:
            term *= structure
        psi += term
        return psi

    def quantize(self, psi: np.ndarray) -> Hologram:
        return ((128. / np.pi) * np.angle(psi) + 127.).astype(np.uint8)

    def upload(self, field: np.ndarray) -> np.ndarray:
        return field.astype(np.complex64)
