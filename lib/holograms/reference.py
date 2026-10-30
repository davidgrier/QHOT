r'''The hologram of a pattern of traps, stated as plainly as possible.

This is the algorithm of linear superposition
(:cite:p:`dufresne2001,curtis2002`), written to be read.
It is slow and keeps nothing between calls, which is the point: it is the
standard that every faster implementation is tested against.  The
engines of QHOT are this, made quick.

A trap focuses the light at a position :math:`\mathbf r` and shapes the
focus.  Its field in the plane of the SLM is the product of three things,

.. math::

    \psi(x, y) = a \; D(x, y; \mathbf r) \; S(x, y),

the complex amplitude :math:`a = A e^{i\varphi}` of the trap, the
*displacement* :math:`D`, which is the phase ramp that moves a focus to
:math:`\mathbf r` (:func:`displacement`), and the *structuring field*
:math:`S`, which shapes the focus and does not depend on where the trap is
(:func:`structuringField`): 1 for a plain tweezer, a helical phase
:math:`e^{i\ell\theta}` for a vortex.

A group has no structuring field of its own.  It is the superposition of
the fields of its members, measured from the displacement of the group's
own center :math:`\mathbf r_G`, and this holds at every depth of nesting,

.. math::

    S_G = D_G^{*} \sum_{k \in G} \psi_k, \qquad
    \psi_G = a_G \, D_G \, S_G = a_G \sum_{k \in G} \psi_k.

The displacement of the group cancels (:math:`|D_G| = 1`), so a group is
exactly the sum of its members.  The complex amplitude of a plain group is
1, so that a member means the same in a group as alone.  A composite, a
group that is used as a single trap, has an amplitude and a phase of its
own.  The structure :math:`S_G` is worth having because it does not change
when the group moves as a rigid body, so a cache of it can be reused until
the members move relative to one another.

The hologram is the phase of the superposition of the fields of all the
traps in the pattern, quantized to 8 bits (:func:`quantize`),

.. math::

    H = \left\lfloor \frac{128}{\pi} \arg \sum_j \psi_j + 127
        \right\rfloor.
'''
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from QHOT.lib.traps import QTrap, TrapSpec
from QHOT.lib.types import Field, Hologram
from .optics import Optics


__all__ = [
    'displacement',
    'structuringField',
    'structure',
    'field',
    'quantize',
    'hologram',
]


def displacement(r, optics: Optics) -> Field:
    r'''Return the displacement :math:`D(x, y; \mathbf r)`.

    This is the phase ramp that moves a focus to ``r``, the outer product
    of the phasor of each row and the phasor of each column
    (:meth:`~QHOT.lib.holograms.optics.Optics.phasors`).

    Parameters
    ----------
    r : array_like
        Position (x, y, z) in the camera plane [pixels].
    optics : Optics
        The calibration.

    Returns
    -------
    Field
        A complex array of unit modulus, the shape of the hologram.
    '''
    ey, ex = optics.phasors(r)
    return np.outer(ey, ex)


def structuringField(spec: TrapSpec, optics: Optics) -> Field | float:
    '''Return the structuring field of a trap that is not a group.

    The class of the trap makes it from the geometry of the SLM plane
    and the parameters in the spec.

    Parameters
    ----------
    spec : TrapSpec
        The trap.
    optics : Optics
        The calibration.

    Returns
    -------
    Field or float
        The structuring field :math:`S`, or 1 for a trap without
        structure.
    '''
    import QHOT.traps  # noqa: F401 -- registers the trap classes
    cls = QTrap._registry.get(spec.kind)
    if cls is None:
        raise KeyError(f'unknown trap kind {spec.kind!r}')
    structure = cls.structuringField(optics.geometry, **spec.parameters())
    return 1. if structure is None else structure


def structure(spec: TrapSpec, optics: Optics) -> Field | float:
    r'''Return the structuring field of a trap or group.

    For a group it is the superposition of the fields of the members,
    measured from the displacement of the group,
    :math:`S_G = D_G^{*} \sum_{k \in G} \psi_k`.

    Parameters
    ----------
    spec : TrapSpec
        The trap or group.
    optics : Optics
        The calibration.

    Returns
    -------
    Field or float
        The structuring field :math:`S`.
    '''
    if not spec.isGroup:
        return structuringField(spec, optics)
    total = np.zeros(optics.shape, dtype=complex)
    for member in spec.children:
        total += field(member, optics)
    return total * np.conj(displacement(spec.r, optics))


def field(spec: TrapSpec, optics: Optics) -> Field:
    r'''Return the field :math:`\psi = a D S` of a trap or group.

    Parameters
    ----------
    spec : TrapSpec
        The trap or group.
    optics : Optics
        The calibration.

    Returns
    -------
    Field
        A complex array, the shape of the hologram.
    '''
    amplitude = spec.amplitude * np.exp(1j * spec.phase)
    return amplitude * displacement(spec.r, optics) * structure(spec, optics)


def quantize(psi: Field) -> Hologram:
    r'''Return the phase of a complex field as 8-bit integers.

    Parameters
    ----------
    psi : Field
        A complex field.

    Returns
    -------
    Hologram
        :math:`\lfloor 128 \arg\psi / \pi + 127 \rfloor`, as ``uint8``.
    '''
    return ((128. / np.pi) * np.angle(psi) + 127.).astype(np.uint8)


def hologram(pattern: Iterable[TrapSpec], optics: Optics) -> Hologram:
    r'''Return the hologram of a pattern of traps.

    Parameters
    ----------
    pattern : iterable of TrapSpec
        The top-level traps and groups.
    optics : Optics
        The calibration.

    Returns
    -------
    Hologram
        The phase of the superposition :math:`\sum_j \psi_j` of the
        fields, as ``uint8``.
    '''
    psi = np.zeros(optics.shape, dtype=complex)
    for spec in pattern:
        psi += field(spec, optics)
    return quantize(psi)
