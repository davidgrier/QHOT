from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.recording import startRecording


class StartRecording(QTask):

    '''Start recording video from the camera.

    Starts the recorder of ``dvr`` in ``initialize()``, without a click on
    the record button of the DVR widget.  Does not stop recording; use a
    separate ``StopRecording`` task for that.  Set ``nframes`` to record up
    to a fixed number of frames.

    The task fails, and with it the queue, if the recording cannot start:
    there is no camera, a video is playing, a recording is already running,
    the file name has an extension that cannot be written, or the file
    exists and ``overwrite`` is ``False``.  No dialog interrupts the run.

    Typically registered as a blocking task that returns immediately.

        manager.register(StartRecording(dvr=dvr, nframes=300))
        manager.register(Move(overlay, trap, target))

    Parameters
    ----------
    dvr : QDVRWidget
        The video recorder.  Required to run the task.
    filename : str
        File to record to.  If empty (default), the file name that the DVR
        widget shows is used.
    nframes : int
        Maximum number of frames to record.
    nskip : int
        Number of frames between recorded frames.  ``1`` records every
        frame.
    overwrite : bool
        Replace the file if it exists.  Default: ``False``.
    '''

    parameters = [
        dict(name='filename', type='str', value='', default=''),
        dict(name='nframes', type='int', value=10_000,
             default=10_000, min=10),
        dict(name='nskip', type='int', value=1, default=1, min=1),
        dict(name='overwrite', type='bool', value=False, default=False),
    ]

    def __init__(self, *args,
                 filename: str = '',
                 nframes: int = 10_000,
                 nskip: int = 1,
                 overwrite: bool = False,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.duration = 0
        self.filename = str(filename)
        self.nframes = int(nframes)
        self.nskip = int(nskip)
        self.overwrite = bool(overwrite)

    def initialize(self) -> None:
        startRecording(self.dvr, self.filename, self.nframes, self.nskip,
                       self.overwrite)
