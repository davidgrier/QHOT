'''The program ends cleanly: the exit status is zero.

A crash while Python shuts down does not fail a test, only the process,
so a suite can pass and still leave a failed run behind.  Qt objects that
are destroyed in a bad order, or a thread that is still running, show up
only there.
'''
import os
import subprocess
import sys
import textwrap
import unittest

SCRIPT = textwrap.dedent('''
    import sys
    sys.path.insert(0, {root!r})
    from qtpy import QtWidgets
    app = QtWidgets.QApplication([])
    from QHOT.lib.holograms import CGH, NumpyBackend
    from QHOT.traps import QTweezer

    cghs = [CGH(shape=(32, 32)) for _ in range(50)]     # never started
    running = CGH(shape=(32, 32)).start()               # left running
    stopped = CGH(shape=(32, 32)).start()
    stopped.compute((QTweezer(r=(5, 5, 0), phase=0.).spec(),))
    stopped.stop()
    again = CGH(shape=(32, 32)).start()                 # restarted
    again.stop()
    again.start()
    again.compute((QTweezer(r=(5, 5, 0), phase=0.).spec(),))
    print('ok')
''')


class TestExit(unittest.TestCase):

    def test_pipelines_in_every_state_leave_a_clean_exit(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}
        done = subprocess.run(
            [sys.executable, '-c', SCRIPT.format(root=os.path.dirname(root))],
            capture_output=True,
            text=True,
            env=environment,
            timeout=60,
        )
        self.assertIn('ok', done.stdout, done.stderr[-500:])
        self.assertEqual(done.returncode, 0, done.stderr[-500:])


if __name__ == '__main__':
    unittest.main()
