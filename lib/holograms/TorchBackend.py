from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from QHOT.lib.types import Hologram
from .Backend import Backend
from .Optics import Optics

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None


__all__ = ['TorchBackend']


def select_device() -> 'torch.device':
    '''Return the best device that torch has: Apple's GPU (MPS), then
    CUDA (NVIDIA, or AMD with ROCm), then the CPU.'''
    if torch.backends.mps.is_available():
        return torch.device('mps')
    if torch.cuda.is_available():
        return torch.device('cuda')
    return torch.device('cpu')


class TorchBackend(Backend):

    '''Computes holograms with PyTorch, on a GPU if there is one.

    The whole computation happens on the device, including the
    quantization, so that only the finished 8-bit hologram crosses back to
    the host.  The fields are complex tensors, and the sum over the
    plain tweezers is one complex matrix product.  A structured term is
    added with a single fused multiply-add.

    The structuring fields are made on the host by the traps, since some
    of them need functions that torch does not have (a Bessel function of
    any order), and are uploaded once.

    Parameters
    ----------
    device : torch.device or str or None
        Where to compute.  Default: the best device available.
    cache : int
        Number of structuring fields to keep.  Default: 64.

    Raises
    ------
    ImportError
        If ``torch`` is not installed.
    '''

    name = 'torch'

    def __init__(self, device=None, cache: int = 64) -> None:
        if torch is None:
            raise ImportError('torch is required for TorchBackend. '
                              'Install it with: pip install torch')
        super().__init__(cache)
        self.device = torch.device(device) if device else select_device()

    def _tensor(self, array: np.ndarray,
                dtype=np.float32) -> 'torch.Tensor':
        array = np.ascontiguousarray(array, dtype=dtype)
        return torch.as_tensor(array, device=self.device)

    def calibrate(self, optics: Optics) -> SimpleNamespace:
        return SimpleNamespace(
            shape=optics.shape, qpar=float(optics.qpar),
            qx=self._tensor(optics.qx), qy=self._tensor(optics.qy),
            x2=self._tensor(optics.x**2), y2=self._tensor(optics.y**2))

    def zeros(self, c: SimpleNamespace) -> 'torch.Tensor':
        return torch.zeros(c.shape, dtype=torch.complex64,
                           device=self.device)

    def phasors(self, c: SimpleNamespace, R: np.ndarray,
              amplitudes: np.ndarray) -> tuple:
        R = self._tensor(R)
        w = self._tensor(amplitudes, np.complex64)[:, None]
        px = c.qx * R[:, 0:1] + c.qpar * c.x2 * R[:, 2:3]    # n x width
        py = -c.qy * R[:, 1:2] + c.qpar * c.y2 * R[:, 2:3]   # n x height
        ex = torch.complex(torch.cos(px), torch.sin(px))
        ey = torch.complex(torch.cos(py), torch.sin(py)) * w
        return ey.T, ex

    def superpose(self, psi: 'torch.Tensor', phasors: tuple,
                   structure: 'torch.Tensor | None' = None
                   ) -> 'torch.Tensor':
        rows, columns = phasors
        if rows.shape[1] == 1:                       # one trap: an outer
            if structure is None:                    # product, fused with
                return psi.addcmul_(rows, columns)   # the addition
            return psi.addcmul_(structure * rows, columns)
        term = rows @ columns
        if structure is None:
            return psi.add_(term)
        return psi.addcmul_(term, structure)

    def quantize(self, psi: 'torch.Tensor') -> Hologram:
        phase = (128. / np.pi) * torch.atan2(psi.imag, psi.real) + 127.
        return phase.to(torch.uint8).cpu().numpy()

    def upload(self, field: np.ndarray) -> 'torch.Tensor':
        return self._tensor(field, np.complex64)
