# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python -m pytest --tb=short -q

# Run a single test file
python -m pytest tests/test_qfabscreen.py

# Run a single test
python -m pytest tests/test_qfabscreen.py::ClassName::test_method

# Run with coverage report
python -m pytest --cov=QFab --cov-report=term-missing

# Build HTML documentation  (output: docs/_build/html/index.html)
sphinx-build -b html docs docs/_build/html
```

**Install for development:**
```bash
pip install -e ".[dev]"
pip install -e ".[docs]"  # for documentation builds
```

**Launch the application:**
```bash
pyfab
```

## Architecture

QFab is a holographic optical trapping system. It uses a spatial light modulator (SLM) to display computer-generated holograms (CGH) that focus laser light into configurable optical traps. The main window (`pyfab.py`) orchestrates several subsystems connected via Qt signals:

```
pyfab.py (QFabWindow)
  ├── QFabScreen      — live video display with interactive trap overlay
  ├── QSLM            — SLM display window (secondary screen, shows phase pattern)
  ├── CGH             — hologram computation engine (runs in QThread)
  ├── QCGHTree        — Qt parameter tree for CGH calibration
  └── QSaveFile       — TOML config and image file I/O
```

**Signal flow:** trap changes → `QTrapOverlay` emits → `CGH.computeHologram()` in worker thread → `CGH.hologramReady` → `QSLM.setData()` updates SLM display.

**Trap hierarchy:**
- `lib/traps/QTrap.py` — base class; all traps have a 3D position and phase profile
- `lib/traps/QTrapGroup.py` — recursive grouping of traps
- `lib/traps/QTrapOverlay.py` — `QGraphicsScene` subclass; handles mouse/wheel interaction
- `traps/` — concrete trap types: `QTweezer`, `QVortex`, `QRingTrap`, `QTrapArray`, `QLetterArray`, `QTextArray`

**Hologram computation** (`lib/holograms/`):
- `CGH.py` — CPU-based iterative CGH algorithm; calibration parameters (pixel pitch, wavelength, focal length, etc.)
- `cupyCGH.py` — GPU-accelerated variant (excluded from coverage)

## Testing

- Framework: `pytest` with `pytest-cov`; test files use `unittest.TestCase`
- Tests live in `tests/` and mirror the `lib/` and `traps/` structure
- Qt widgets require a `QApplication` instance; tests use `QApplication.instance() or QApplication(sys.argv)`
- Qt signals are tested with `QtTest.QSignalSpy`
- CI runs headless with `QT_QPA_PLATFORM=offscreen` across Python 3.10–3.12
- Coverage config in `pyproject.toml` under `[tool.coverage.*]`
- Use `# pragma: no cover` for example/main blocks and GPU-only code paths
- `QVideo` (camera library) is an external dependency installed from GitHub, not pip

## Style

- Prefer single quotes over double quotes for strings, including docstrings.
- Docstrings use NumPy style.

## Circular imports

`CGH` → `lib/traps` → `QTrapOverlay` → `traps/` → `QVortex`/`QRingTrap` forms a cycle. Annotate `cgh` parameters in trap subclasses with `TYPE_CHECKING`:

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from QFab.lib.holograms.CGH import CGH
```

## Naming conventions

Follow the PyQt camelCase convention for all instance attributes on Qt classes:
- Use `camelCase` for private attributes (e.g. `self._ignoreSync`, `self._isOpen`).
- Use `snake_case` only for pure-Python, non-Qt classes.
- When renaming, update both the source file and all corresponding test files.
