'''Unit tests for QTextArray.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtWidgets, QtTest
from QHOT.lib.traps.QTrapGroup import QTrapGroup  # must precede traps imports
from QHOT.traps.QTextArray import QTextArray
from QHOT.traps.QLetterArray import QLetterArray, _char_positions, _FONT
from QHOT.traps.QTweezer import QTweezer

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# Known dot-counts for selected characters (hand-verified from _FONT).
KNOWN_DOT_COUNTS = {
    'N': 17,
    'Y': 10,
    'U': 15,
    'A': 17,
    ' ': 0,
    '0': 20,
}


class TestFont(unittest.TestCase):
    '''Font data lives in QLetterArray; verify it is accessible via import.'''

    def test_all_uppercase_letters_present(self):
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            self.assertIn(ch, _FONT, msg=f'{ch!r} missing from _FONT')

    def test_all_lowercase_letters_present(self):
        for ch in 'abcdefghijklmnopqrstuvwxyz':
            self.assertIn(ch, _FONT, msg=f'{ch!r} missing from _FONT')

    def test_all_digits_present(self):
        for ch in '0123456789':
            self.assertIn(ch, _FONT, msg=f'{ch!r} missing from _FONT')

    def test_space_present(self):
        self.assertIn(' ', _FONT)

    def test_each_char_has_seven_rows(self):
        for ch, rows in _FONT.items():
            self.assertEqual(len(rows), 7, msg=f'{ch!r} has {len(rows)} rows')

    def test_each_row_fits_in_5_bits(self):
        for ch, rows in _FONT.items():
            for row in rows:
                self.assertLessEqual(row, 0x1F,
                                     msg=f'{ch!r} row {row:#04x} > 5 bits')
                self.assertGreaterEqual(row, 0)

    def test_space_all_zeros(self):
        self.assertEqual(_FONT[' '], [0] * 7)

    def test_n_dot_count(self):
        self.assertEqual(len(_char_positions('N')), KNOWN_DOT_COUNTS['N'])

    def test_y_dot_count(self):
        self.assertEqual(len(_char_positions('Y')), KNOWN_DOT_COUNTS['Y'])

    def test_u_dot_count(self):
        self.assertEqual(len(_char_positions('U')), KNOWN_DOT_COUNTS['U'])

    def test_space_dot_count(self):
        self.assertEqual(len(_char_positions(' ')), 0)

    def test_lowercase_has_distinct_glyph(self):
        self.assertNotEqual(_char_positions('n'), _char_positions('N'))

    def test_lowercase_glyph_used_over_uppercase(self):
        positions_n = _char_positions('n')
        rows_used = {row for _, row in positions_n}
        self.assertNotIn(0, rows_used, 'lowercase n should have blank row 0')
        self.assertNotIn(1, rows_used, 'lowercase n should have blank row 1')

    def test_unknown_char_treated_as_space(self):
        self.assertEqual(_char_positions('!'), _char_positions(' '))


class TestInit(unittest.TestCase):

    def test_default_text(self):
        ta = QTextArray()
        self.assertEqual(ta.text, 'NYU')

    def test_default_separation(self):
        ta = QTextArray()
        self.assertEqual(ta.separation, 40.)

    def test_custom_text(self):
        ta = QTextArray(text='AB')
        self.assertEqual(ta.text, 'AB')

    def test_custom_separation(self):
        ta = QTextArray(separation=15.)
        self.assertEqual(ta.separation, 15.)

    def test_is_qtrapgroup(self):
        ta = QTextArray()
        self.assertIsInstance(ta, QTrapGroup)

    def test_kwargs_forwarded(self):
        ta = QTextArray(r=(5., 10., 2.))
        np.testing.assert_array_almost_equal(ta.r, [5., 10., 2.])


class TestStructure(unittest.TestCase):
    '''QTextArray direct children are QLetterArrays; leaves are QTweezers.'''

    def test_direct_children_are_letter_arrays(self):
        ta = QTextArray(text='NYU')
        for child in ta:
            self.assertIsInstance(child, QLetterArray)

    def test_letter_count_equals_text_length(self):
        ta = QTextArray(text='NYU')
        self.assertEqual(len(list(ta)), 3)

    def test_letter_count_single_char(self):
        ta = QTextArray(text='A')
        self.assertEqual(len(list(ta)), 1)

    def test_all_leaves_are_tweezers(self):
        ta = QTextArray(text='NYU')
        for trap in ta.leaves():
            self.assertIsInstance(trap, QTweezer)

    def test_nyu_total_leaf_count(self):
        ta = QTextArray(text='NYU')
        expected = (KNOWN_DOT_COUNTS['N'] +
                    KNOWN_DOT_COUNTS['Y'] +
                    KNOWN_DOT_COUNTS['U'])
        self.assertEqual(len(list(ta.leaves())), expected)

    def test_space_contributes_no_traps(self):
        ta_no_space = QTextArray(text='NY')
        ta_with_space = QTextArray(text='N Y')
        self.assertEqual(len(list(ta_with_space.leaves())),
                         len(list(ta_no_space.leaves())))

    def test_empty_string_no_children(self):
        ta = QTextArray(text='')
        self.assertEqual(len(list(ta)), 0)
        self.assertEqual(len(list(ta.leaves())), 0)

    def test_each_letter_char_matches_text(self):
        ta = QTextArray(text='NYU')
        for letter, char in zip(ta, 'NYU'):
            self.assertEqual(letter.char, char)

    def test_each_letter_separation_matches_ta(self):
        ta = QTextArray(text='AB', separation=15.)
        for letter in ta:
            self.assertAlmostEqual(letter.separation, 15., places=6)


class TestLetterPositions(unittest.TestCase):
    '''Letter cell centers follow a 6-column stride centerd on ta.r.'''

    def setUp(self):
        self.sep = 10.
        self.ta = QTextArray(text='NYU', separation=self.sep)

    def test_all_letters_at_same_y(self):
        cy = self.ta.r[1]
        for letter in self.ta:
            self.assertAlmostEqual(letter.r[1], cy, places=5)

    def test_all_letters_at_same_z(self):
        cz = self.ta.r[2]
        for letter in self.ta:
            self.assertAlmostEqual(letter.r[2], cz, places=5)

    def test_middle_letter_at_group_x(self):
        # For n=3, the middle letter (i=1) should be at cx.
        cx = self.ta.r[0]
        letters = list(self.ta)
        self.assertAlmostEqual(letters[1].r[0], cx, places=5)

    def test_letter_stride_is_6_times_sep(self):
        letters = list(self.ta)
        dx = letters[1].r[0] - letters[0].r[0]
        self.assertAlmostEqual(dx, 6. * self.sep, places=5)

    def test_letter_positions_symmetric(self):
        cx = self.ta.r[0]
        letters = list(self.ta)
        offsets = [l.r[0] - cx for l in letters]
        self.assertAlmostEqual(offsets[0], -offsets[-1], places=5)

    def test_ta_r_is_center_of_letter_x_positions(self):
        letter_xs = np.array([l.r[0] for l in self.ta])
        self.assertAlmostEqual(letter_xs.mean(), self.ta.r[0], places=5)

    def test_single_letter_centerd_at_ta_r(self):
        ta = QTextArray(text='A', separation=10.)
        letter = list(ta)[0]
        np.testing.assert_array_almost_equal(letter.r, ta.r, decimal=5)

    def test_positions_with_nonzero_group_r(self):
        ta = QTextArray(text='AB', separation=10., r=(100., 200., 5.))
        letters = list(ta)
        self.assertAlmostEqual(letters[0].r[0], 100. - 30., places=5)
        self.assertAlmostEqual(letters[1].r[0], 100. + 30., places=5)
        for letter in letters:
            self.assertAlmostEqual(letter.r[1], 200., places=5)
            self.assertAlmostEqual(letter.r[2], 5., places=5)

    def test_z_of_leaves_matches_group_z(self):
        ta = QTextArray(text='NYU', r=(0., 0., 7.))
        for trap in ta.leaves():
            self.assertAlmostEqual(trap.r[2], 7., places=6)


class TestRegisteredProperties(unittest.TestCase):

    def setUp(self):
        self.ta = QTextArray()

    def test_separation_is_registered(self):
        self.assertIn('separation', self.ta.properties)

    def test_text_is_not_registered(self):
        self.assertNotIn('text', self.ta.properties)

    def test_separation_decimals(self):
        self.assertEqual(self.ta.properties['separation']['decimals'], 1)


class TestSeparationSetter(unittest.TestCase):

    def test_separation_minimum_is_one(self):
        ta = QTextArray()
        ta.separation = 0.
        self.assertGreaterEqual(ta.separation, 1.)

    def test_separation_updates_letter_separation(self):
        ta = QTextArray(text='AB', separation=10.)
        ta.separation = 20.
        for letter in ta:
            self.assertAlmostEqual(letter.separation, 20., places=5)

    def test_separation_preserves_leaf_count(self):
        ta = QTextArray(text='NYU')
        original = len(list(ta.leaves()))
        ta.separation = 20.
        self.assertEqual(len(list(ta.leaves())), original)

    def test_separation_updates_letter_stride(self):
        ta = QTextArray(text='AB', separation=10.)
        ta.separation = 20.
        letters = list(ta)
        dx = abs(letters[1].r[0] - letters[0].r[0])
        self.assertAlmostEqual(dx, 120., places=5)  # 6 * 20


class TestTextSetter(unittest.TestCase):

    def test_text_setter_updates_letter_count(self):
        ta = QTextArray(text='A')
        ta.text = 'AB'
        self.assertEqual(len(list(ta)), 2)

    def test_text_setter_updates_property(self):
        ta = QTextArray(text='NYU')
        ta.text = 'ABC'
        self.assertEqual(ta.text, 'ABC')

    def test_text_setter_updates_leaf_count(self):
        ta = QTextArray(text='A')
        ta.text = 'N'
        self.assertEqual(len(list(ta.leaves())), len(_char_positions('N')))

    def test_lowercase_text_accepted(self):
        ta = QTextArray(text='nyu')
        self.assertGreater(len(list(ta.leaves())), 0)

    def test_lowercase_uses_distinct_glyphs(self):
        ta_upper = QTextArray(text='NYU')
        ta_lower = QTextArray(text='nyu')
        self.assertLess(len(list(ta_lower.leaves())),
                        len(list(ta_upper.leaves())))


class TestSignals(unittest.TestCase):

    def setUp(self):
        self.ta = QTextArray(text='NY')

    def test_reshaping_emitted_on_text_change(self):
        spy = QtTest.QSignalSpy(self.ta.reshaping)
        self.ta.text = 'AB'
        self.assertEqual(len(spy), 1)

    def test_reshaped_emitted_on_text_change(self):
        spy = QtTest.QSignalSpy(self.ta.reshaped)
        self.ta.text = 'AB'
        self.assertEqual(len(spy), 1)

    def test_reshaping_emitted_on_separation_change(self):
        spy = QtTest.QSignalSpy(self.ta.reshaping)
        self.ta.separation = 20.
        self.assertEqual(len(spy), 1)

    def test_reshaped_emitted_on_separation_change(self):
        spy = QtTest.QSignalSpy(self.ta.reshaped)
        self.ta.separation = 20.
        self.assertEqual(len(spy), 1)

    def test_reshaping_before_reshaped(self):
        order = []
        self.ta.reshaping.connect(lambda: order.append('reshaping'))
        self.ta.reshaped.connect(lambda: order.append('reshaped'))
        self.ta.text = 'AB'
        self.assertEqual(order, ['reshaping', 'reshaped'])

    def test_reshaping_fired_with_old_letters_attached(self):
        old_count = [0]
        self.ta.reshaping.connect(
            lambda: old_count.__setitem__(0, len(list(self.ta))))
        original_count = len(list(self.ta))
        self.ta.text = 'A'
        self.assertEqual(old_count[0], original_count)

    def test_reshaped_fired_with_new_letters_attached(self):
        new_count = [0]
        self.ta.reshaped.connect(
            lambda: new_count.__setitem__(0, len(list(self.ta))))
        self.ta.text = 'ABC'
        self.assertEqual(new_count[0], 3)

    def test_reshaped_fired_with_new_leaves_attached(self):
        new_leaves = [0]
        self.ta.reshaped.connect(
            lambda: new_leaves.__setitem__(0, len(list(self.ta.leaves()))))
        self.ta.text = 'A'
        self.assertEqual(new_leaves[0], len(_char_positions('A')))


class TestInMenu(unittest.TestCase):

    def test_in_all(self):
        import QHOT.traps as traps_pkg
        self.assertIn('QTextArray', traps_pkg.__all__)

    def test_importable(self):
        from QHOT.traps import QTextArray as TA
        self.assertIsNotNone(TA)


if __name__ == '__main__':
    unittest.main()
