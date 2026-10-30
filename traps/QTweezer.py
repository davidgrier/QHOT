from QHOT.lib.traps.QTrap import QTrap


class QTweezer(QTrap):

    '''Single Gaussian optical tweezer.

    Subclass of ``QTrap`` with no additional properties or structure.
    The trapping beam is a plain focused Gaussian; all behavior is
    inherited directly from ``QTrap``.

    Notes
    -----
    A single beam focused by a lens traps a small dielectric particle with
    the gradient force of its intensity (:cite:p:`ashkin1986`).  An array
    of tweezers is projected from one beam by a hologram
    (:cite:p:`dufresne1998,dufresne2001`).
    '''


if __name__ == '__main__':  # pragma: no cover
    QTweezer.example()
