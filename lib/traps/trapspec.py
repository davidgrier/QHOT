from __future__ import annotations

import cmath
from collections.abc import Iterator
from dataclasses import dataclass


__all__ = ['TrapSpec']

#: A trap that is not a group, and its complex amplitude in a pattern.
Component = tuple['TrapSpec', complex]


@dataclass(frozen=True)
class TrapSpec:

    '''What a hologram needs to know about a trap, as a plain value.

    A ``TrapSpec`` is a snapshot of a trap, or of a group and everything
    that it contains.  It holds numbers and strings only, so it can be
    handed to another thread, compared, hashed and kept as the key of a
    cache.  Nothing that happens to the trap afterwards changes it.  Make
    one with :meth:`~QHOT.lib.traps.QTrap.QTrap.spec`.

    A pattern of traps is a tuple of the specs of its top-level traps.

    Parameters
    ----------
    kind : str
        Name of the trap's class, which tells the hologram how to make
        the structuring field of the trap (see
        :meth:`~QHOT.lib.traps.QTrap.QTrap.structuringField`).
    r : tuple[float, float, float]
        Position of the trap in the camera plane [pixels]: (x, y, z).  For
        a group, the center that the group is moved by.
    amplitude : float
        Relative amplitude of the field.  Always 1 for a plain group,
        whose members have amplitudes of their own; a composite has an
        amplitude of its own.
    phase : float
        Relative phase of the field [radians].  Always 0 for a plain
        group; a composite has a phase of its own.
    params : tuple[tuple[str, object], ...]
        The parameters of the structuring field, as sorted ``(name,
        value)`` pairs: ``(('ell', 3),)`` for a vortex.
    children : tuple[TrapSpec, ...]
        The members of a group.
    isGroup : bool
        Whether the spec is that of a group, which may have no members.
    '''

    kind: str
    r: tuple[float, float, float]
    amplitude: float = 1.
    phase: float = 0.
    params: tuple[tuple[str, object], ...] = ()
    children: tuple[TrapSpec, ...] = ()
    isGroup: bool = False

    def parameters(self) -> dict[str, object]:
        '''Return the parameters of the structuring field as a dict.'''
        return dict(self.params)

    def components(self,
                   envelope: complex = 1.) -> Iterator[Component]:
        r'''Yield the components of the superposition, with their amplitudes.

        The field of a group is the sum of the fields of its members, so
        the hologram of a pattern is the superposition of the fields of
        the traps that are not groups.  The complex amplitude of each is
        the product of its own :math:`a = A e^{i\varphi}` and those of
        every group that contains it.  A plain group has an amplitude of 1,
        so a trap in one has the amplitude that it has alone; a composite
        scales all of its members.

        Parameters
        ----------
        envelope : complex
            The amplitude of what contains this spec.  Default: 1.

        Yields
        ------
        tuple[TrapSpec, complex]
            A trap that is not a group, and its complex amplitude.
        '''
        mine = envelope * self.amplitude * cmath.exp(1j * self.phase)
        if self.isGroup:
            for child in self.children:
                yield from child.components(mine)
        else:
            yield self, mine

    def leaves(self) -> Iterator[TrapSpec]:
        '''Yield the traps that are not groups, at any depth.'''
        if self.isGroup:
            for child in self.children:
                yield from child.leaves()
        else:
            yield self
