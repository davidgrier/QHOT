from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from QHOT.lib.types import Hologram
from .Backend import Backend
from .Optics import Optics

try:
    import cupy as cp
except ImportError:  # pragma: no cover
    cp = None


__all__ = ['CupyBackend']


class CupyBackend(Backend):

    r'''Computes holograms on an NVIDIA GPU with CuPy.

    CuPy has the API of NumPy, and the computation is that of
    :class:`~QHOT.lib.holograms.NumpyBackend.NumpyBackend` carried out on
    the device: the sum of the fields of the traps is a complex matrix
    product, :math:`\psi = YX`, done by cuBLAS, and the phase is taken and
    scaled on the device so that only the finished bytes cross to the
    host.  The structuring fields are made on the host by the traps and
    uploaded once.

    .. note::

        This backend has been tested against the reference with a NumPy
        stand-in for CuPy, which checks the logic and the shapes and
        types, but not the CUDA library.  It has to be tried on a machine
        with an NVIDIA GPU.  Choose it with ``-u`` rather than leaving it
        to the automatic choice, until it has been.

    Parameters
    ----------
    cache : int
        Number of structuring fields to keep.  Default: 64.

    Raises
    ------
    ImportError
        If ``cupy`` is not installed.
    RuntimeError
        If there is no CUDA device.
    '''

    name = 'cupy'

    def __init__(self, cache: int = 64) -> None:
        if cp is None:
            raise ImportError(
                'cupy is required for CupyBackend. '
                'Install it with: pip install cupy-cuda12x '
                '(or the build for your version of CUDA)',
            )
        super().__init__(cache)
        try:
            cp.cuda.Device()
        except Exception as ex:
            raise RuntimeError(f'no CUDA device is available: {ex}') from ex

    def calibrate(self, optics: Optics) -> SimpleNamespace:
        '''Return the vectors of the optics as arrays on the device.'''
        f32 = cp.float32
        return SimpleNamespace(
            shape=optics.shape,
            qpar=float(optics.qpar),
            qx=cp.asarray(optics.qx, dtype=f32),
            qy=cp.asarray(optics.qy, dtype=f32),
            x2=cp.asarray(optics.x**2, dtype=f32),
            y2=cp.asarray(optics.y**2, dtype=f32),
        )

    def zeros(self, c: SimpleNamespace):
        '''Return an empty ``complex64`` field on the device.'''
        return cp.zeros(c.shape, dtype=cp.complex64)

    def phasors(self,
                c: SimpleNamespace,
                positions: np.ndarray,
                amplitudes: np.ndarray) -> tuple:
        r'''Return :math:`(Y, X)` as ``complex64`` arrays on the device.'''
        r = cp.asarray(positions, dtype=cp.float32)
        a = cp.asarray(amplitudes, dtype=cp.complex64)[:, None]
        px = c.qx * r[:, 0:1] + c.qpar * c.x2 * r[:, 2:3]    # n x width
        py = -c.qy * r[:, 1:2] + c.qpar * c.y2 * r[:, 2:3]   # n x height
        x = cp.exp(1j * px).astype(cp.complex64)
        y = cp.exp(1j * py).astype(cp.complex64) * a
        return y.T, x

    def superpose(self,
                  psi,
                  phasors: tuple,
                  structure=None):
        '''Add the traps to ``psi`` in place and return it.

        One trap is an outer product; more are a matrix product.
        '''
        y, x = phasors
        term = y * x if y.shape[1] == 1 else y @ x
        if structure is not None:
            term *= structure
        psi += term
        return psi

    def quantize(self, psi) -> Hologram:
        '''Return the phase of ``psi`` as ``uint8`` on the host.

        The phase is taken and scaled on the device, so that only the
        finished bytes cross to the host.
        '''
        level = (128. / np.pi) * cp.angle(psi) + 127.
        return cp.asnumpy(level.astype(cp.uint8))

    def upload(self, field: np.ndarray):
        '''Return the structuring field as a ``complex64`` array on the
        device.'''
        return cp.asarray(field, dtype=cp.complex64)
