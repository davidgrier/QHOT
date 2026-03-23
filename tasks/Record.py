from QHOT.lib.tasks.QTask import QTask


class Record(QTask):

    '''Record video from the camera to a file.

    Calls ``dvr.record()`` in ``initialize()`` and ``dvr.stop()`` in
    ``complete()``.  Set ``nframes`` to record a fixed number of
    frames; leave it as ``0`` (default) to record until the task is
    stopped manually.

    Typically registered as a non-blocking (background) task so that
    trap-manipulation tasks proceed in parallel::

        manager.register(Record(dvr=dvr, nframes=300), blocking=False)
        manager.register(Move(overlay, trap, target))

    Parameters
    ----------
    dvr : QDVRWidget
        The video recorder.  Required.
    filename : str
        If non-empty, set ``dvr.filename`` before recording starts.
        If ``''`` (default), the DVR's current filename is used.
    nframes : int
        Number of frames to record.  ``0`` (default) records until
        the task is stopped manually.
    **kwargs
        Forwarded to ``QTask`` (e.g. ``delay``).
    '''

    parameters = [
        dict(name='filename', type='str', value='', default=''),
        dict(name='nframes', type='int', value=0, default=0, min=0),
    ]

    def __init__(self, *args,
                 filename: str = '',
                 nframes: int = 0,
                 **kwargs) -> None:
        duration = nframes if nframes > 0 else None
        super().__init__(*args, duration=duration, **kwargs)
        self.filename = filename
        self._nframes = int(nframes)

    @property
    def nframes(self) -> int:
        '''Number of frames to record (0 = unlimited).'''
        return self._nframes

    @nframes.setter
    def nframes(self, value: int) -> None:
        self._nframes = int(value)
        self.duration = self._nframes if self._nframes > 0 else None

    def initialize(self) -> None:
        if self.filename:
            self.dvr.filename = self.filename
        self.dvr.record()

    def complete(self) -> None:
        self.dvr.stop()
