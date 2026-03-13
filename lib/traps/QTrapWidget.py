import functools
from pyqtgraph.Qt import QtCore, QtWidgets, QtGui
from QFab.lib.traps.QTrap import QTrap
from QFab.lib.traps.QTrapGroup import QTrapGroup
import logging


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

    propertyChanged = QtCore.pyqtSignal(str, float)

    _field_width: int | None = None

    @classmethod
    def fieldWidth(cls) -> int:
        '''Return the pixel width needed to display a typical value.

        Computed from the application font metrics and cached per
        concrete class (not shared across subclasses).
        '''
        if cls.__dict__.get('_field_width') is None:
            fm = QtGui.QFontMetrics(QtWidgets.QApplication.instance().font())
            cls._field_width = fm.boundingRect('12345.6').width()
        return cls._field_width

    def __init__(self, name: str, value: float, *args,
                 decimals: int = 2, **kwargs) -> None:
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

    @QtCore.pyqtSlot()
    def updateValue(self) -> None:
        '''Read the current text, update the stored value, and emit signal.

        No-op if the parsed value equals the currently stored value.
        '''
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

    Creates one ``QTrapPropertyEdit`` per registered property and
    connects each to ``trap.setTrapProperty``.  Updates automatically
    when the trap emits ``changed``.  Call ``cleanup()`` before
    deletion to disconnect from the trap's signals.

    Parameters
    ----------
    trap : QTrap
        The trap whose properties will be displayed and edited.
    '''

    def __init__(self, trap: QTrap, *args, indent: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._trap = trap
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
            wid.propertyChanged.connect(trap.setTrapProperty)
            wid.setStatusTip(trap.__class__.__name__ + ': ' + name)
            if trap.properties[name]['tooltip']:
                wid.setToolTip(name)
            self.wid[name] = wid
            layout.addWidget(wid)
        self._update_slot = functools.partial(self.updateValues, trap)
        trap.changed.connect(self._update_slot)
        self.setLayout(layout)

    def updateValues(self, trap: QTrap) -> None:
        '''Refresh all editors from the trap's current property values.'''
        for name in trap.properties.keys():
            self.wid[name].value = getattr(trap, name)

    def cleanup(self) -> None:
        '''Disconnect from ``changed`` signal before deleting trap.'''
        try:
            self._trap.changed.disconnect(self._update_slot)
        except (TypeError, RuntimeError):
            pass


class QTrapWidget(QtWidgets.QFrame):

    '''Scrollable panel showing property editors for all active traps.

    Maintains a ``QTrapPropertyWidget`` row for each registered trap.
    Traps are added via ``registerTrap`` and removed via
    ``unregisterTrap``.
    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._trap_widgets: dict[QTrap, QTrapPropertyWidget] = {}
        self._setupUi()

    def _setupUi(self) -> None:
        '''Build the scrollable frame with a column header row.'''
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)
        inner = QtWidgets.QWidget()
        self._inner_layout = QtWidgets.QVBoxLayout()
        self._inner_layout.setSpacing(0)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        inner.setLayout(self._inner_layout)
        scroll = QtWidgets.QScrollArea()
        policy = QtCore.Qt.ScrollBarPolicy
        scroll.setVerticalScrollBarPolicy(policy.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(policy.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll)
        self.setLayout(layout)
        self._inner_layout.addWidget(self._labelLine())

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

    @QtCore.pyqtSlot(QTrap)
    def registerTrap(self, trap: QTrap) -> None:
        '''Add a property editor row for ``trap``.

        If ``trap`` is a ``QTrapGroup``, also adds an indented row for
        each leaf trap beneath the group header row.
        '''
        if trap in self._trap_widgets:
            logger.warning(f'Trap already registered: {trap}')
            return
        trapWidget = QTrapPropertyWidget(trap)
        self._trap_widgets[trap] = trapWidget
        self._inner_layout.addWidget(trapWidget)
        if isinstance(trap, QTrapGroup):
            for leaf in trap.leaves():
                if leaf in self._trap_widgets:
                    logger.warning(f'Leaf already registered: {leaf}')
                    continue
                leafWidget = QTrapPropertyWidget(leaf, indent=20)
                self._trap_widgets[leaf] = leafWidget
                self._inner_layout.addWidget(leafWidget)

    @QtCore.pyqtSlot(QTrap)
    def unregisterTrap(self, trap: QTrap) -> None:
        '''Remove and destroy the property editor row for ``trap``.

        If ``trap`` is a ``QTrapGroup``, also removes the indented leaf
        rows that were added by ``registerTrap``.
        '''
        if isinstance(trap, QTrapGroup):
            for leaf in trap.leaves():
                widget = self._trap_widgets.pop(leaf, None)
                if widget is not None:
                    widget.cleanup()
                    self._inner_layout.removeWidget(widget)
                    widget.deleteLater()
        try:
            widget = self._trap_widgets.pop(trap)
            widget.cleanup()
            self._inner_layout.removeWidget(widget)
            widget.deleteLater()
        except KeyError:
            logger.warning(f'Trap not registered: {trap}')

    def count(self) -> int:
        '''Return the number of rows currently in the layout.'''
        return self._inner_layout.count()

    @classmethod
    def example(cls) -> None:
        '''Display a QTrapWidget demo with several traps.'''
        import pyqtgraph as pg

        pg.mkQApp('QTrapWidget Example')
        table = cls()
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


if __name__ == '__main__':
    QTrapWidget.example()
