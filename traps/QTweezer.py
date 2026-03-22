from QHOT.lib.traps.QTrap import QTrap


class QTweezer(QTrap):

    '''Single Gaussian optical tweezer.

    Subclass of ``QTrap`` with no additional properties or structure.
    The trapping beam is a plain focused Gaussian; all behaviour is
    inherited directly from ``QTrap``.
    '''


if __name__ == '__main__':  # pragma: no cover
    QTweezer.example()
