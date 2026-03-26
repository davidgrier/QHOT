from QHOT.lib.tasks.QTask import QTask


class StopRecording(QTask):

    '''Stop recording video from the camera.

    Calls ``dvr.stop()`` in ``initialize()``.

    Typically registered as a blocking task that returns immediately.

        manager.register(StartRecording(dvr=dvr, nframes=300))
        manager.register(Move(overlay, trap, target))
        manager.register(StopRecording(dvr=dvr))

    Parameters
    ----------
    dvr : QDVRWidget
        The video recorder.  Required.
    **kwargs
        Forwarded to ``QTask`` (e.g. ``delay``).
    '''

    parameters = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.duration = 0

    def initialize(self) -> None:
        self.dvr.stopButton.animateClick()
