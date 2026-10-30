from QHOT.lib.tasks.QTask import QTask


class Snapshot(QTask):

    '''Save a single video frame to a file.

    Calls ``save.image()`` in ``initialize()`` using the
    :class:`~pyqtgraph.ImageItem` supplied at construction.
    Completes immediately in a single frame.

    Parameters
    ----------
    image : pyqtgraph.ImageItem
        The live image item to export.  Typically ``screen.image``.
    filename : str
        Destination path.  If ``''`` (default), a timestamped ``.png``
        file is created in the data directory via
        :meth:`~QHOT.lib.QSaveFile.QSaveFile.image`.
    prefix : str
        Prefix for the auto-generated filename when ``filename`` is
        empty.  Default: ``'snapshot'``.
    **kwargs
        Forwarded to :class:`~QHOT.lib.tasks.QTask.QTask`.

    Examples
    --------
    Save the current frame, then move all traps right by 20 pixels::

        manager.register(Snapshot(image=screen.image))
        manager.register(MoveTraps(overlay=overlay, dx=20.))
    '''

    parameters = [
        dict(name='filename', type='str', value='', default=''),
        dict(name='prefix', type='str', value='snapshot', default='snapshot'),
    ]

    def __init__(
        self,
        image,
        *,
        filename: str = '',
        prefix: str = 'snapshot',
        **kwargs,
    ) -> None:
        super().__init__(duration=0, **kwargs)
        self._image = image
        self.filename = filename
        self.prefix = prefix

    def initialize(self) -> None:
        filename = self.filename or None
        self.save.image(self._image, filename=filename, prefix=self.prefix)
