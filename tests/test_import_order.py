'''qtpy must select the Qt binding before pyqtgraph can.

``qtpy`` honors ``QT_API``.  ``pyqtgraph`` chooses a binding of its own when
it is imported first, and ``qtpy`` then follows it, so ``QT_API`` is
ignored.  ``import QVideo`` imports ``qtpy`` first, so QVideo may stand in
for it.  The check reads the text of every source file, the scripts and
examples that sit in strings and documents included.
'''
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUFFIXES = ('.py', '.rst', '.md')
PYQTGRAPH = re.compile(r'^\s*(import pyqtgraph|from pyqtgraph)')
SELECTS = re.compile(r'^\s*(import qtpy|from qtpy|import QVideo|from QVideo)')


def sources():
    '''Yield the source files of the repository, not scratch directories.'''
    for path in sorted(ROOT.rglob('*')):
        parts = path.relative_to(ROOT).parts
        if (path.suffix in SUFFIXES and path.is_file()
                and not any(part.startswith('.') or part in
                            ('devel', 'old', 'build', '_build') or
                            part.endswith('.egg-info') for part in parts)):
            yield path


def first(pattern: re.Pattern, lines: list[str]) -> int | None:
    '''Return the number of the first line that matches *pattern*.'''
    for number, line in enumerate(lines, 1):
        if pattern.match(line):
            return number
    return None


class TestQtpyComesBeforePyqtgraph(unittest.TestCase):

    def test_no_file_imports_pyqtgraph_first(self):
        late = []
        for path in sources():
            lines = path.read_text(errors='replace').splitlines()
            graph = first(PYQTGRAPH, lines)
            if graph is None:
                continue
            select = first(SELECTS, lines)
            if select is None or graph < select:
                late.append(f'{path.relative_to(ROOT)}:{graph}')
        self.assertEqual(late, [], 'import qtpy (or QVideo) before pyqtgraph')

    def test_the_check_sees_a_late_import(self):
        lines = ['import pyqtgraph as pg', 'from qtpy import QtCore']
        self.assertLess(first(PYQTGRAPH, lines), first(SELECTS, lines))
        self.assertIsNone(first(SELECTS, ['import numpy']))


FUTURE, STDLIB, THIRD, QVIDEO, QHOT, LOCAL = range(6)
GROUPS = 'future standard-library third-party QVideo QHOT local'.split()
#: The modules that sit beside the tests, such as ``taskmanagers``.
HELPERS = {path.stem for path in (ROOT / 'tests').glob('*.py')}


def group(node: ast.Import | ast.ImportFrom) -> int:
    '''Return the group of an import: where it belongs in the block.'''
    if isinstance(node, ast.ImportFrom) and node.level:
        return LOCAL
    name = (node.module if isinstance(node, ast.ImportFrom)
            else node.names[0].name) or ''
    top = name.split('.')[0]
    if top in HELPERS:
        return LOCAL
    if top == '__future__':
        return FUTURE
    if top in sys.stdlib_module_names:
        return STDLIB
    return {'QVideo': QVIDEO, 'QHOT': QHOT}.get(top, THIRD)


def misplaced(source: str) -> tuple[int, str, str] | None:
    '''Return the first import of the top block that is in the wrong group.

    The block is the imports at the head of the module, before the first
    statement that does something (a docstring, a ``try`` or an ``if`` that
    guards an import do not end it).  Returns ``(line, group, after)``.
    '''
    last = FUTURE
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            here = group(node)
            if here < last:
                return node.lineno, GROUPS[here], GROUPS[last]
            last = here
        elif not (isinstance(node, ast.Try | ast.If) or (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant))):
            return None
    return None


class TestTheImportsAreInGroups(unittest.TestCase):

    '''The imports of a module come in this order, a blank line between
    the groups: the standard library, the third-party libraries (``qtpy``
    first), QVideo, QHOT, and the siblings of a package (``.name``) or of a test.'''

    def test_no_module_has_a_group_out_of_place(self):
        late = []
        for path in sources():
            if path.suffix == '.py':
                found = misplaced(path.read_text())
                if found:
                    line, here, after = found
                    late.append(f'{path.relative_to(ROOT)}:{line} '
                                f'{here} after {after}')
        self.assertEqual(late, [])

    def test_the_check_sees_a_group_out_of_place(self):
        self.assertEqual(
            misplaced('import numpy\nimport os\n'), (2, 'standard-library',
                                                       'third-party'))
        self.assertEqual(
            misplaced('"""Doc."""\nimport os\nimport numpy\n'
                      'from QVideo import x\nfrom QHOT import y\n'
                      'from . import z\n'), None)
        self.assertIsNone(misplaced('import numpy\nimport taskmanagers\n'))
        self.assertIsNone(misplaced('import numpy\nx = 1\nimport os\n'))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
