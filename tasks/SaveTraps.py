from QHOT.lib.tasks.QTask import QTask


class SaveTraps(QTask):

    '''Save the current trap overlay to a JSON file.

    Calls ``save.traps()`` in ``initialize()``.
    Completes immediately in a single frame.

    Parameters
    ----------
    filename : str
        Destination path.  If ``''`` (default), a timestamped ``.json``
        file is created in the data directory via
        :meth:`~QHOT.lib.QSaveFile.QSaveFile.traps`.
    **kwargs
        Forwarded to :class:`~QHOT.lib.tasks.QTask.QTask`.

    Examples
    --------
    Assemble a configuration, save it, then start recording::

        manager.register(MoveTraps(dy=-50.))
        manager.register(SaveTraps())
        manager.register(Record(nframes=300), blocking=False)
    '''

    parameters = (
        dict(name='filename', type='str', value='', default=''),
    )

    def __init__(self, *, filename: str = '', **kwargs) -> None:
        super().__init__(duration=0, **kwargs)
        self.filename = filename

    def initialize(self) -> None:
        filename = self.filename or None
        self.save.traps(self.overlay, filename=filename)
