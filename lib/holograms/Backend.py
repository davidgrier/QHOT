from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable

import numpy as np

from QHOT.lib.traps import QTrap, TrapSpec
from QHOT.lib.types import Hologram
from .Optics import Optics


__all__ = ['Backend']


class Backend:

    r'''Computes holograms, quickly, on some kind of hardware.

    A backend computes what :func:`~QHOT.lib.holograms.reference.hologram`
    states, the phase of the superposition of the fields of the traps,

    .. math::

        \psi(x, y) = \sum_j a_j \, D(x, y; \mathbf r_j) \, S_j(x, y),

    and is tested against it.  It differs from the reference only in using
    the structure of the problem:

    * The displacement :math:`D` of a focus is the product of a phasor for
      each column and a phasor for each row,
      :math:`D = e^{i\varphi_y(y)} e^{i\varphi_x(x)}`.  So the fields of
      :math:`n` plain tweezers, whose structure is 1, add up to one matrix
      product,

      .. math::

          \psi_{mn} = \sum_j Y_{mj} X_{jn}, \qquad
          Y_{mj} = a_j e^{i\varphi_y^{(j)}(y_m)}, \quad
          X_{jn} = e^{i\varphi_x^{(j)}(x_n)},

      which hardware does very much faster than :math:`n` outer products.
    * A trap with a structuring field :math:`S` has the same product times
      a field that does not depend on where the trap is.  Traps that share
      a structure are summed first and the structure multiplies the sum,
      :math:`\psi \leftarrow \psi + S \odot (YX)`.
    * The field of a group is the sum of the fields of its members, each
      with the complex amplitude of the groups that contain it, so the
      groups can be flattened away.

    Nothing is remembered between holograms except the structuring fields,
    which are kept by their value (the kind of trap and its parameters)
    and so cannot go stale.  There is no cache to invalidate when a trap
    moves, because a hologram is computed from scratch in less time than
    the old cache took to sum.

    A subclass supplies the array operations: :meth:`calibrate`,
    :meth:`zeros`, :meth:`phasors`, :meth:`superpose`, :meth:`quantize`
    and :meth:`upload`.  A backend is used by one thread at a time.

    Parameters
    ----------
    cache : int
        Number of structuring fields to keep.  Default: 64.

    See Also
    --------
    QHOT.lib.holograms.reference : The algorithm, stated plainly.
    QHOT.lib.holograms.NumpyBackend.NumpyBackend : Computes on the CPU.
    QHOT.lib.holograms.TorchBackend.TorchBackend : Computes with PyTorch.
    '''

    name = 'abstract'

    def __init__(self, cache: int = 64) -> None:
        self.cache = int(cache)
        self._calibration: tuple | None = None
        self._context = None
        self._structures: OrderedDict = OrderedDict()

    def hologram(self,
                 pattern: Iterable[TrapSpec],
                 optics: Optics) -> Hologram:
        r'''Return the hologram of a pattern of traps.

        The phase of the superposition :math:`\psi` of the fields of the
        traps, quantized to 8 bits.

        Parameters
        ----------
        pattern : iterable of TrapSpec
            The top-level traps and groups.
        optics : Optics
            The calibration.

        Returns
        -------
        Hologram
            The phase of the superposition, as ``uint8``.
        '''
        context = self._context_for(optics)
        families = self._families(pattern, optics)
        psi = self.zeros(context)
        for key, (positions, amplitudes) in families.items():
            positions = optics.toSLM(np.array(positions, dtype=float))
            amplitudes = np.array(amplitudes, dtype=complex)
            phasors = self.phasors(context, positions, amplitudes)
            structure = None if key is None else self._structure(key, optics)
            psi = self.superpose(psi, phasors, structure)
        return self.quantize(psi)

    def _families(self, pattern: Iterable[TrapSpec], optics: Optics) -> dict:
        '''Sort the traps into families that share a structuring field.

        Returns
        -------
        dict
            Maps the structure to the positions and the amplitudes of the
            traps that have it.  The key ``None`` is for plain tweezers.
        '''
        families: dict = {}
        for top in pattern:
            for spec, amplitude in top.components():
                key = (spec.kind, spec.params)
                if self._structure(key, optics) is None:
                    key = None
                positions, amplitudes = families.setdefault(key, ([], []))
                positions.append(spec.r)
                amplitudes.append(amplitude)
        return families

    def _context_for(self, optics: Optics):
        '''Return what the backend keeps of the optics, remaking it only
        when the calibration has changed.'''
        calibration = tuple(optics.settings.items())
        if calibration != self._calibration:
            self._context = self.calibrate(optics)
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

    def calibrate(self, optics: Optics):
        r'''Return the coordinates of the optics that this backend needs.

        These are the vectors of the phase gradients along :math:`x` and
        :math:`y` and of the squares of the coordinates, in the form that
        this backend computes with.  They are made again only when the
        calibration changes.

        Parameters
        ----------
        optics : Optics
            The calibration.
        '''
        raise NotImplementedError

    def zeros(self, context):
        '''Return a field with no light in it.

        Parameters
        ----------
        context
            What :meth:`calibrate` returned.
        '''
        raise NotImplementedError

    def phasors(self,
                context,
                positions: np.ndarray,
                amplitudes: np.ndarray):
        r'''Return the phasors of :math:`n` traps, amplitudes included.

        The field of the traps is the product of two matrices: :math:`Y`,
        with a row for each row of the hologram and a column for each
        trap, and :math:`X`, with a row for each trap and a column for
        each column of the hologram,

        .. math::

            Y_{mj} = a_j \, e^{i\varphi_y^{(j)}(y_m)}, \qquad
            X_{jn} = e^{i\varphi_x^{(j)}(x_n)}.

        They are returned as a pair, so that :meth:`superpose` can choose
        how to multiply them.

        Parameters
        ----------
        context
            What :meth:`calibrate` returned.
        positions : np.ndarray
            Positions of the traps in the SLM plane, shape ``(n, 3)``.
        amplitudes : np.ndarray
            Complex amplitude :math:`a_j` of each trap, shape ``(n,)``.

        Returns
        -------
        tuple
            :math:`(Y, X)`, in the form that this backend computes with.
        '''
        raise NotImplementedError

    def superpose(self, psi, phasors, structure=None):
        r'''Add the field of some traps to the field.

        .. math::

            \psi \leftarrow \psi + S \odot (Y X),

        or :math:`\psi + YX` if there is no structure.  It does this in as
        few passes over the arrays as the hardware allows, and may change
        ``psi`` in place.

        Parameters
        ----------
        psi
            The field so far.
        phasors
            What :meth:`phasors` returned.
        structure
            The structuring field :math:`S`, as :meth:`upload` returned
            it, or ``None``.

        Returns
        -------
        The new field.
        '''
        raise NotImplementedError

    def quantize(self, psi) -> Hologram:
        r'''Return the phase of a field as 8-bit integers on the host.

        Parameters
        ----------
        psi
            The field.

        Returns
        -------
        Hologram
            :math:`\lfloor 128 \arg\psi / \pi + 127 \rfloor`, as ``uint8``.
        '''
        raise NotImplementedError

    def upload(self, field: np.ndarray):
        '''Return a structuring field in the form that this backend
        computes with.

        Parameters
        ----------
        field : np.ndarray
            A complex array made on the host.
        '''
        raise NotImplementedError
