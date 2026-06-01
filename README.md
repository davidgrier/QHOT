# QHOT

[![PyPI version](https://img.shields.io/pypi/v/QHOT.svg)](https://pypi.org/project/QHOT/)
[![Python versions](https://img.shields.io/pypi/pyversions/QHOT.svg)](https://pypi.org/project/QHOT/)
[![Tests](https://github.com/davidgrier/QHOT/actions/workflows/tests.yml/badge.svg)](https://github.com/davidgrier/QHOT/actions/workflows/tests.yml)
[![Documentation](https://readthedocs.org/projects/qhot/badge/?version=latest)](https://qhot.readthedocs.io/en/latest/)
[![License](https://img.shields.io/github/license/davidgrier/QHOT.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19254265.svg)](https://doi.org/10.5281/zenodo.19254265)

![QHOT screenshot](https://raw.githubusercontent.com/davidgrier/QHOT/main/docs/_static/screenshot.png)

**QHOT** is a Python framework for holographic optical trapping — controlling
spatial light modulators (SLMs) to create, move, and reconfigure optical traps
in real time using a live camera feed.

## Features

- Real-time hologram computation (CGH) with GPU-optional acceleration
- Interactive trap manipulation via camera overlay
- Modular trap types: single tweezers, vortex beams, ring traps, arrays, and
  dot-matrix text patterns
- Interactive display filter pipeline (smoothing, edge detection, RGB selection, sample-hold)
- Configuration save/restore via TOML
- Full unit-test suite (1400+ tests)

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

## References

- E. R. Dufresne and D. G. Grier, "Optical tweezer arrays and optical substrates
  created with diffractive optics," *Rev. Sci. Instrum.* **69**, 1974 (1998).
  https://doi.org/10.1063/1.1148883
- J. E. Curtis, B. A. Koss, and D. G. Grier, "Dynamic holographic optical
  tweezers," *Opt. Commun.* **207**, 169 (2002).
  https://doi.org/10.1016/S0030-4018(02)01524-9
- D. G. Grier, "A revolution in optical manipulation," *Nature* **424**,
  810 (2003). https://doi.org/10.1038/nature01935

## Acknowledgments
This project is maintained with support from the National Science Foundation of the United States under Award Number DMR-2428983.

## License

See [LICENSE](LICENSE).
