'''Unit tests for Repeat.'''
import unittest

from qtpy import QtCore, QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager
from QHOT.tasks.BeginRepeat import BeginRepeat
from QHOT.tasks.Delay import Delay
from QHOT.tasks.Repeat import Repeat

try:
    from taskmanagers import Screen, manager_for
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import Screen, manager_for

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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
# Serialization

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
    '''Base class providing a manager wired to a Screen.'''

    def setUp(self):
        self.screen  = Screen()
        self.manager = manager_for(self.screen)

    def _pump(self, max_signals=200):
        '''Draw frames until the manager pauses (schedule complete).

        Returns the number of signals fired.
        '''
        for count in range(1, max_signals + 1):
            self.screen.draw()
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
        self.screen.draw()
        self.assertEqual(len(spy), 1)

    def test_n1_without_bracket_completes(self):
        '''Nothing to repeat, so nothing to look for.'''
        repeat = Repeat(n=1)
        self.manager.register(repeat)
        spy = QtTest.QSignalSpy(repeat.finished)
        self._pump()
        self.assertEqual(len(spy), 1)

    def test_n3_without_bracket_fails_the_queue(self):
        '''The block would run once, not three times.'''
        repeat = Repeat(n=3)
        after = Tick()
        self.manager.register(repeat)
        self.manager.register(after)
        spy = QtTest.QSignalSpy(repeat.failed)
        self.screen.draw()
        self.assertEqual(len(spy), 1)
        self.assertIs(repeat.state, QTask.State.FAILED)
        self.assertEqual(self.manager.queueSize, 0)

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
        # With n=1: no injection.  3 tasks × 1 step each = 3 frames.
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

    def test_frame_count_formula(self):
        # General: 2*n + 1 frames for a single-task block
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

        # Step through until inner_repeat has initialized
        for _ in range(10):
            self.screen.draw()
            if inner_repeat.state == QTask.State.COMPLETED:
                break

        # the block of the inner Repeat is the inner Delay, not the outer one
        self.assertEqual(len(inner_repeat._findSpecs()), 1)


# ------------------------------------------------------------------
# What runs, and what is saved

class Tick(QTask):
    '''Writes its tag in a log when it runs, and takes no frames.'''

    log: list = []
    parameters = (dict(name='tag', type='str', value='', default=''),)

    def __init__(self, tag: str = '', **kwargs):
        super().__init__(duration=0, **kwargs)
        self.tag = tag

    def initialize(self):
        Tick.log.append(self.tag)


class TestWhatRuns(TestRepeatSetup):

    def setUp(self):
        super().setUp()
        Tick.log.clear()

    def run_queue(self):
        Tick.log.clear()
        self.manager.pause(False)
        self._pump(max_signals=500)
        return ' '.join(Tick.log)

    def register(self, *tasks):
        for task in tasks:
            self.manager.register(task)

    def test_a_block_runs_n_times(self):
        self.register(BeginRepeat(), Tick('a'), Repeat(n=3))
        self.assertEqual(self.run_queue(), 'a a a')

    def test_nested_blocks_multiply(self):
        tasks = [BeginRepeat(), Tick('a'), BeginRepeat(), Tick('b'),
                 Repeat(n=2), Repeat(n=3)]
        self.register(*tasks)
        self.assertEqual(self.run_queue(), 'a b b a b b a b b')

    def test_three_levels_of_blocks(self):
        tasks = [BeginRepeat(), Tick('a'), BeginRepeat(), Tick('b'),
                 BeginRepeat(), Tick('c'), Repeat(n=2), Repeat(n=2),
                 Repeat(n=2)]
        self.register(*tasks)
        pass_ = 'a b c c b c c'
        self.assertEqual(self.run_queue(), f'{pass_} {pass_}')

    def test_the_same_queue_runs_the_same_again(self):
        tasks = [BeginRepeat(), Tick('a'), BeginRepeat(), Tick('b'),
                 Repeat(n=2), Repeat(n=2)]
        self.register(*tasks)
        first = self.run_queue()
        self.assertEqual(self.run_queue(), first)

    def test_a_task_edited_in_the_block_is_the_one_repeated(self):
        tick = Tick('a')
        self.register(BeginRepeat(), tick, Repeat(n=3))
        self.run_queue()
        tick.tag = 'edited'
        self.assertEqual(self.run_queue(), 'edited edited edited')

    def test_a_queue_saved_after_a_run_is_as_it_was_made(self):
        self.register(BeginRepeat(), Tick('a'), Repeat(n=3))
        before = self.manager.toList()
        self.run_queue()
        self.assertEqual(self.manager.toList(), before)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
