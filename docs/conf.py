'''Sphinx configuration for QHOT.'''

import os
import sys
from pathlib import Path

# Use Qt's offscreen platform so pyqtgraph can be imported by autodoc
# without a display (required on ReadTheDocs and other headless build hosts).
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# The repo root is two levels up from docs/ (docs/ -> QHOT/ -> parent/).
# Adding the parent lets autodoc import QHOT as a package without requiring
# an editable install.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# -- Project information -----------------------------------------------------

project = 'QHOT'
author = 'David G. Grier'
copyright = '2026, David G. Grier'
try:
    from importlib.metadata import version as _get_version
    release = _get_version('QHOT')
except Exception:
    release = '0.1.0'

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'sphinxcontrib.bibtex',
]

# The peer-reviewed literature that the documentation cites, with DOIs.
bibtex_bibfiles = ['references.bib']
bibtex_default_style = 'plain'
bibtex_reference_style = 'author_year'

# Optional accelerators (torch) are not installed on the documentation
# host, so the annotations that name them cannot be resolved.  The
# annotations are then shown as they are written, which is what we want.
suppress_warnings = ['sphinx_autodoc_typehints.forward_reference']

# Napoleon settings for NumPy-style docstrings
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_use_param = False
napoleon_use_rtype = False

# autodoc settings
autodoc_member_order = 'bysource'
autodoc_default_options = {
    'undoc-members': False,
    'show-inheritance': True,
}

# Optional dependencies that cannot be imported on a doc-build host
autodoc_mock_imports = [
    'cupy',
    'QVideo',
]

# intersphinx: link to external package docs
intersphinx_mapping = {
    'python':    ('https://docs.python.org/3', None),
    'numpy':     ('https://numpy.org/doc/stable', None),
    'scipy':     ('https://docs.scipy.org/doc/scipy', None),
    'pyqtgraph': ('https://pyqtgraph.readthedocs.io/en/latest', None),
}

exclude_patterns = ['_build']


def setup(app):
    '''Suppress spurious duplicate-object warnings from Sphinx 8.x.

    Sphinx 8.x's ObjectDescription generates class member directives both
    inside the class body (via parse_content_to_nodes) and as a separate
    top-level list.  This causes every method/attribute to be registered
    twice, triggering "duplicate object description" warnings.  The fix
    marks the second registration as an alias so it silently defers to the
    first without emitting a warning.
    '''
    from sphinx.domains.python import PythonDomain
    _orig = PythonDomain.note_object
    _seen = {}

    def _dedup(self, name, objtype, node_id, aliased=False, location=None):
        if not aliased and name in _seen:
            return _orig(
                self,
                name,
                objtype,
                node_id,
                aliased=True,
                location=location,
            )
        if not aliased:
            _seen[name] = self.env.docname
        return _orig(self, name, objtype, node_id, aliased, location)

    PythonDomain.note_object = _dedup

# -- HTML output -------------------------------------------------------------

html_theme = 'pydata_sphinx_theme'
html_title = 'QHOT'
html_static_path = ['_static']
html_css_files = ['nyu.css']

html_theme_options = {
    'github_url': 'https://github.com/davidgrier/QHOT',
    'show_toc_level': 2,
    'navigation_with_keys': True,
    'show_nav_level': 2,
    'navbar_end': ['navbar-icon-links', 'theme-switcher'],
    'footer_start': ['copyright'],
    'footer_end': ['sphinx-version'],
}

# The site is small enough that the top navbar covers all navigation.
# Suppress the primary (left) sidebar so it doesn't appear empty on
# leaf pages that have no toctree children.
html_sidebars = {'**': []}
