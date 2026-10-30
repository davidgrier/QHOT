# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python -m pytest --tb=short -q

# Run a single test file
python -m pytest tests/test_qhotscreen.py

# Run a single test
python -m pytest tests/test_qhotscreen.py::ClassName::test_method

# Run with coverage report
python -m pytest --cov=QHOT --cov-report=term-missing

# Build HTML documentation  (output: docs/_build/html/index.html)
sphinx-build -b html docs docs/_build/html
```

**Install for development:**
```bash
pip install -e ".[dev,pyqt6]"  # or pyqt5, pyside6
pip install -e ".[docs]"  # for documentation builds
```

**Launch the application:**
```bash
qhot
```

## Releasing

When pushing a new version, always create a GitHub Release (not just a tag) so
that Zenodo's webhook fires and mints a DOI:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes
```

Pushing the tag alone is not sufficient — Zenodo listens for the GitHub
`release` event, not a raw tag push.

## Architecture

QHOT is a holographic optical trapping system. It uses a spatial light modulator (SLM) to display computer-generated holograms (CGH) that focus laser light into configurable optical traps. The main window (`qhot.py`) orchestrates several subsystems connected via Qt signals:

```
qhot.py (QHOTWindow)
  ├── QHOTScreen      — live video display with interactive trap overlay
  ├── QSLM            — SLM display window (secondary screen, shows phase pattern)
  ├── CGH             — calibration and hologram pipeline (computes in a QThread)
  ├── QCGHTree        — Qt parameter tree for CGH calibration
  └── QSaveFile       — TOML config and image file I/O
```

**Signal flow:** trap or calibration changes → `QHOT._scheduleCompute` → a timer (`QHOT.COMPUTE_INTERVAL`, independent of the video) calls `CGH.compute(overlay.pattern())` → the worker thread computes with a `Backend` → `CGH.hologramReady` → `QSLM.setData()` updates SLM display.

**Threading rule:** the compute thread must never touch anything the interface edits. `CGH.compute` captures two plain values at the request: the pattern (`QTrapOverlay.pattern()`, a tuple of immutable `TrapSpec`) and the calibration (`CGH.optics`, an immutable `Optics`). Anything a hologram depends on must therefore be in the `TrapSpec` or the `Optics`. There are no locks and no caches to invalidate: a hologram is computed from scratch, and the only thing kept between holograms is the structuring fields, keyed by value.

**The algorithm** is stated in `lib/holograms/reference.py` (slow, literal, float64). Backends are tested against it, so change the reference and its tests first, then make a backend agree. A trap's field is `amplitude * exp(i phase) * D(r) * S`, where `D` is the displacement and `S` the structuring field (`QTrap.structuringField(geometry, **params)`, a function of values, given only a `Geometry`). A group's structure is the superposition of its members', recursively. A plain group has no amplitude of its own; a composite (`QTrapGroup.composite = True`) does.

**Trap hierarchy:**
- `lib/traps/QTrap.py` — base class; all traps have a 3D position and phase profile
- `lib/traps/QTrapGroup.py` — recursive grouping of traps
- `lib/traps/QTrapOverlay.py` — `QGraphicsScene` subclass; handles mouse/wheel interaction
- `traps/` — concrete trap types: `QTweezer`, `QVortex`, `QRingTrap`, `QTrapArray`, `QLetterArray`, `QTextArray`

**Hologram computation** (`lib/holograms/`):
- `CGH.py` — calibration parameters (pixel pitch, wavelength, focal length, etc.) and the pipeline: `compute(pattern)`, `hologramReady`, `computeFailed`
- `Optics.py` — the calibration as an immutable value; `Geometry` is all a trap is given
- `reference.py` — the algorithm stated plainly; the standard for the backends
- `Backend.py`, `NumpyBackend.py`, `TorchBackend.py` — compute holograms from a pattern (matrix product of the phase ramps; PyTorch runs on Apple GPU, CUDA or CPU). A CuPy backend is still to be written.

## Testing

- Framework: `pytest` with `pytest-cov`; test files use `unittest.TestCase`
- Tests live in `tests/` and mirror the `lib/` and `traps/` structure
- Qt widgets require a `QApplication` instance; tests use `QApplication.instance() or QApplication(sys.argv)`
- Qt signals are tested with `QtTest.QSignalSpy`
- CI runs headless with `QT_QPA_PLATFORM=offscreen` across Python 3.11–3.12
- Coverage config in `pyproject.toml` under `[tool.coverage.*]`
- Use `# pragma: no cover` for example/main blocks and GPU-only code paths
- `QVideo` (camera library) is an external dependency installed from GitHub, not pip

## Style

- Prefer single quotes over double quotes for strings, including docstrings.
- Docstrings use NumPy style.
- Use split-string style for `__all__`: `__all__ = 'Foo Bar Baz'.split()`
- Keep all lines within 79 columns, including comments and docstrings.

## Imports

Traps do not import the hologram pipeline: they are given a `Geometry`. `reference.py` and `Backend.py` import `QHOT.traps` lazily, inside the function that needs it, to register the trap classes without a cycle.

## Naming conventions

Follow the PyQt camelCase convention throughout:
- Module files are named after the class they contain: `QFoo.py` holds `class QFoo`. Do **not** rename modules to snake_case.
- Use `camelCase` for private instance attributes on Qt classes (e.g. `self._ignoreSync`, `self._isOpen`).
- Use `snake_case` only for pure-Python, non-Qt classes.
- When renaming, update both the source file and all corresponding test files.

## `__init__.py` re-exports and `mock.patch`

Because every module `QFoo.py` defines a class `QFoo` with the same name, doing
`from .QFoo import QFoo` in an `__init__.py` shadows the submodule with the class.
`mock.patch('pkg.QFoo.attr')` resolves names via `getattr`, so it then finds the
class instead of the module and fails.

The fix is to use `patch.object` in tests rather than string-based patch targets.
`import pkg.mod as alias` also uses attribute lookup, so it has the same problem.
Use `importlib.import_module` instead, which looks up `sys.modules` directly:

```python
# avoid — breaks when QFoo is re-exported from __init__.py
with patch('QHOT.lib.QFoo.some_name'):

# avoid — import alias also uses attribute lookup, gets the class
import QHOT.lib.QFoo as _mod

# preferred — importlib bypasses attribute lookup, always returns the module
import importlib as _importlib
from QHOT.lib.QFoo import QFoo
_mod = _importlib.import_module('QHOT.lib.QFoo')
with patch.object(_mod, 'some_name'):
```

When adding a class to an `__init__.py` re-export, update any string-based patches
in the corresponding test file to use `patch.object` at the same time.
