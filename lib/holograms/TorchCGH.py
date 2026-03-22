'''PyTorch-accelerated CGH computation pipeline.

Supports NVIDIA CUDA, AMD ROCm, and Apple Silicon MPS via a single
implementation that selects the best available device at startup.
'''
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui

from QHOT.lib.types import Field, Hologram
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from .CGH import CGH

try:
    import torch
except ImportError:
    torch = None


def _select_device() -> 'torch.device':
    '''Return the best available torch device.

    Probes MPS (Apple Silicon), then CUDA (NVIDIA/AMD ROCm),
    then falls back to CPU.

    Returns
    -------
    torch.device
        The selected compute device.
    '''
    if torch.backends.mps.is_available():
        return torch.device('mps')
    if torch.cuda.is_available():
        return torch.device('cuda')
    return torch.device('cpu')


class TorchCGH(CGH):

    '''CGH pipeline accelerated by PyTorch.

    Automatically selects the best available device (Apple Silicon
    MPS, NVIDIA/AMD CUDA/ROCm, or CPU).  Displacement-field
    computation and per-frame accumulation run on-device; structure
    arrays (which depend on ``theta`` and ``qr``) and the final
    quantize step run on the CPU.

    Requires the ``torch`` package (``pip install torch``).  For AMD
    GPUs install the ROCm wheel instead of the default CUDA wheel.

    Parameters
    ----------
    *args, **kwargs
        Forwarded to ``CGH.__init__``.

    Raises
    ------
    ImportError
        If ``torch`` is not installed.
    '''

    def __init__(self, *args, **kwargs) -> None:
        if torch is None:
            raise ImportError(
                'torch is required for TorchCGH. '
                'Install it with: pip install torch')
        self.device = _select_device()
        super().__init__(*args, **kwargs)

    def updateGeometry(self) -> None:
        '''Recompute geometry, storing phase-ramp vectors on-device.

        Calls the base ``updateGeometry`` to build ``iqx``, ``iqy``,
        ``iqxz``, ``iqyz``, ``theta``, and ``qr`` as NumPy arrays,
        then uploads the phase-ramp vectors to ``self.device`` as
        torch tensors and allocates the on-device field accumulator.
        '''
        super().updateGeometry()
        self._tiqx = torch.as_tensor(self.iqx, device=self.device)
        self._tiqy = torch.as_tensor(self.iqy, device=self.device)
        self._tiqxz = torch.as_tensor(self.iqxz, device=self.device)
        self._tiqyz = torch.as_tensor(self.iqyz, device=self.device)
        self._torch_field = torch.zeros(
            self.shape, dtype=torch.complex64, device=self.device)

    def fieldOf(self, trap: QTrap) -> 'torch.Tensor':
        '''Compute the on-device complex field contribution of a trap.

        The displacement field is computed from on-device phase-ramp
        vectors.  Structure fields returned by ``trap.structure()``
        are uploaded to the device on first use.  Caching semantics
        are identical to the base class.

        Parameters
        ----------
        trap : QTrap
            The trap or group to compute the field for.

        Returns
        -------
        torch.Tensor
            Complex field tensor on ``self.device`` with shape
            ``self.shape``.
        '''
        self._connectTrap(trap)
        if trap not in self._field_cache:
            r = self.transform(QtGui.QVector3D(*trap.r))
            rx = np.float32(r.x())
            ry = np.float32(r.y())
            rz = np.float32(r.z())
            ex = torch.exp(self._tiqx * rx + self._tiqxz * rz)
            ey = torch.exp(self._tiqy * ry + self._tiqyz * rz)
            if isinstance(trap, QTrapGroup):
                self._field_cache[trap] = torch.outer(ey, ex)
            else:
                amplitude = np.complex64(
                    trap.amplitude * np.exp(1j * trap.phase))
                amp_t = torch.tensor(
                    complex(amplitude),
                    dtype=torch.complex64, device=self.device)
                self._field_cache[trap] = torch.outer(amp_t * ey, ex)
        if trap not in self._structure_cache:
            if isinstance(trap, QTrapGroup):
                child_sum = sum(
                    (self.fieldOf(child) for child in trap),
                    torch.zeros(self.shape, dtype=torch.complex64,
                                device=self.device))
                self._structure_cache[trap] = (
                    child_sum * self._field_cache[trap].conj())
            elif hasattr(trap, 'structure'):
                s = trap.structure(self)
                if isinstance(s, np.ndarray):
                    self._structure_cache[trap] = torch.as_tensor(
                        s.astype(np.complex64), device=self.device)
                else:
                    self._structure_cache[trap] = s
            else:
                self._structure_cache[trap] = 1.
        return self._field_cache[trap] * self._structure_cache[trap]

    @QtCore.pyqtSlot(list)
    def compute(self, traps: list[QTrap]) -> Hologram:
        '''Compute the phase hologram on-device, then transfer to CPU.

        Parameters
        ----------
        traps : list[QTrap]
            Traps (or group members) to include in the hologram.

        Returns
        -------
        Hologram
            Quantized phase hologram as a uint8 NumPy array.
        '''
        self._torch_field.zero_()
        seen: set = set()
        for trap in traps:
            item = self._topLevel(trap)
            if item not in seen:
                self._torch_field += self.fieldOf(item)
                seen.add(item)
        self.phase = self.quantize(self._torch_field.cpu().numpy())
        self.hologramReady.emit(self.phase)
        return self.phase

    def bless(self, field: Field | None) -> 'torch.Tensor | None':
        '''Cast a CPU array to complex64 and upload it to ``self.device``.

        Parameters
        ----------
        field : np.ndarray or None
            CPU array to transfer, or None.

        Returns
        -------
        torch.Tensor or None
            Tensor on ``self.device``, or None if input is None.
        '''
        if field is None:
            return None
        return torch.as_tensor(
            np.asarray(field, dtype=np.complex64), device=self.device)

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Demonstrate TorchCGH device selection and hologram computation.'''
        from QHOT.traps.QTweezer import QTweezer
        cgh = cls()
        print(f'TorchCGH device: {cgh.device}')
        trap = QTweezer(r=(cgh.xc, cgh.yc, 0.))
        hologram = cgh.compute([trap])
        print(f'TorchCGH: hologram shape={hologram.shape}, '
              f'dtype={hologram.dtype}')


if __name__ == '__main__':  # pragma: no cover
    TorchCGH.example()
