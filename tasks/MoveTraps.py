import math

import numpy as np

from QHOT.lib.tasks.QTask import QTask


class MoveTraps(QTask):

    '''Translate all traps by a 3D displacement over multiple frames.

    Moves every leaf trap in the overlay from its current position to
    ``r + (dx, dy, dz)`` via linear interpolation.  The displacement is
    divided into steps of at most ``step`` pixels (L2 norm) so that
    trapped particles are not lost.

    ``duration`` is computed automatically as
    ``ceil(sqrt(dx²+dy²+dz²) / step)`` frames (minimum 1).  Zero
    displacement completes in a single frame without moving anything.
    Setting any of ``dx``, ``dy``, ``dz``, or ``step`` via
    ``QTaskTree`` updates ``duration`` immediately.

    Parameters
    ----------
    dx : float
        Displacement along x [pixels].  Default: ``0.``.
    dy : float
        Displacement along y [pixels].  Default: ``0.``.
    dz : float
        Displacement along z [pixels].  Default: ``0.``.
    step : float
        Maximum displacement per frame [pixels].  Default: ``1.``.
    **kwargs
        Forwarded to ``QTask`` (e.g. ``overlay``, ``delay``).
        ``duration`` may not be supplied.

    Examples
    --------
    Move all traps 50 pixels to the right in steps of 2 pixels::

        manager.register(MoveTraps(overlay=overlay, dx=50., step=2.))
    '''

    parameters = [
        dict(name='dx',   type='float', value=0.,  default=0.),
        dict(name='dy',   type='float', value=0.,  default=0.),
        dict(name='dz',   type='float', value=0.,  default=0.),
        dict(name='step', type='float', value=1.,  default=1., min=0.01),
    ]

    def __init__(self,
                 dx: float = 0.,
                 dy: float = 0.,
                 dz: float = 0.,
                 step: float = 1.,
                 **kwargs) -> None:
        if 'duration' in kwargs:
            raise TypeError("'duration' may not be set on MoveTraps; "
                            'duration is computed from dx, dy, dz, step')
        # Compute duration using local variables; self cannot be used
        # safely before super().__init__() in PyQt.
        _dx = float(dx)
        _dy = float(dy)
        _dz = float(dz)
        _step_size = max(1e-6, float(step))
        _dist = math.sqrt(_dx**2 + _dy**2 + _dz**2)
        _n = max(1, math.ceil(_dist / _step_size))
        super().__init__(duration=_n, **kwargs)
        self._dx        = _dx
        self._dy        = _dy
        self._dz        = _dz
        self._step_size = _step_size
        self._starts: dict = {}

    # ------------------------------------------------------------------
    # Internal helpers

    def _frames(self) -> int:
        '''Compute duration from current displacement and step size.'''
        distance = math.sqrt(
            self._dx**2 + self._dy**2 + self._dz**2)
        return max(1, math.ceil(distance / self._step_size))

    def _update_duration(self) -> None:
        self.duration = self._frames()

    # ------------------------------------------------------------------
    # Parameter properties (each setter updates duration)

    @property
    def dx(self) -> float:
        '''Displacement along x [pixels].'''
        return self._dx

    @dx.setter
    def dx(self, value: float) -> None:
        self._dx = float(value)
        self._update_duration()

    @property
    def dy(self) -> float:
        '''Displacement along y [pixels].'''
        return self._dy

    @dy.setter
    def dy(self, value: float) -> None:
        self._dy = float(value)
        self._update_duration()

    @property
    def dz(self) -> float:
        '''Displacement along z [pixels].'''
        return self._dz

    @dz.setter
    def dz(self, value: float) -> None:
        self._dz = float(value)
        self._update_duration()

    @property
    def step(self) -> float:
        '''Maximum displacement per frame [pixels].'''
        return self._step_size

    @step.setter
    def step(self, value: float) -> None:
        self._step_size = max(1e-6, float(value))
        self._update_duration()

    # ------------------------------------------------------------------
    # QTask lifecycle hooks

    def initialize(self) -> None:
        '''Record starting positions of all leaf traps.'''
        self._starts = {
            trap: trap.r.copy()
            for top in self.overlay
            for trap in top.leaves()
        }

    def process(self, frame: int) -> None:
        '''Interpolate each trap toward its target position.'''
        t = (frame + 1) / self.duration
        dr = np.array([self._dx, self._dy, self._dz])
        for trap, r0 in self._starts.items():
            trap.r = r0 + t * dr
