'''The panel that shows the properties of the traps and edits them.'''
import functools
import logging

from qtpy import QtCore, QtGui, QtWidgets

from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup


logger = logging.getLogger(__name__)


class QTrapPropertyEdit(QtWidgets.QLineEdit):

    '''Single-property editor for one numeric trap attribute.

    Displays a right-aligned, fixed-width line edit with a double
    validator.  Emits ``propertyChanged(name, value)`` when the user
    commits a new value with Return or focus-loss.

    Parameters
    ----------
    name : str
        Name of the trap property this editor controls.
    value : float
        Initial value to display.
    decimals : int
        Number of decimal places for display and validation. Default: 2.
    '''

    #: Emitted with (name, value) when a trap property is edited.
    propertyChanged = QtCore.Signal(str, float)

    _field_width: int | None = None

    @classmethod
    def fieldWidth(cls) -> int:
        '''Return the pixel width needed to display a typical value.

        The width of the text of a typical value, ``12345.6``, and what the
        style puts around the text of a line edit: its frame, and the
        margin inside it.  Without them the digits at the left of the field
        are clipped.  Computed from the application font and style, and
        cached per concrete class (not shared across subclasses).
        '''
        if cls.__dict__.get('_field_width') is None:
            edit = QtWidgets.QLineEdit()
            style = edit.style()
            option = QtWidgets.QStyleOptionFrame()
            option.initFrom(edit)
            option.lineWidth = style.pixelMetric(
                QtWidgets.QStyle.PixelMetric.PM_DefaultFrameWidth,
                option,
                edit)
            metrics = edit.fontMetrics()
            margin = 4      # inside the frame, as QLineEdit makes it
            text = QtCore.QSize(
                metrics.horizontalAdvance('12345.6') + margin,
                metrics.height())
            cls._field_width = style.sizeFromContents(
                QtWidgets.QStyle.ContentsType.CT_LineEdit,
                option,
                text,
                edit).width()
        return cls._field_width

    def __init__(self,
                 name: str,
                 value: float,
                 *args,
                 decimals: int = 2,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = name
        self.decimals = decimals
        self._value: float = 0.
        self._setupUi()
        self._connectSignals()
        self.value = value

    def _setupUi(self) -> None:
        '''Configure alignment, width, length, and numeric validator.'''
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.setFixedWidth(self.fieldWidth())
        # sign (1) + up to 5 integer digits + optional '.' + decimal places
        max_len = 1 + 5 + (1 + self.decimals if self.decimals > 0 else 0)
        self.setMaxLength(max_len)
        v = QtGui.QDoubleValidator(decimals=self.decimals)
        v.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.setValidator(v)

    def _connectSignals(self) -> None:
        '''Commit value on Return or focus-loss.'''
        self.editingFinished.connect(self.updateValue)

    def format(self, value: float) -> str:
        '''Format a float with the configured decimal places.'''
        return f'{value:.{self.decimals}f}'

    @QtCore.Slot()
    def updateValue(self) -> None:
        '''Read the current text, update the stored value, and emit signal.

        No-op if the text is what the field shows for the stored value: a
        field is left, by a click or the Tab key, whether or not it was
        edited, and what it shows is rounded.
        '''
        if self.text() == self.format(self._value):
            return
        new_value = float(self.text())
        if new_value == self._value:
            return
        self.value = new_value
        logger.debug(f'Changing {self.name}: {self.value}')
        self.propertyChanged.emit(self.name, self.value)

    @property
    def value(self) -> float:
        '''Current numeric value displayed in the editor.'''
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self.setText(self.format(value))
        self._value = value


class QTrapPropertyWidget(QtWidgets.QWidget):

    '''Row of property editors for a single trap.

    Creates one ``QTrapPropertyEdit`` per registered property.  An edit
    is not made here but announced, as ``edited(trap, name, value)``, so
    that whoever owns the traps can make it undoable.  Updates
    automatically when the trap emits ``changed``.  Call ``cleanup()``
    before deletion to disconnect from the trap's signals.

    Parameters
    ----------
    trap : QTrap
        The trap whose properties will be displayed and edited.
    '''

    #: Emitted with (trap, name, value) when the user edits a property.
    edited = QtCore.Signal(object, str, float)

    def __init__(self, trap: QTrap, *args, indent: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._trap = trap
        #: The rows of the members, if the trap is a group.
        self.members: list[QTrapPropertyWidget] = []
        self._setupUi(trap, indent=indent)

    def _setupUi(self, trap: QTrap, indent: int = 0) -> None:
        '''Build the row of editors from registered properties.'''
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(indent, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.wid: dict[str, QTrapPropertyEdit] = {}
        for name in trap.properties.keys():
            value = getattr(trap, name)
            decimals = trap.properties[name]['decimals']
            wid = QTrapPropertyEdit(name, value, decimals=decimals)
            wid.propertyChanged.connect(self._announce)
            wid.setStatusTip(trap.__class__.__name__ + ': ' + name)
            if trap.properties[name]['tooltip']:
                wid.setToolTip(name)
            self.wid[name] = wid
            layout.addWidget(wid)
        self._updateSlot = functools.partial(self.updateValues, trap)
        trap.changed.connect(self._updateSlot)
        self.setLayout(layout)

    @QtCore.Slot(str, float)
    def _announce(self, name: str, value: float) -> None:
        '''Say that the user has edited a property of the trap.'''
        self.edited.emit(self._trap, name, value)

    def updateValues(self, trap: QTrap) -> None:
        '''Refresh all editors from the trap's current property values.'''
        for name in trap.properties.keys():
            self.wid[name].value = getattr(trap, name)

    def updateMembers(self) -> None:
        '''Refresh the rows of the members of a group.

        Moving a group moves its members without a ``changed`` of their
        own, so the row of the group says what the rows of the members
        should show.
        '''
        for widget in self.members:
            widget.updateValues(widget._trap)

    def cleanup(self) -> None:
        '''Disconnect from ``changed`` signal before deleting trap.'''
        for slot in (self._updateSlot, self.updateMembers):
            try:
                self._trap.changed.disconnect(slot)
            except (TypeError, RuntimeError):
                pass


class QTrapWidget(QtWidgets.QFrame):

    '''Scrollable panel showing property editors for all active traps.

    Maintains a ``QTrapPropertyWidget`` row for each registered trap.
    Traps are added via ``registerTrap`` and removed via
    ``unregisterTrap``.  The panel does not change the traps: it emits
    ``edited`` when the user edits a property, and whoever owns the traps
    makes the change (``QTrapOverlay.editTrap``, which can be undone).
    '''

    #: Emitted with (trap, name, value) when the user edits a property.
    edited = QtCore.Signal(object, str, float)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._trapWidgets: dict[QTrap, QTrapPropertyWidget] = {}
        self._setupUi()

    def _setupUi(self) -> None:
        '''Build the scrollable frame with a column header row.'''
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)
        inner = QtWidgets.QWidget()
        self._innerLayout = QtWidgets.QVBoxLayout()
        self._innerLayout.setSpacing(0)
        self._innerLayout.setContentsMargins(0, 0, 0, 0)
        self._innerLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        inner.setLayout(self._innerLayout)
        scroll = QtWidgets.QScrollArea()
        policy = QtCore.Qt.ScrollBarPolicy
        scroll.setVerticalScrollBarPolicy(policy.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(policy.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll)
        self.setLayout(layout)
        self._innerLayout.addWidget(self._labelLine())

    def _labelLine(self) -> QtWidgets.QWidget:
        '''Build the column header row.'''
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        for name in 'x y z A ϕ'.split():
            label = QtWidgets.QLabel(name)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(QTrapPropertyEdit.fieldWidth())
            layout.addWidget(label)
        widget.setLayout(layout)
        return widget

    @QtCore.Slot(QTrap)
    def registerTrap(self, trap: QTrap) -> None:
        '''Add a property editor row for ``trap``.

        If ``trap`` is a ``QTrapGroup``, also adds an indented row for
        each leaf trap beneath the group header row.
        '''
        if trap in self._trapWidgets:
            logger.warning(f'Trap already registered: {trap}')
            return
        trapWidget = QTrapPropertyWidget(trap)
        trapWidget.edited.connect(self.edited)
        self._trapWidgets[trap] = trapWidget
        self._innerLayout.addWidget(trapWidget)
        if isinstance(trap, QTrapGroup):
            for leaf in trap.leaves():
                if leaf in self._trapWidgets:
                    logger.warning(f'Leaf already registered: {leaf}')
                    continue
                leafWidget = QTrapPropertyWidget(leaf, indent=20)
                leafWidget.edited.connect(self.edited)
                self._trapWidgets[leaf] = leafWidget
                self._innerLayout.addWidget(leafWidget)
            trapWidget.members = [self._trapWidgets[leaf]
                                  for leaf in trap.leaves()]
            trap.changed.connect(trapWidget.updateMembers)

    @QtCore.Slot(QTrap)
    def unregisterTrap(self, trap: QTrap) -> None:
        '''Remove and destroy the property editor row for ``trap``.

        If ``trap`` is a ``QTrapGroup``, also removes the indented leaf
        rows that were added by ``registerTrap``.
        '''
        if isinstance(trap, QTrapGroup):
            for leaf in trap.leaves():
                widget = self._trapWidgets.pop(leaf, None)
                if widget is not None:
                    widget.cleanup()
                    self._innerLayout.removeWidget(widget)
                    widget.deleteLater()
        try:
            widget = self._trapWidgets.pop(trap)
            widget.cleanup()
            self._innerLayout.removeWidget(widget)
            widget.deleteLater()
        except KeyError:
            logger.warning(f'Trap not registered: {trap}')

    def count(self) -> int:
        '''Return the number of rows currently in the layout.'''
        return self._innerLayout.count()

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Display a QTrapWidget demo with several traps.'''
        import pyqtgraph as pg

        pg.mkQApp('QTrapWidget Example')
        table = cls()
        table.edited.connect(
            lambda trap, name, value: trap.setTrapProperty(name, value))
        trapa = QTrap(phase=0.)
        trapb = QTrap(phase=0.)
        trapc = QTrap(phase=0.)
        table.registerTrap(trapa)
        table.registerTrap(trapb)
        table.show()
        trapa.r = (100, 100, 10)
        trapc.r = (50, 50, 5)
        table.unregisterTrap(trapb)
        trapb.deleteLater()
        table.registerTrap(trapc)
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QTrapWidget.example()
