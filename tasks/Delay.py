from QHOT.lib.tasks.QTask import QTask


class Delay(QTask):

    '''Wait a fixed number of frames before the next task begins.

    ``process()`` is a no-op; the task auto-completes after exactly
    ``frames`` rendered frames have been delivered.

    Parameters
    ----------
    frames : int
        Number of frames to wait.  Default: 30.
    **kwargs
        Forwarded to ``QTask``.  ``duration`` may not be supplied.

    Examples
    --------
    Record for 60 frames, wait 30 frames, then record again::

        manager.register(Record(dvr=dvr, nframes=60))
        manager.register(Delay(30))
        manager.register(Record(dvr=dvr, nframes=60))
    '''

    parameters = [
        dict(name='frames', type='int', value=30, default=30, min=0),
    ]

    def __init__(self, frames: int = 30, **kwargs) -> None:
        if 'duration' in kwargs:
            raise TypeError("'duration' may not be set on Delay; "
                            'use frames instead')
        super().__init__(duration=frames, **kwargs)
        self._frames = int(frames)

    @property
    def frames(self) -> int:
        '''Number of frames to wait.'''
        return self._frames

    @frames.setter
    def frames(self, value: int) -> None:
        self._frames = int(value)
        self.duration = self._frames
