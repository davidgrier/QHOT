import math

import numpy as np

from QHOT.lib.tasks.QTask import QTask


class MoveTraps(QTask):

    '''Translate all traps by a 3D displacement over multiple frames.

    Moves every trap and group in the overlay from its current position
    to ``r + (dx, dy, dz)`` via linear interpolation; a group moves as a
    whole and keeps its own center.  The displacement is
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

        manager.register(MoveTraps(dx=50., step=2.))
    '''

    parameters = (
        dict(name='dx',           type='float', value=0., default=0.),
        dict(name='dy',           type='float', value=0., default=0.),
        dict(name='dz',           type='float', value=0., default=0.),
        dict(name='step', type='float', value=1., default=1., min=0.01),
        dict(name='selected_only', type='bool', value=False, default=False),
    )

    def __init__(self,
                 dx: float = 0.,
                 dy: float = 0.,
                 dz: float = 0.,
                 step: float = 1.,
                 selected_only: bool = False,
                 **kwargs) -> None:
        if 'duration' in kwargs:
            raise TypeError("'duration' may not be set on MoveTraps; "
                            'duration is computed from dx, dy, dz, step')
        super().__init__(duration=1, **kwargs)
        self._dx = float(dx)
        self._dy = float(dy)
        self._dz = float(dz)
        self._stepSize = max(1e-6, float(step))
        self.selected_only = bool(selected_only)
        self._starts: dict = {}
        self._updateDuration()

    def _updateDuration(self) -> None:
        '''Set ``duration`` to the frames that the displacement needs.'''
        distance = math.sqrt(self._dx**2 + self._dy**2 + self._dz**2)
        self.duration = max(1, math.ceil(distance / self._stepSize))

    # ------------------------------------------------------------------
    # Parameter properties (each setter updates duration)

    @property
    def dx(self) -> float:
        '''Displacement along x [pixels].'''
        return self._dx

    @dx.setter
    def dx(self, value: float) -> None:
        self._dx = float(value)
        self._updateDuration()

    @property
    def dy(self) -> float:
        '''Displacement along y [pixels].'''
        return self._dy

    @dy.setter
    def dy(self, value: float) -> None:
        self._dy = float(value)
        self._updateDuration()

    @property
    def dz(self) -> float:
        '''Displacement along z [pixels].'''
        return self._dz

    @dz.setter
    def dz(self, value: float) -> None:
        self._dz = float(value)
        self._updateDuration()

    @property
    def step(self) -> float:
        '''Maximum displacement per frame [pixels].'''
        return self._stepSize

    @step.setter
    def step(self, value: float) -> None:
        self._stepSize = max(1e-6, float(value))
        self._updateDuration()

    # ------------------------------------------------------------------
    # QTask lifecycle hooks

    def initialize(self) -> None:
        '''Record starting positions of the traps and groups to be moved.

        Uses ``overlay.markedGroups`` when ``selected_only`` is ``True``,
        otherwise all the traps and groups of the overlay.
        '''
        if self.selected_only:
            traps = self.overlay.markedGroups
        else:
            traps = list(self.overlay)
        self._starts = {trap: trap.r for trap in traps}

    def process(self, frame: int) -> None:
        '''Interpolate each trap toward its target position.'''
        t = (frame + 1) / self.duration
        dr = np.array([self._dx, self._dy, self._dz])
        for trap, r0 in self._starts.items():
            trap.r = r0 + t * dr
