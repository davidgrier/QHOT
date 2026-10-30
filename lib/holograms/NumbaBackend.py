from __future__ import annotations

import math

import numpy as np

from QHOT.lib.types import Hologram
from .NumpyBackend import NumpyBackend

try:
    from numba import njit, prange
except ImportError:  # pragma: no cover
    njit = None


__all__ = ['NumbaBackend']

#: Up to this many traps are summed by a kernel of our own; more are left
#: to the matrix product of the BLAS library, which wins when there are
#: many.
FUSED_LIMIT = 12


if njit is not None:

    @njit(parallel=True, fastmath=True, cache=True)
    def _phasors(q, q2, qpar, sign, a, b, amplitude, out):
        '''Fill ``out[k, m]`` with the phasor of trap ``k`` at point ``m``.

        ``out[k, m] = amplitude[k] exp(i (sign q[m] a[k] + qpar q2[m] b[k]))``
        '''
        n, m = out.shape
        for k in prange(n):
            for i in range(m):
                phase = sign * q[i] * a[k] + qpar * q2[i] * b[k]
                out[k, i] = amplitude[k] * (
                    math.cos(phase) + 1j * math.sin(phase)
                )

    @njit(parallel=True, fastmath=True, cache=True)
    def _superpose(psi, y, x):
        '''psi += y @ x, a row at a time, for a few traps.'''
        height, width = psi.shape
        n = x.shape[0]
        for i in prange(height):
            row = np.zeros(width, dtype=np.complex64)
            for k in range(n):
                yk = y[i, k]
                for j in range(width):
                    row[j] += yk * x[k, j]
            for j in range(width):
                psi[i, j] += row[j]

    @njit(parallel=True, fastmath=True, cache=True)
    def _superpose_structured(psi, y, x, s):
        '''psi += s * (y @ x), a row at a time, for a few traps.'''
        height, width = psi.shape
        n = x.shape[0]
        for i in prange(height):
            row = np.zeros(width, dtype=np.complex64)
            for k in range(n):
                yk = y[i, k]
                for j in range(width):
                    row[j] += yk * x[k, j]
            for j in range(width):
                psi[i, j] += s[i, j] * row[j]

    @njit(parallel=True, fastmath=True, cache=True)
    def _add(psi, term):
        '''psi += term.'''
        height, width = psi.shape
        for i in prange(height):
            for j in range(width):
                psi[i, j] += term[i, j]

    @njit(parallel=True, fastmath=True, cache=True)
    def _add_structured(psi, term, s):
        '''psi += s * term.'''
        height, width = psi.shape
        for i in prange(height):
            for j in range(width):
                psi[i, j] += s[i, j] * term[i, j]

    @njit(parallel=True, fastmath=True, cache=True)
    def _quantize(psi, out):
        '''out = floor(128 arg(psi) / pi + 127), clipped to a byte.'''
        height, width = psi.shape
        scale = 128. / math.pi
        for i in prange(height):
            for j in range(width):
                level = scale * math.atan2(psi[i, j].imag, psi[i, j].real)
                level += 127.
                out[i, j] = np.uint8(min(max(level, 0.), 255.))


class NumbaBackend(NumpyBackend):

    r'''Computes holograms on the CPU with numba, on all the cores.

    The sum of the fields of many plain tweezers is the matrix product
    :math:`\psi = YX`, which the BLAS library does better than we could,
    so it is left to NumPy.  What numba improves are the parts that NumPy
    does in several passes over memory, each with its own temporary array:

    * a few traps, with or without a structuring field, are added to the
      field in a single pass, :math:`\psi \leftarrow \psi + S \odot (YX)`,
      computed a row at a time in cache;
    * the phasors are made, with their amplitudes, in one pass;
    * the quantization takes the phase and scales it in one pass.

    All of them run in parallel over the rows.  The kernels are compiled
    when the backend is made and kept on disk, so only the first run on a
    machine waits for the compiler.

    The compiled kernels use the threading layer of numba, which is not
    safe to call from several threads at once.  Use a backend from one
    thread at a time, as the pipeline does.

    Parameters
    ----------
    cache : int
        Number of structuring fields to keep.  Default: 64.

    Raises
    ------
    ImportError
        If ``numba`` is not installed.
    '''

    name = 'numba'

    def __init__(self, cache: int = 64) -> None:
        if njit is None:
            raise ImportError(
                'numba is required for NumbaBackend. '
                'Install it with: pip install numba',
            )
        super().__init__(cache)
        self._compile()

    def _compile(self) -> None:
        '''Compile the kernels now, on small arrays of the types used.'''
        n, height, width = 2, 4, 4
        psi = np.zeros((height, width), dtype=np.complex64)
        s = np.ones((height, width), dtype=np.complex64)
        x = np.ones((n, width), dtype=np.complex64)
        y = np.ones((n, height), dtype=np.complex64).T
        _phasors(
            np.zeros(width, dtype=np.float32),
            np.zeros(width, dtype=np.float32),
            np.float32(0.),
            np.float32(1.),
            np.zeros(n, dtype=np.float32),
            np.zeros(n, dtype=np.float32),
            np.ones(n, dtype=np.complex64),
            x,
        )
        _superpose(psi, y, x)
        _superpose_structured(psi, y, x, s)
        _add(psi, s)
        _add_structured(psi, s, s)
        _quantize(psi, np.zeros((height, width), dtype=np.uint8))

    def phasors(
        self,
        c,
        positions: np.ndarray,
        amplitudes: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        r'''Return :math:`(Y, X)` as ``complex64`` arrays.

        Each is made in one parallel pass, with the amplitudes in
        :math:`Y`.  :math:`Y` is returned transposed from the array that
        is made, which is the layout the matrix product wants.
        '''
        r = np.ascontiguousarray(positions, dtype=np.float32)
        a = np.ascontiguousarray(amplitudes, dtype=np.complex64)
        n = len(r)
        x = np.empty((n, len(c.qx)), dtype=np.complex64)
        y = np.empty((n, len(c.qy)), dtype=np.complex64)
        ones = np.ones(n, dtype=np.complex64)
        rx = np.ascontiguousarray(r[:, 0])
        ry = np.ascontiguousarray(r[:, 1])
        rz = np.ascontiguousarray(r[:, 2])
        _phasors(c.qx, c.x2, c.qpar, np.float32(1.), rx, rz, ones, x)
        _phasors(c.qy, c.y2, c.qpar, np.float32(-1.), ry, rz, a, y)
        return y.T, x

    def superpose(
        self,
        psi: np.ndarray,
        phasors: tuple[np.ndarray, np.ndarray],
        structure: np.ndarray | None = None,
    ) -> np.ndarray:
        '''Add the traps to ``psi`` in place and return it.

        A few traps are added by a kernel in one pass.  Many are a matrix
        product from BLAS, added in one pass.
        '''
        y, x = phasors
        if y.shape[1] <= FUSED_LIMIT:
            if structure is None:
                _superpose(psi, y, x)
            else:
                _superpose_structured(psi, y, x, structure)
            return psi
        term = y @ x
        if structure is None:
            _add(psi, term)
        else:
            _add_structured(psi, term, structure)
        return psi

    def quantize(self, psi: np.ndarray) -> Hologram:
        '''Return the phase of ``psi`` as ``uint8``, in one pass.'''
        out = np.empty(psi.shape, dtype=np.uint8)
        _quantize(psi, out)
        return out
