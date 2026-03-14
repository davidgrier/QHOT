# QFab

[![Tests](https://github.com/davidgrier/QFab/actions/workflows/tests.yml/badge.svg)](https://github.com/davidgrier/QFab/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/davidgrier/QFab/branch/main/graph/badge.svg)](https://codecov.io/gh/davidgrier/QFab)

**QFab** is a Python application for holographic optical trapping — controlling
spatial light modulators (SLMs) to create, move, and reconfigure optical tweezers
in real time using a live camera feed.

## Features

- Real-time hologram computation (CGH) with GPU-optional acceleration
- Interactive trap manipulation via camera overlay
- Modular trap types: single tweezers, vortex beams, ring traps, arrays, and
  dot-matrix text patterns
- Extensible display filter pipeline (blur, edge detection, RGB selection, sample-hold)
- Configuration save/restore via TOML
- Full unit-test suite (~700+ tests)

## Requirements

- Python 3.10+
- PyQt5 ≥ 5.15
- pyqtgraph ≥ 0.13
- numpy ≥ 1.24
- scipy ≥ 1.10
- tomlkit ≥ 0.11
- [QVideo](https://github.com/davidgrier/QVideo) — camera interface library

## Installation

```bash
# Install QVideo first (see its own instructions), then:
pip install .
```

Or for development:

```bash
pip install -e .
```

## Usage

```bash
pyfab
```

Or from Python:

```python
from QFab.pyfab import main
main()
```

## Trap types

| Class | Description |
|---|---|
| `QTweezer` | Single Gaussian tweezer |
| `QVortex` | Laguerre-Gaussian vortex beam |
| `QRingTrap` | Ring-shaped optical trap |
| `QTrapArray` | Rectangular grid of tweezers with optional mask and position jitter |
| `QLetterArray` | Single dot-matrix character (A-Z, a-z, 0-9) rendered as tweezers |
| `QTextArray` | String of `QLetterArray` characters |

## Project structure

```
QFab/
├── pyfab.py          — Main application window
├── PyFab.ui          — Qt Designer UI layout
├── lib/              — Core library (SLM, CGH, trap infrastructure)
│   ├── QSLM.py
│   ├── QFabScreen.py
│   ├── QSaveFile.py
│   ├── holograms/    — Hologram computation
│   └── traps/        — Trap base classes and overlay
├── traps/            — Concrete trap implementations
└── tests/            — Unit tests
```

## License

See [LICENSE](LICENSE).
