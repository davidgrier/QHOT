'''Patterns of traps and calibrations that the hologram tests share.'''
import numpy as np

from QHOT.lib.holograms import Optics
from QHOT.lib.traps import QTrapGroup
from QHOT.traps import QRingTrap, QTweezer, QVortex

__all__ = ('SHAPE CALIBRATIONS Composite optics tweezer group levels '
           'patterns').split()

SHAPE = (48, 64)
CALIBRATIONS = {
    'default': dict(),
    'rotated': dict(thetac=15.),
    'offset': dict(xc=20., yc=30., xs=3., ys=-2.),
    'tilted': dict(phis=20.),
    'deep': dict(zc=3., splay=0.02),
    'everything': dict(thetac=-10., zc=2., splay=0.03, phis=12.,
                       xs=2., ys=1., xc=28., yc=26.),
}


class Composite(QTrapGroup):

    '''A group that is used as a single trap, for the tests.'''

    composite = True


def optics(**kwargs) -> Optics:
    return Optics(**{**dict(shape=SHAPE, xc=32., yc=24.), **kwargs})


def tweezer(x, y, z=0., phase=0.5, **kw):
    return QTweezer(r=(x, y, z), phase=phase, **kw)


def group(*members, r=(32., 24., 0.)):
    g = QTrapGroup(r=r)
    g.addTrap(list(members))
    return g


def levels(a, b):
    '''Return the difference between two holograms, in levels of phase.'''
    d = np.abs(a.astype(int) - b.astype(int))
    return np.minimum(d, 256 - d)


def patterns():
    '''Yield (name, list of traps) for patterns that exercise the cases.'''
    yield 'tweezers', [tweezer(10, 12, 1., 0.1), tweezer(40, 30, -2., 1.),
                       tweezer(25, 22, 3., 2.), tweezer(50, 10, 0., 3.)]
    yield 'weighted', [tweezer(10, 12, amplitude=2.5),
                       tweezer(40, 30, phase=2., amplitude=0.4)]
    yield 'vortex', [QVortex(r=(30, 24, 0), ell=4, phase=0.3)]
    yield 'ring', [QRingTrap(r=(30, 24, 0), radius=8., ell=3, phase=0.4)]
    yield 'vortices', [QVortex(r=(10 + 9 * n, 12 + 5 * n, n), ell=2 + n % 3,
                               phase=0.3 * n, amplitude=1. + 0.2 * n)
                       for n in range(6)]
    yield 'group', [group(tweezer(20, 20), tweezer(40, 28, 2.),
                          QVortex(r=(30, 15, 1), ell=3, phase=0.2))]
    yield 'nested', [group(group(tweezer(10, 10), tweezer(14, 12, 1.)),
                           QRingTrap(r=(40, 30, 0), radius=5., ell=2,
                                     phase=0.5),
                           r=(30., 20., 0.)),
                     tweezer(50, 40, 2., 1.2)]
    composite = Composite(r=(32., 24., 0.), amplitude=2.5, phase=0.9)
    composite.addTrap([tweezer(20, 20), QVortex(r=(40, 28, 0), ell=2,
                                                phase=1.1)])
    yield 'composite', [composite, tweezer(10, 40, phase=0.2)]
    yield 'composite in group', [group(
        Composite(r=(20., 20., 0.), amplitude=0.5, phase=2.),
        tweezer(45, 35))]
