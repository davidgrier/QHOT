'''Rules that keep every Qt binding working, which no test run shows unless
it runs on that binding, and on that version of Python.'''
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ('lib', 'traps', 'tasks')
OBJECT_SETATTR = re.compile(r'\bobject\.__setattr__\(')


def program():
    '''Yield the source files of the program.'''
    yield ROOT / 'qhot.py'
    for directory in PROGRAM:
        yield from sorted((ROOT / directory).rglob('*.py'))


class TestNoObjectSetattr(unittest.TestCase):

    '''PySide6 on Python 3.12 and earlier refuses ``object.__setattr__`` on
    a Qt object (``can't apply this __setattr__ to CGH object``), and the
    program stopped at the first line of ``CGH``.  Python 3.13 allows it,
    so a machine that has it does not see the fault.  Say
    ``super().__setattr__`` instead.'''

    def test_the_program_does_not_use_it(self):
        found = [f'{path.relative_to(ROOT)}:{n}'
                 for path in program()
                 for n, line in enumerate(path.read_text().splitlines(), 1)
                 if OBJECT_SETATTR.search(line)]
        self.assertEqual(found, [])

    def test_the_check_sees_it(self):
        self.assertTrue(OBJECT_SETATTR.search('    object.__setattr__(x, 1)'))
        self.assertFalse(OBJECT_SETATTR.search('    super().__setattr__(x, 1)'))


if __name__ == '__main__':
    unittest.main()
