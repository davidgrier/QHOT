'''Start a recording on the recorder of a DVR widget, for the tasks.

The tasks that record video call the recorder of the
:class:`~QVideo.dvr.QDVRWidget.QDVRWidget` directly.  Clicking its record
button instead would be unreliable in an experiment that runs unattended:
the click takes effect a moment later, and the button does nothing at all
when it is disabled.  The widget would also stop the experiment to ask
what to do about a file that exists or a name that it does not accept.
Here every one of these is an error, which fails the task and with it the
queue, and the reason appears in the status bar.
'''
from __future__ import annotations

from QVideo.dvr import QDVRWidget

__all__ = ['startRecording']


def startRecording(dvr: QDVRWidget,
                   filename: str,
                   nframes: int,
                   nskip: int = 1,
                   overwrite: bool = False) -> None:
    '''Start recording on the recorder of *dvr*.

    Parameters
    ----------
    dvr : QDVRWidget
        The video recorder.
    filename : str
        The file to write.  If empty, the file name that the DVR widget
        shows is used; otherwise the widget shows *filename* from now on.
    nframes : int
        The number of frames to record.
    nskip : int
        Record every *nskip*-th frame.
    overwrite : bool
        Replace *filename* if it exists.  By default an existing file
        is an error, so that a run cannot destroy an earlier one.

    Raises
    ------
    RuntimeError
        If there is no source to record, a video is playing,
        or a recording is already running.
    ValueError
        If the extension of the file is not one that can be written.
    FileExistsError
        If the file exists and *overwrite* is ``False``.
    '''
    if dvr.isPlaying():
        raise RuntimeError('cannot record while a video is playing')
    path = filename or dvr.filename
    dvr.recorder.start(path, int(nframes), int(nskip), overwrite=overwrite)
    dvr.filename = path
