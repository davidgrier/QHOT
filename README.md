# QHOT

**QHOT** is a Python application for holographic optical trapping — controlling
spatial light modulators (SLMs) to create, move, and reconfigure optical traps
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
- QVideo ≥ 3.2.3

## Installation

```bash
pip install QHOT
```

Or for development:

```bash
git clone https://github.com/davidgrier/QHOT.git
cd QHOT
pip install -e .
```

## Usage

```bash
qhot
```

Or from Python:

```python
from QHOT.qhot import main
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
QHOT/
├── qhot.py          — Main application window
├── QHOT.ui          — Qt Designer UI layout
├── lib/              — Core library (SLM, CGH, trap infrastructure)
│   ├── QSLM.py
│   ├── QHOTScreen.py
│   ├── QSaveFile.py
│   ├── holograms/    — Hologram computation
│   └── traps/        — Trap base classes and overlay
├── traps/            — Concrete trap implementations
└── tests/            — Unit tests
```

## Acknowledgments
This project is maintained with support from the National Science Foundation of the United States under Award Number DMR-2428983.

## License

See [LICENSE](LICENSE).
