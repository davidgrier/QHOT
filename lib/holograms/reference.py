'''The hologram of a pattern of traps, stated as plainly as possible.

This is the algorithm of linear superposition [1]_, written to be read.
It is slow and keeps nothing between calls, which is the point: it is the
standard that every faster implementation is tested against.  The
engines of QHOT are this, made quick.

A focus at ``r`` has the field ``D(r)``, the phase ramp that moves it
there.  A trap shapes its focus with a structuring field ``S`` that does
not depend on where the trap is: 1 for a plain tweezer, a helical phase
for a vortex.  So the field of a trap with the complex amplitude ``a`` is::

    a * D(r) * S

A group has no structuring field of its own.  It is the superposition
of the fields of its members, measured from the group's own
displacement, and this holds at every depth of nesting::

    S(group) = sum(field(member) for member in group) / D(r_group)
    field(group) = a_group * D(r_group) * S(group)

The group's displacement cancels, so a group is exactly the sum of its
members.  The amplitude of a plain group is 1, so that a member means the
same in a group as alone.  A composite, a group that is used as a single
trap, has an amplitude and a phase of its own.  The structure of a group
is worth having because it does not change when the group moves as a rigid
body, so a cache of it can be reused until the members move relative to
one another.

The hologram is the phase of the sum of the fields of the traps in the
pattern, quantized to 8 bits.

References
----------
.. [1] J. E. Curtis, B. A. Koss, and D. G. Grier, "Dynamic holographic
   optical tweezers," *Opt. Commun.* **207**, 169 (2002).
   https://doi.org/10.1016/S0030-4018(02)01524-9
'''
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from QHOT.lib.traps import QTrap, TrapSpec
from QHOT.lib.types import Field, Hologram
from .Optics import Optics


__all__ = ('displacement structuringField structure field quantize '
           'hologram').split()


def displacement(r, optics: Optics) -> Field:
    '''Return the phase ramp ``D(r)`` that moves a focus to ``r``.'''
    ey, ex = optics.phasors(r)
    return np.outer(ey, ex)


def structuringField(spec: TrapSpec, optics: Optics) -> Field | float:
    '''Return the structuring field of a trap that is not a group.

    The class of the trap makes it from the geometry of the SLM plane
    and the parameters in the spec.  A trap without structure gives 1.
    '''
    import QHOT.traps  # noqa: F401 -- registers the trap classes
    cls = QTrap._registry.get(spec.kind)
    if cls is None:
        raise KeyError(f'unknown trap kind {spec.kind!r}')
    structure = cls.structuringField(optics.geometry, **spec.parameters())
    return 1. if structure is None else structure


def structure(spec: TrapSpec, optics: Optics) -> Field | float:
    '''Return the structuring field of a trap or group.

    For a group it is the superposition of the fields of the members,
    relative to the displacement of the group.
    '''
    if not spec.isGroup:
        return structuringField(spec, optics)
    total = np.zeros(optics.shape, dtype=complex)
    for member in spec.children:
        total += field(member, optics)
    return total * np.conj(displacement(spec.r, optics))


def field(spec: TrapSpec, optics: Optics) -> Field:
    '''Return the field of a trap or group.'''
    amplitude = spec.amplitude * np.exp(1j * spec.phase)
    return amplitude * displacement(spec.r, optics) * structure(spec, optics)


def quantize(psi: Field) -> Hologram:
    '''Return the phase of a complex field as 8-bit integers.'''
    return ((128. / np.pi) * np.angle(psi) + 127.).astype(np.uint8)


def hologram(pattern: Iterable[TrapSpec], optics: Optics) -> Hologram:
    '''Return the hologram of a pattern of traps.

    Parameters
    ----------
    pattern : iterable of TrapSpec
        The top-level traps and groups.
    optics : Optics
        The calibration.

    Returns
    -------
    Hologram
        The phase of the sum of the fields, as ``uint8``.
    '''
    psi = np.zeros(optics.shape, dtype=complex)
    for spec in pattern:
        psi += field(spec, optics)
    return quantize(psi)
