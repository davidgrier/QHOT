from QHOT.lib.tasks.QTask import QTask


class StopRecording(QTask):

    '''Stop recording video from the camera.

    Stops the recorder of ``dvr`` in ``initialize()``, without a click on
    the stop button of the DVR widget.  The recorder writes the frames that
    were captured before it returns.  Does nothing if no recording is
    running.  Playback of a video is not affected.

    Typically registered as a blocking task that returns immediately.

        manager.register(StartRecording(dvr=dvr, nframes=300))
        manager.register(Move(overlay, trap, target))
        manager.register(StopRecording(dvr=dvr))

    Parameters
    ----------
    dvr : QDVRWidget
        The video recorder.  Required to run the task.
    **kwargs
        Forwarded to ``QTask`` (e.g. ``delay``).
    '''

    parameters = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.duration = 0

    def initialize(self) -> None:
        self.dvr.recorder.stop()
