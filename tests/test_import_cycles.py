'''Every package can be the first one that a program imports.

The tests of QHOT import ``QHOT.lib`` first, which hides a cycle between
``QHOT.traps`` and ``QHOT.lib.traps``.  Each module is imported here in an
interpreter of its own, as a script would.
'''
import os
import subprocess
import sys
import unittest

MODULES = ('QHOT.traps', 'QHOT.traps.QTweezer', 'QHOT.traps.QTrapArray',
           'QHOT.lib.traps', 'QHOT.lib.traps.commands', 'QHOT.tasks',
           'QHOT.lib.tasks', 'QHOT.lib.holograms')


class TestFirstImport(unittest.TestCase):

    def test_each_module_imports_in_a_fresh_interpreter(self):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        for module in MODULES:
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, '-I', '-c', f'import {module}'],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
