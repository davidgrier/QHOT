from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.recording import startRecording


class Record(QTask):

    '''Record video from the camera to a file.

    Starts the recorder of ``dvr`` in ``initialize()`` and stops it in
    ``complete()``, without clicks on the buttons of the DVR widget.  The
    recording lasts as long as the task: set ``nframes`` to record for
    that many frames of the display; leave it as ``0`` (default) to record
    until the task is stopped.  The recording is bounded by the frame count
    that the DVR widget shows, which is only a safety limit when the task
    ends first.  A task that is aborted, for example by stopping the queue,
    stops its recording.

    The task fails, and with it the queue, if the recording cannot start:
    there is no camera, a video is playing, a recording is already running,
    the file name has an extension that cannot be written, or the file
    exists and ``overwrite`` is ``False``.  No dialog interrupts the run.

    Typically registered as a non-blocking (background) task so that
    trap-manipulation tasks proceed in parallel::

        manager.register(Record(dvr=dvr, nframes=300), blocking=False)
        manager.register(Move(overlay, trap, target))

    Parameters
    ----------
    dvr : QDVRWidget
        The video recorder.  Required to run the task.
    filename : str
        File to record to.  If ``''`` (default), the file name that the
        DVR widget shows is used.
    nframes : int
        Number of frames of the display to record.  ``0`` (default)
        records until the task is stopped.
    overwrite : bool
        Replace the file if it exists.  Default: ``False``.
    **kwargs
        Forwarded to ``QTask`` (e.g. ``delay``).
    '''

    parameters = [
        dict(name='filename', type='str', value='', default=''),
        dict(name='nframes', type='int', value=0, default=0, min=0),
        dict(name='overwrite', type='bool', value=False, default=False),
    ]

    def __init__(self, *args,
                 filename: str = '',
                 nframes: int = 0,
                 overwrite: bool = False,
                 **kwargs) -> None:
        duration = nframes if nframes > 0 else None
        super().__init__(*args, duration=duration, **kwargs)
        self.filename = filename
        self.overwrite = bool(overwrite)
        self._nframes = int(nframes)
        self._recording = False

    @property
    def nframes(self) -> int:
        '''Number of frames to record (0 = unlimited).'''
        return self._nframes

    @nframes.setter
    def nframes(self, value: int) -> None:
        self._nframes = int(value)
        self.duration = self._nframes if self._nframes > 0 else None

    def initialize(self) -> None:
        startRecording(self.dvr, self.filename, self.dvr.nframes.value(),
                       overwrite=self.overwrite)
        self._recording = True

    def complete(self) -> None:
        self._stop()

    def abort(self, reason: str = 'aborted') -> None:
        '''Stop the recording that this task started, then abort.'''
        self._stop()
        super().abort(reason)

    def _stop(self) -> None:
        '''Stop the recording, if this task started one.'''
        if self._recording:
            self._recording = False
            self.dvr.recorder.stop()
