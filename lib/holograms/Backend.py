from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable

import numpy as np

from QHOT.lib.traps import QTrap, TrapSpec
from QHOT.lib.types import Hologram
from .Optics import Optics


__all__ = ['Backend']


class Backend:

    '''Computes holograms, quickly, on some kind of hardware.

    A backend computes what :func:`~QHOT.lib.holograms.reference.hologram`
    states, and is tested against it.  What it does differently is to use
    the structure of the problem:

    * The field of a focus is the outer product of a factor for each row
      and a factor for each column.  So the fields of ``n`` plain
      tweezers add up to one matrix product, ``(rows x n) @ (n x columns)``,
      which hardware does very much faster than ``n`` outer products.
    * A trap with a structuring field is that product times a field that
      does not depend on where the trap is.  Traps that share the same
      structure are summed first, and the structure multiplies the sum.
    * The field of a group is the sum of the fields of its members,
      weighted by the amplitudes of the groups that contain them, so the
      groups can be flattened away.

    Nothing is remembered between holograms except the structuring fields,
    which are kept by their value (the kind of trap and its parameters)
    and so cannot go stale.  There is no cache to invalidate when a trap
    moves, because a hologram is computed from scratch in the time that
    the cache used to take to sum.

    A subclass supplies the array operations: :meth:`prepare`,
    :meth:`zeros`, :meth:`ramps`, :meth:`accumulate`, :meth:`quantize`
    and :meth:`upload`.  A backend is used by one thread
    at a time.

    Parameters
    ----------
    cache : int
        Number of structuring fields to keep.  Default: 64.
    '''

    name = 'abstract'

    def __init__(self, cache: int = 64) -> None:
        self.cache = int(cache)
        self._calibration: tuple | None = None
        self._context = None
        self._structures: OrderedDict = OrderedDict()

    def hologram(self, pattern: Iterable[TrapSpec],
                 optics: Optics) -> Hologram:
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
        context = self._prepare(optics)
        batches = self._batches(pattern, optics)
        psi = self.zeros(context)
        for key, (positions, weights) in batches.items():
            R = optics.transform(np.array(positions, dtype=float))
            ramps = self.ramps(context, R, np.array(weights, dtype=complex))
            structure = None if key is None else self._structure(key, optics)
            psi = self.accumulate(psi, ramps, structure)
        return self.quantize(psi)

    def _batches(self, pattern: Iterable[TrapSpec], optics: Optics) -> dict:
        '''Sort the traps by structure.

        Returns
        -------
        dict
            Maps the structure to the positions and the weights of the
            traps that have it.  The key ``None`` is for plain tweezers.
        '''
        batches: dict = {}
        for top in pattern:
            for spec, weight in top.weighted():
                key = (spec.kind, spec.params)
                if self._structure(key, optics) is None:
                    key = None
                positions, weights = batches.setdefault(key, ([], []))
                positions.append(spec.r)
                weights.append(weight)
        return batches

    def _prepare(self, optics: Optics):
        '''Return what the backend keeps of the optics, remaking it only
        when the calibration has changed.'''
        calibration = tuple(optics.settings.items())
        if calibration != self._calibration:
            self._context = self.prepare(optics)
            self._calibration = calibration
            self._structures.clear()
        return self._context

    def _structure(self, key: tuple, optics: Optics):
        '''Return the structuring field for ``(kind, params)``.

        The class of the trap makes it, once, from the geometry and the
        parameters.  ``None`` means that the trap has no structure.
        '''
        if key in self._structures:
            self._structures.move_to_end(key)
            return self._structures[key]
        import QHOT.traps  # noqa: F401 -- registers the trap classes
        kind, params = key
        cls = QTrap._registry.get(kind)
        if cls is None:
            raise KeyError(f'unknown trap kind {kind!r}')
        field = cls.structuringField(optics.geometry, **dict(params))
        value = None if field is None else self.upload(np.asarray(field))
        self._structures[key] = value
        while len(self._structures) > self.cache:
            self._structures.popitem(last=False)
        return value

    # The array operations that a backend provides.

    def prepare(self, optics: Optics):
        '''Return the vectors of the optics, in the form that this backend
        computes with.'''
        raise NotImplementedError

    def zeros(self, context):
        '''Return an empty field.'''
        raise NotImplementedError

    def ramps(self, context, R: np.ndarray, weights: np.ndarray):
        '''Return the phase ramps of ``n`` traps, weights included.

        The field of the traps is the product of two matrices, the first
        with a column for each trap and a row for each row of the
        hologram and the second with a row for each trap and a column for
        each column of the hologram.  They are returned as a pair, so
        that :meth:`accumulate` can choose how to multiply them.

        Parameters
        ----------
        context
            What :meth:`prepare` returned.
        R : np.ndarray
            Positions of the traps in the SLM plane, shape ``(n, 3)``.
        weights : np.ndarray
            Complex weight of each trap, shape ``(n,)``.
        '''
        raise NotImplementedError

    def accumulate(self, psi, ramps, structure=None):
        '''Add the field of traps to the field, shaped by a structure.

        This is ``psi + (rows @ columns) * structure``, or without the
        structure if there is none.  It does it in as few passes over the
        arrays as the hardware allows, and may change ``psi`` in place.

        Parameters
        ----------
        psi
            The field so far.
        ramps
            What :meth:`ramps` returned.
        structure
            What :meth:`upload` returned for the structuring field, or
            ``None``.
        '''
        raise NotImplementedError

    def quantize(self, psi) -> Hologram:
        '''Return the phase of a field as 8-bit integers on the host.'''
        raise NotImplementedError

    def upload(self, field: np.ndarray):
        '''Return a structuring field in the form that this backend
        computes with.'''
        raise NotImplementedError
