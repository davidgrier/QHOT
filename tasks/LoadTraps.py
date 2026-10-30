import json

from QHOT.lib.tasks.QTask import QTask


class LoadTraps(QTask):

    '''Load a trap configuration from a JSON file into the overlay.

    Calls ``overlay.fromList()`` in ``initialize()``, replacing the
    current traps with those stored in ``filename``.
    Completes immediately in a single frame.

    Parameters
    ----------
    filename : str
        Path to a ``.json`` file previously written by
        :class:`SaveTraps` or :meth:`~QHOT.lib.QSaveFile.QSaveFile.traps`.
        Required; an empty string is logged as an error and the task
        completes without changing the overlay.
    **kwargs
        Forwarded to :class:`~QHOT.lib.tasks.QTask.QTask`.

    Examples
    --------
    Load a saved configuration and begin recording::

        manager.register(LoadTraps(filename='/data/traps_20260326.json'))
        manager.register(Record(dvr=dvr, nframes=300), blocking=False)
    '''

    parameters = (
        dict(name='filename', type='str', value='', default=''),
    )

    def __init__(self, *, filename: str = '', **kwargs) -> None:
        super().__init__(duration=0, **kwargs)
        self.filename = filename

    def initialize(self) -> None:
        if not self.filename:
            import logging
            logging.getLogger(__name__).error(
                'LoadTraps: filename is required')
            return
        with open(self.filename) as f:
            self.overlay.fromList(json.load(f))
