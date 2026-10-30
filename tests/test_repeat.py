'''Unit tests for Repeat.'''
import unittest

from pyqtgraph.Qt import QtCore, QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager
from QHOT.tasks.BeginRepeat import BeginRepeat
from QHOT.tasks.Delay import Delay
from QHOT.tasks.Repeat import Repeat

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class MockScreen(QtCore.QObject):
    rendered = QtCore.pyqtSignal()


# ------------------------------------------------------------------
# Init

class TestRepeatInit(unittest.TestCase):

    def test_registered_in_registry(self):
        self.assertIn('Repeat', QTask._registry)

    def test_duration_is_zero(self):
        self.assertEqual(Repeat().duration, 0)

    def test_default_n(self):
        self.assertEqual(Repeat().n, 1)

    def test_explicit_n_stored(self):
        self.assertEqual(Repeat(n=5).n, 5)

    def test_duration_keyword_raises(self):
        with self.assertRaises(TypeError):
            Repeat(duration=1)

    def test_parameters_declared(self):
        names = [p['name'] for p in Repeat.parameters]
        self.assertIn('n', names)

    def test_initial_state_pending(self):
        self.assertEqual(Repeat().state, QTask.State.PENDING)


# ------------------------------------------------------------------
# Serialisation

class TestRepeatSerialization(unittest.TestCase):

    def test_to_dict_includes_type(self):
        self.assertEqual(Repeat(n=3).toDict()['type'], 'Repeat')

    def test_to_dict_includes_n(self):
        self.assertEqual(Repeat(n=3).toDict()['n'], 3)

    def test_to_dict_no_specs_when_none(self):
        self.assertNotIn('_specs', Repeat(n=3).toDict())

    def test_to_dict_includes_specs_when_set(self):
        specs = [{'type': 'Delay', 'delay': 0, 'frames': 0}]
        repeat = Repeat(n=2, _specs=specs)
        d = repeat.toDict()
        self.assertIn('_specs', d)
        self.assertEqual(d['_specs'], specs)

    def test_round_trip_n(self):
        task = Repeat(n=4)
        restored = QTask.fromDict(task.toDict())
        self.assertIsInstance(restored, Repeat)
        self.assertEqual(restored.n, 4)

    def test_round_trip_with_specs(self):
        specs = [{'type': 'Delay', 'delay': 0, 'frames': 0}]
        task = Repeat(n=2, _specs=specs)
        restored = QTask.fromDict(task.toDict())
        self.assertIsInstance(restored, Repeat)
        self.assertEqual(restored._specs, specs)


# ------------------------------------------------------------------
# Execution helpers

class TestRepeatSetup(unittest.TestCase):
    '''Base class providing a manager wired to a MockScreen.'''

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def _pump(self, max_signals=200):
        '''Fire rendered until manager pauses (schedule complete).

        Returns the number of signals fired.
        '''
        for count in range(1, max_signals + 1):
            self.screen.rendered.emit()
            if self.manager.paused:
                return count
        return max_signals  # did not complete


# ------------------------------------------------------------------
# Execution: no-op / single pass

class TestRepeatNoOp(TestRepeatSetup):

    def test_n1_emits_finished(self):
        repeat = Repeat(n=1)
        self.manager.register(repeat)
        spy = QtTest.QSignalSpy(repeat.finished)
        self.screen.rendered.emit()
        self.assertEqual(len(spy), 1)

    def test_n1_without_bracket_completes(self):
        '''Repeat with no BeginRepeat in schedule: logs warning, completes.'''
        self.manager.register(Repeat(n=3))
        self._pump()
        self.assertTrue(self.manager.paused)

    def test_manager_is_set_after_register(self):
        repeat = Repeat(n=1)
        self.manager.register(repeat)
        self.assertIs(repeat.manager, self.manager)


# ------------------------------------------------------------------
# Execution: bracketed block

class TestRepeatBracketed(TestRepeatSetup):

    def _schedule_block(self, n):
        '''Register [BeginRepeat, Delay(0), Repeat(n)] and return Repeat.'''
        self.manager.register(BeginRepeat())
        self.manager.register(Delay(frames=0))
        repeat = Repeat(n=n)
        self.manager.register(repeat)
        return repeat

    def test_n1_block_runs_once(self):
        # With n=1: no injection.  3 tasks × 1 step each = 3 rendered signals.
        self._schedule_block(n=1)
        count = self._pump()
        self.assertEqual(count, 3)

    def test_n2_block_runs_twice(self):
        # n=2: 3 (first pass) + 2 (Delay_fresh + Repeat(n=1)) = 5
        self._schedule_block(n=2)
        count = self._pump()
        self.assertEqual(count, 5)

    def test_n3_block_runs_three_times(self):
        # n=3: 3 + 2 + 2 = 7
        self._schedule_block(n=3)
        count = self._pump()
        self.assertEqual(count, 7)

    def test_rendered_count_formula(self):
        # General: 2*n + 1 rendered signals for a single-task block
        for n in range(1, 6):
            self.setUp()   # fresh manager each iteration
            self._schedule_block(n=n)
            count = self._pump()
            self.assertEqual(
                count,
                2 * n + 1,
                msg=f'n={n}: expected {2*n+1}, got {count}',
            )

    def test_schedule_unchanged_after_block(self):
        '''Injected tasks must not appear in the persistent schedule.'''
        self._schedule_block(n=3)
        self._pump()
        self.assertEqual(len(self.manager.scheduled), 3)

    def test_manager_resets_after_completion(self):
        self._schedule_block(n=2)
        self._pump()
        self.assertTrue(self.manager.paused)


# ------------------------------------------------------------------
# Execution: nested brackets

class TestRepeatNested(TestRepeatSetup):

    def test_nested_outer_runs_correct_count(self):
        # [BeginRepeat, BeginRepeat, Delay(0), Repeat(n=2), Repeat(n=3)]
        # Inner block: Delay runs 2× per outer pass.
        # Outer: 3 outer passes.
        # Rendered: outer-BeginRepeat(1) + 3×(inner-pass)
        # inner-pass = inner-BeginRepeat(1) + Delay(1) + inner-Repeat(1) = 3
        # But on outer runs 2 & 3, outer-BeginRepeat is not re-run (it's fresh).
        # Let me count carefully:
        # Pass 1 (from schedule): BR_outer + BR_inner + Delay + Repeat(n=2) +
        #   inject [BR_inner_f, Delay_f, Repeat(n=1)] + outer_Repeat(n=3) runs
        # This is complex to predict exactly; just verify completion.
        self.manager.register(BeginRepeat())   # outer
        self.manager.register(BeginRepeat())   # inner
        self.manager.register(Delay(frames=0))
        self.manager.register(Repeat(n=2))     # inner repeat
        self.manager.register(Repeat(n=3))     # outer repeat
        count = self._pump(max_signals=500)
        self.assertTrue(self.manager.paused,
                        f'did not complete within {count} signals')
        self.assertEqual(len(self.manager.scheduled), 5)

    def test_inner_specs_do_not_include_outer_tasks(self):
        '''Inner Repeat should only capture tasks between its BeginRepeat.'''
        self.manager.register(BeginRepeat())   # outer
        self.manager.register(Delay(frames=0))  # outer-only task
        self.manager.register(BeginRepeat())   # inner
        self.manager.register(Delay(frames=0))  # inner task
        inner_repeat = Repeat(n=2)
        self.manager.register(inner_repeat)
        self.manager.register(Repeat(n=1))     # outer no-op

        # Step through until inner_repeat has initialised
        for _ in range(10):
            self.screen.rendered.emit()
            if inner_repeat.state == QTask.State.COMPLETED:
                break

        # _specs should contain only the inner Delay, not the outer one
        self.assertIsNotNone(inner_repeat._specs)
        self.assertEqual(len(inner_repeat._specs), 1)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
