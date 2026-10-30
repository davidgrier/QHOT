from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from QHOT.lib.types import Hologram
from ._base import Backend
from ..optics import Optics

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

    def _tensor(self,
                array: np.ndarray,
                dtype=np.float32) -> 'torch.Tensor':
        '''Return an array as a tensor on the device.'''
        array = np.ascontiguousarray(array, dtype=dtype)
        return torch.as_tensor(array, device=self.device)

    def calibrate(self, optics: Optics) -> SimpleNamespace:
        '''Return the vectors of the optics as tensors on the device.'''
        return SimpleNamespace(
            shape=optics.shape,
            qpar=float(optics.qpar),
            qx=self._tensor(optics.qx),
            qy=self._tensor(optics.qy),
            x2=self._tensor(optics.x**2),
            y2=self._tensor(optics.y**2),
        )

    def zeros(self, c: SimpleNamespace) -> 'torch.Tensor':
        '''Return an empty ``complex64`` field on the device.'''
        return torch.zeros(
            c.shape,
            dtype=torch.complex64,
            device=self.device,
        )

    def phasors(self,
                c: SimpleNamespace,
                positions: np.ndarray,
                amplitudes: np.ndarray) -> tuple:
        r'''Return :math:`(Y, X)` as ``complex64`` tensors on the device.

        The phases are made with ``cos`` and ``sin`` of real tensors,
        which every device supports.
        '''
        r = self._tensor(positions)
        a = self._tensor(amplitudes, np.complex64)[:, None]
        px = c.qx * r[:, 0:1] + c.qpar * c.x2 * r[:, 2:3]    # n x width
        py = -c.qy * r[:, 1:2] + c.qpar * c.y2 * r[:, 2:3]   # n x height
        x = torch.complex(torch.cos(px), torch.sin(px))
        y = torch.complex(torch.cos(py), torch.sin(py)) * a
        return y.T, x

    def superpose(self,
                  psi: 'torch.Tensor',
                  phasors: tuple,
                  structure: 'torch.Tensor | None' = None) -> 'torch.Tensor':
        '''Add the traps to ``psi`` in place and return it.

        One trap is an outer product, fused with the addition into a
        single pass; more are a complex matrix product.
        '''
        y, x = phasors
        if y.shape[1] == 1:
            if structure is None:
                return psi.addcmul_(y, x)
            return psi.addcmul_(structure * y, x)
        term = y @ x
        if structure is None:
            return psi.add_(term)
        return psi.addcmul_(term, structure)

    def quantize(self, psi: 'torch.Tensor') -> Hologram:
        '''Return the phase of ``psi`` as ``uint8`` on the host.

        The phase is taken and scaled on the device, so that only the
        finished bytes cross to the host.
        '''
        phase = (128. / np.pi) * torch.atan2(psi.imag, psi.real) + 127.
        return phase.to(torch.uint8).cpu().numpy()

    def upload(self, field: np.ndarray) -> 'torch.Tensor':
        '''Return the structuring field as a ``complex64`` tensor.'''
        return self._tensor(field, np.complex64)
