from qtpy import QtCore
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from .QLetterArray import QLetterArray


class QTextArray(QTrapGroup):

    '''Dot-matrix text rendered as a pattern of optical tweezers.

    Renders a string of characters using a 7-row × 5-column dot-matrix
    typeface.  Each character occupies a fixed 5 × 7 cell rendered by a
    child ``QLetterArray``.  The text block is positioned so that the
    geometric center of the character cells coincides with the group's
    own position.

    Characters A-Z, a-z, 0-9 and space are supported.  Upper- and
    lower-case letters use distinct glyphs.  Unrecognized characters
    are rendered as spaces.

    Inherits
    --------
    QHOT.lib.traps.QTrapGroup

    Parameters
    ----------
    text : str
        String to render.  Default: ``'NYU'``.
    separation : float
        Center-to-center dot spacing [pixels].  Default: ``40.``.
    *args, **kwargs
        Forwarded to ``QTrapGroup``.

    Attributes
    ----------
    text : str
        Current text string.  Setting this triggers repopulation.
    separation : float
        Dot spacing [pixels].  Registered property.

    Signals
    -------
    reshaping : ()
        Emitted before the existing letter arrays are cleared.
    reshaped : ()
        Emitted after the new letter arrays have been added.
    '''

    #: Emitted when the text array begins to reshape.
    reshaping = QtCore.Signal()
    #: Emitted when the text array has finished reshaping.
    reshaped = QtCore.Signal()

    def __init__(self, *args,
                 text: str = 'NYU',
                 separation: float = 40.,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._text = str(text)
        self._separation = max(1., float(separation))
        self._populate()

    def _registerProperties(self) -> None:
        super()._registerProperties()
        self.registerProperty('separation', decimals=1, tooltip=True)

    # --- properties ---

    @property
    def text(self) -> str:
        '''Text string rendered as tweezers.'''
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = str(text)
        self._repopulate()

    @property
    def separation(self) -> float:
        '''Center-to-center dot spacing [pixels].'''
        return self._separation

    @separation.setter
    def separation(self, separation: float) -> None:
        self._separation = max(1., float(separation))
        self._repopulate()

    # --- population ---

    def _populate(self) -> None:
        '''Create one QLetterArray per character, centered on the group.

        Each character cell is 5 columns wide with a 1-column gap
        between characters, giving a 6-column stride.  The cells are
        positioned so that their geometric center coincides with
        ``self._r``.
        '''
        cx, cy, cz = self._r
        n = len(self._text)
        if n == 0:
            return
        # Character i cell-center offset from the group center:
        #   stride = 6 columns; cell center at column 2 within each cell.
        #   For n characters the layout center is at column 3*(n-1).
        #   Offset of char i = 6*i + 2 - 3*(n-1) = 3*(2*i - n + 1) columns.
        letters = [
            QLetterArray(char=char,
                         separation=self._separation,
                         r=(cx + self._separation * 3 * (2 * i - n + 1),
                            cy, cz))
            for i, char in enumerate(self._text)
        ]
        self.addTrap(letters)

    def _repopulate(self) -> None:
        '''Signal, clear direct children (QLetterArrays), repopulate.'''
        self.reshaping.emit()
        for child in list(self):
            child.setParent(None)
        self._populate()
        self.reshaped.emit()

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Demonstrate creation of a text trap array.'''
        ta = cls(text='NYU', separation=30.)
        print(ta)
        print(f'  {len(list(ta.leaves()))} tweezers across '
              f'{len(list(ta))} letter arrays')


if __name__ == '__main__':  # pragma: no cover
    QTextArray.example()
