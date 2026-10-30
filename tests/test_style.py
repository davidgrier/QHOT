'''The layout of arguments follows the rule of the project.

In a definition or a call, either all the arguments are on one line or
each has a line of its own.  A list that is wrapped with several arguments
on a line is hard to read and to change, because a change to one argument
moves the others.  See ``CLAUDE.md``.
'''
import ast
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = ('old', 'devel', 'htmlcov', 'build', '_build')


def arguments(node: ast.AST) -> list[ast.AST]:
    '''Return the arguments of a call or a definition.'''
    if isinstance(node, ast.Call):
        return list(node.args) + list(node.keywords)
    a = node.args
    found = a.posonlyargs + a.args + a.kwonlyargs
    return found + [x for x in (a.vararg, a.kwarg) if x]


def crowded(source: str) -> list[int]:
    '''Return the lines of the argument lists that put several arguments on
    a line but are not wholly on one.'''
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.Call, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        lines = [a.lineno for a in arguments(node)]
        if len(lines) < 2 or min(lines) == max(lines):
            continue
        if any(n > 1 for n in Counter(lines).values()):
            found.append(node.lineno)
    return found


def sources():
    for path in sorted(ROOT.rglob('*.py')):
        relative = path.relative_to(ROOT).parts
        if relative[0].startswith('.') or relative[0] in SKIP:
            continue
        yield path, path.read_text()


class TestTheDetector(unittest.TestCase):

    def test_one_line_is_fine(self):
        self.assertEqual(crowded('f(a, b, c)\n'), [])

    def test_one_to_a_line_is_fine(self):
        self.assertEqual(crowded('f(\n    a,\n    b,\n)\n'), [])

    def test_several_to_a_line_is_found(self):
        self.assertEqual(crowded('f(a, b,\n  c)\n'), [1])

    def test_a_definition_is_found_too(self):
        self.assertEqual(crowded('def f(a, b,\n      c):\n    pass\n'), [1])

    def test_one_argument_is_fine(self):
        self.assertEqual(crowded('f(\n    a,\n)\n'), [])


class TestTheCode(unittest.TestCase):

    def test_arguments_are_on_one_line_or_one_to_a_line(self):
        found = [
            f'{path.relative_to(ROOT)}:{line}'
            for path, source in sources()
            for line in crowded(source)
        ]
        self.assertEqual(
            found,
            [],
            'argument lists with several arguments on a line:\n  '
            + '\n  '.join(found),
        )


if __name__ == '__main__':
    unittest.main()
