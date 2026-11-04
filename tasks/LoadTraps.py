from QHOT.lib.tasks.QTask import QTask


class LoadTraps(QTask):

    '''Load a trap configuration from a JSON file into the overlay.

    Calls ``overlay.fromList()`` in ``initialize()``, replacing the
    current traps with those stored in ``filename``.
    Completes immediately in a single frame.

    The task fails, and with it the queue, if there is no file name or the
    file cannot be read, because a run that went on with the wrong traps
    would be wrong without anyone knowing.

    Parameters
    ----------
    filename : str
        Path to a ``.json`` file previously written by
        :class:`SaveTraps` or by File > Save Traps.  Required.
    **kwargs
        Forwarded to :class:`~QHOT.lib.tasks.QTask.QTask`.

    Examples
    --------
    Load a saved configuration and begin recording::

        manager.register(LoadTraps(filename='/data/traps_20260326.json'))
        manager.register(Record(nframes=300), blocking=False)
    '''

    parameters = (
        dict(name='filename', type='str', value='', default=''),
    )

    def __init__(self, *, filename: str = '', **kwargs) -> None:
        super().__init__(duration=0, **kwargs)
        self.filename = filename

    def initialize(self) -> None:
        if not self.filename:
            raise ValueError('LoadTraps needs the name of a file')
        self.overlay.fromList(self.save.readJson(self.filename))
