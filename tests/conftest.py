'''Configuration of the tests.

``QtTest.QSignalSpy`` of PyQt has ``len()`` and indexing, and the tests use
them.  The spy of PySide6 has neither, so under PySide6 the tests get a
spy that does: a list of the arguments of each emission.
'''
from qtpy import API_NAME, QtTest

if API_NAME.startswith('PySide'):
    class SignalSpy(list):

        '''The emissions of a signal, each a list of its arguments.'''

        def __init__(self, signal) -> None:
            super().__init__()
            signal.connect(self._record)

        def _record(self, *args) -> None:
            self.append(list(args))

    QtTest.QSignalSpy = SignalSpy
