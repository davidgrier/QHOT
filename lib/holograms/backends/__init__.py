'''Backends that compute holograms, one for each kind of hardware.

Every backend computes what
:func:`~QHOT.lib.holograms.reference.hologram` states, and is tested
against it.  ``Backend`` is the algorithm; the others supply the array
operations for the hardware:

``NumpyBackend``
    The CPU, with nothing but NumPy.
``NumbaBackend``
    The CPU, with compiled kernels on all the cores (needs ``numba``).
``TorchBackend``
    An Apple GPU, CUDA or the CPU (needs ``torch``).
``CupyBackend``
    An NVIDIA GPU (needs ``cupy``).

The optional backends are imported when they are asked for, so importing
this package does not import ``numba``, ``torch`` or ``cupy``:
``from QHOT.lib.holograms.backends import TorchBackend`` imports torch,
and fails with ``ImportError`` if it is not installed.
'''
import importlib

from ._base import Backend
from ._numpy import NumpyBackend


__all__ = ['Backend', 'NumpyBackend']

#: The optional backends, and the private modules that have them.
_OPTIONAL = {
    'NumbaBackend': '_numba',
    'TorchBackend': '_torch',
    'CupyBackend': '_cupy',
}


def __getattr__(name: str):
    '''Import an optional backend when it is asked for.'''
    if name in _OPTIONAL:
        module = importlib.import_module(f'.{_OPTIONAL[name]}', __name__)
        return getattr(module, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_OPTIONAL))
