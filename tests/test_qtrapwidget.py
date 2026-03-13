'''Unit tests for QTrapWidget.'''
import unittest
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QFab.lib.traps.QTrap import QTrap
from QFab.lib.traps.QTrapWidget import (
    QTrapPropertyEdit, QTrapPropertyWidget, QTrapWidget)

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestQTrapPropertyEditFieldWidth(unittest.TestCase):

    def test_returns_positive_int(self):
        self.assertIsInstance(QTrapPropertyEdit.fieldWidth(), int)
        self.assertGreater(QTrapPropertyEdit.fieldWidth(), 0)

    def test_cached(self):
        w1 = QTrapPropertyEdit.fieldWidth()
        w2 = QTrapPropertyEdit.fieldWidth()
        self.assertIs(w1, w2)


class TestQTrapPropertyEditInit(unittest.TestCase):

    def setUp(self):
        self.edit = QTrapPropertyEdit('x', 3.14, decimals=2)

    def test_name(self):
        self.assertEqual(self.edit.name, 'x')

    def test_decimals(self):
        self.assertEqual(self.edit.decimals, 2)

    def test_initial_value(self):
        self.assertAlmostEqual(self.edit.value, 3.14, places=2)

    def test_text_matches_value(self):
        self.assertEqual(self.edit.text(), '3.14')

    def test_fixed_width(self):
        self.assertEqual(self.edit.width(), QTrapPropertyEdit.fieldWidth())

    def test_max_length_two_decimals(self):
        # sign(1) + 5 integer digits + '.'(1) + 2 decimal places = 9
        self.assertEqual(self.edit.maxLength(), 9)

    def test_max_length_zero_decimals(self):
        edit = QTrapPropertyEdit('x', 0., decimals=0)
        # sign(1) + 5 integer digits = 6
        self.assertEqual(edit.maxLength(), 6)

    def test_max_length_four_decimals(self):
        edit = QTrapPropertyEdit('x', 0., decimals=4)
        # sign(1) + 5 integer digits + '.'(1) + 4 decimal places = 11
        self.assertEqual(edit.maxLength(), 11)

    def test_alignment(self):
        self.assertEqual(self.edit.alignment(),
                         QtCore.Qt.AlignmentFlag.AlignRight)


class TestQTrapPropertyEditFormat(unittest.TestCase):

    def test_two_decimals(self):
        edit = QTrapPropertyEdit('x', 0., decimals=2)
        self.assertEqual(edit.format(3.14159), '3.14')

    def test_four_decimals(self):
        edit = QTrapPropertyEdit('x', 0., decimals=4)
        self.assertEqual(edit.format(3.14159), '3.1416')

    def test_zero_decimals(self):
        edit = QTrapPropertyEdit('x', 0., decimals=0)
        self.assertEqual(edit.format(3.7), '4')


class TestQTrapPropertyEditValue(unittest.TestCase):

    def setUp(self):
        self.edit = QTrapPropertyEdit('x', 1.0, decimals=2)

    def test_setter_updates_value(self):
        self.edit.value = 5.5
        self.assertAlmostEqual(self.edit.value, 5.5, places=2)

    def test_setter_updates_text(self):
        self.edit.value = 5.5
        self.assertEqual(self.edit.text(), '5.50')

    def test_update_value_emits_signal(self):
        self.edit.value = 2.0
        self.edit.setText('9.99')
        spy = QtTest.QSignalSpy(self.edit.propertyChanged)
        self.edit.updateValue()
        self.assertEqual(len(spy), 1)

    def test_update_value_signal_carries_name_and_value(self):
        self.edit.setText('7.00')
        spy = QtTest.QSignalSpy(self.edit.propertyChanged)
        self.edit.updateValue()
        name, value = spy[0]
        self.assertEqual(name, 'x')
        self.assertAlmostEqual(value, 7.0, places=2)

    def test_update_value_stores_new_value(self):
        self.edit.setText('4.25')
        self.edit.updateValue()
        self.assertAlmostEqual(self.edit.value, 4.25, places=2)


class TestQTrapPropertyWidget(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(1., 2., 3.), amplitude=0.5, phase=1.0)
        self.widget = QTrapPropertyWidget(self.trap)

    def test_has_editor_for_each_property(self):
        for name in self.trap.properties:
            self.assertIn(name, self.widget.wid)

    def test_stores_trap_reference(self):
        self.assertIs(self.widget._trap, self.trap)

    def test_editors_show_correct_values(self):
        self.assertAlmostEqual(self.widget.wid['x'].value, 1., places=2)
        self.assertAlmostEqual(self.widget.wid['y'].value, 2., places=2)
        self.assertAlmostEqual(self.widget.wid['z'].value, 3., places=2)

    def test_update_values_on_trap_changed(self):
        self.trap.x = 99.
        self.assertAlmostEqual(self.widget.wid['x'].value, 99., places=2)

    def test_editor_change_updates_trap(self):
        self.widget.wid['x'].setText('42.00')
        self.widget.wid['x'].updateValue()
        self.assertAlmostEqual(self.trap.x, 42., places=2)


class TestQTrapWidget(unittest.TestCase):

    def setUp(self):
        self.widget = QTrapWidget()
        self.trap = QTrap(phase=0.)

    def test_initial_count_is_one(self):
        # label row counts as one item
        self.assertEqual(self.widget.count(), 1)

    def test_register_increments_count(self):
        self.widget.registerTrap(self.trap)
        self.assertEqual(self.widget.count(), 2)

    def test_register_adds_to_dict(self):
        self.widget.registerTrap(self.trap)
        self.assertIn(self.trap, self.widget._trap_widgets)

    def test_register_multiple_traps(self):
        trap2 = QTrap(phase=0.)
        self.widget.registerTrap(self.trap)
        self.widget.registerTrap(trap2)
        self.assertEqual(self.widget.count(), 3)
        self.assertIn(self.trap, self.widget._trap_widgets)
        self.assertIn(trap2, self.widget._trap_widgets)

    def test_register_duplicate_logs_warning(self):
        self.widget.registerTrap(self.trap)
        with self.assertLogs('QFab.lib.traps.QTrapWidget', level='WARNING') as cm:
            self.widget.registerTrap(self.trap)
        self.assertTrue(any('already registered' in line for line in cm.output))

    def test_register_duplicate_does_not_add_row(self):
        self.widget.registerTrap(self.trap)
        self.widget.registerTrap(self.trap)
        self.assertEqual(self.widget.count(), 2)

    def test_unregister_removes_from_dict(self):
        self.widget.registerTrap(self.trap)
        self.widget.unregisterTrap(self.trap)
        self.assertNotIn(self.trap, self.widget._trap_widgets)

    def test_unregister_unknown_trap_logs_warning(self):
        with self.assertLogs('QFab.lib.traps.QTrapWidget', level='WARNING') as cm:
            self.widget.unregisterTrap(self.trap)
        self.assertTrue(any('not registered' in line for line in cm.output))

    def test_unregister_unknown_trap_does_not_raise(self):
        try:
            self.widget.unregisterTrap(self.trap)
        except Exception as e:
            self.fail(f'unregisterTrap raised unexpectedly: {e}')


if __name__ == '__main__':
    unittest.main()
