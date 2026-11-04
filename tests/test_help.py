'''The help pages are one manual: every link leads to a page, and every
page can be reached from the first.'''
import re
import unittest
from pathlib import Path

from qtpy import QtCore, QtWidgets

HELP = Path(__file__).resolve().parent.parent / 'help'
LINK = re.compile(r'''href=["']([^"'#]+)''')

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def pages() -> dict[str, str]:
    return {p.name: p.read_text(encoding='utf-8')
            for p in sorted(HELP.glob('*.html'))}


class TestTheManual(unittest.TestCase):

    def test_every_link_leads_to_a_page(self):
        names = pages()
        missing = [f'{name} -> {target}'
                   for name, text in names.items()
                   for target in LINK.findall(text)
                   if target not in names]
        self.assertEqual(missing, [])

    def test_every_page_can_be_reached_from_the_first(self):
        names = pages()
        reached, waiting = set(), ['index.html']
        while waiting:
            name = waiting.pop()
            if name in reached:
                continue
            reached.add(name)
            waiting.extend(LINK.findall(names[name]))
        self.assertEqual(sorted(set(names) - reached), [])

    def test_every_page_has_a_title_and_a_heading(self):
        for name, text in pages().items():
            with self.subTest(page=name):
                self.assertRegex(text, r'<title>.+</title>')
                self.assertRegex(text, r'<h2>.+</h2>')

    def test_the_browser_shows_the_first_page(self):
        browser = QtWidgets.QTextBrowser()
        browser.setSearchPaths([str(HELP)])
        browser.setSource(QtCore.QUrl('index.html'))
        self.assertIn('QHOT User Manual', browser.toPlainText())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
