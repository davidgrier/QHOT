# QHOT Roadmap: Recreating and Surpassing pyfab

Written 2026-10-27 after a review of pyfab (`~/python/pyfab`), QInstrument
3.0.2, QVideo 4.9 and QHOT 1.5.0.  Code-level claims come from reading
source; pyfab was not run.  Items marked "unverified" need confirmation.

## 1. What pyfab does

| Capability | pyfab implementation |
|---|---|
| Live video | `QCamera` (OpenCV, Spinnaker), filter chain, histogram tab |
| Recording | `QDVR` (AVI, HDF5), player |
| Trap overlay | `QTrappingPattern` (pyqtgraph `ScatterPlotItem`): add, delete, group, move, wheel-for-z |
| Trap types | Tweezer, vortex, ring, tilted ring, Bessel, Bessel-IPH, line, trefoil, ultra, custom (CPU and CUDA) |
| CGH | numba CPU, CUDA, cupy; background field for aberration correction |
| Hardware | IPG laser and Prior Proscan stage on a Hardware tab (hidden if absent) |
| Tasks | About 35: Assemble (A*), AutoTrap, Circle, Lattice, Overlap, SwitchPlaces, Sedimentation, MoveRecordZ, RecordBackground, ...; experiments saved as JSON |
| Vision | pylorenzmie and CNNLorenzMie: real-time localizer and estimator, post-hoc trajectories (`toVision`, `doVision`, `AutoTrap`) |
| Config | Ad hoc JSON; Qt resource-compiled help |

Debt: PyQt5 only, hard-coded paths, 2020-era pinned dependencies,
`obsolete/` code, compiled `.ui` files, hardware wired in directly.

## 2. Where QHOT stands

Ahead of pyfab:

- Trap model: `QTrap`, `QTrapGroup` and `QTrapOverlay` are separate; undo/redo,
  locking, group rotation and JSON round-trip.
- CGH: CPU and Torch backends (CUDA, MPS, CPU) with auto-selection; per-trap
  and per-group field cache (a group move costs one outer product).
- Tasks: `QTask` state machine, `QTaskManager` with blocking and background
  tasks, saved and reorderable queue, parameter tree.
- Calibration: ParameterTree backed by TOML.
- Hygiene: `qtpy`, PyPI, Zenodo, CI, about 1400 tests, docs.

Missing relative to pyfab:

- Trap types: Bessel, line, trefoil, custom, tilted ring.
- CGH background (aberration) field.
- All hardware control (no QInstrument integration).
- Vision and AutoTrap.
- Most of the task library (Circle, Assemble, Lattice, Overlap, SwitchPlaces,
  Sedimentation, MoveRecordZ).
- Histogram tab.

## 3. Assessment of QHOT's divergences from pyfab

| Choice | Verdict | Reasoning |
|---|---|---|
| Delegate video, DVR, filters, histogram to QVideo | Positive | Removes about 40% of pyfab's code; QVideo 4.9 has recorder and player, filter rack, histogram, ROI, YOLO and trackpy overlays |
| `qtpy` instead of PyQt5 | Positive | PyQt6 is production on macOS; future-proof |
| `QTrapOverlay` as `QGraphicsScene` plus signals | Positive | Much cleaner than `ScatterPlotItem` plus raw mouse signals |
| Trap tree with groups, `to_dict`, class registry | Positive | Makes tasks and files serializable |
| Per-trap field cache | Positive | Large efficiency gain |
| Torch CGH | Positive | Portable replacement for CUDA-only code |
| TOML and ParameterTree for calibration | Mostly positive | Declarative and editable; TOML suits instrument profiles |
| `QUndoStack` | Positive | Accidental moves are common |
| Compute driven by `screen.rendered` | Mixed, leaning negative | Couples hologram latency to the display rate (capped at 30 fps); already in TODO |
| CGH on a `QThread` reading live trap objects | Risk (unverified) | `compute()` and `fieldOf()` read trap attributes and write the cache on the worker thread, while the cache is invalidated by main-thread `changed` signals; expect a rare race during fast drags; `_computePending` only partly helps |
| One monolithic window and `.ui` | Mixed | Fine now; unwieldy once hardware and vision arrive |
| Tasks call `animateClick()` on `QDVRWidget` buttons | Negative | Should use the headless `QRecorder` and `QPlayer` in QVideo 4.9 |
| `QHOT.__init__` reaches into `dvr.source` and `playback` | Neutral | Ties it to QDVRWidget internals |

Net: QHOT is a clear improvement.  The two things to change are the
frame-coupled compute and the thread-safety model.

## 4. Plan

### Phase 0: foundations (QHOT)

1. **Done (2026-10-29).** Make CGH thread-safe.  `compute()` takes an immutable snapshot (position,
   amplitude, phase and structure parameters per leaf) built on the main
   thread; the worker owns the cache.
2. **Done (2026-10-29).** Decouple compute from display: a coalescing, latest-wins compute loop with
   its own rate limit.  `rendered` stays for tasks.
3. **Done (2026-10-29).** Tasks drive `dvr.recorder` and `dvr.playback` instead of clicking buttons.

### Phase 1: parity with pyfab's core

4. Trap types as plugins on `QTrap.__init_subclass__`: Bessel, line, trefoil,
   custom, tilted ring.
5. CGH background field (also the natural home for Zernike aberration
   correction).
6. Port high-value tasks: Circle, Lattice, Overlap, SwitchPlaces, Assemble,
   Sedimentation.
7. Histogram tab using QVideo's `QVideo.widgets.QHistogramWidget`.

### Phase 2: hardware through QInstrument

8. Hardware tab built on `QInstrumentRack`.  QInstrument already has
   IPGLaser, Proscan and Novanta Opus, each with widget, tree, fake and
   instrument classes; the fakes make the tab testable without hardware.
9. Optional instrument interface in the profile file so tasks can use
   `laser.power` and `stage.z`; add a `MoveStage` task for 3D experiments.
10. Add missing devices to QInstrument as needed (shutters, etc.).
11. Per-rig TOML profiles: camera, SLM geometry, CGH parameters, instrument
    list.  Replaces `parameters.toml` and `~/.QInstrument` JSON.

### Phase 3: vision and automation

12. Detection as a QVideo capability.  QVideo already has trackpy and YOLO
    overlays and a `blob` filter; add a `QDetector` that emits particle
    positions per frame.
13. QHOT `AutoTrap` (detect, then trap) and closed-loop tracking tasks;
    pylorenzmie as an optional backend.
14. Experiment log of trap events and timestamps, with trajectory export.

### Changes needed in the sibling projects

- QVideo: detection pipeline (item 12); hardware ROI and binning (already in
  its `TODO.md`); documented headless recording API (largely done).
- QInstrument: composing instruments into a profile; a thread-model note for
  use from tasks.  The 3.0.x threading fixes suggest it is still settling.

## 5. Recommended order

Items 1 and 2 first, because everything later depends on a reliable compute
loop.  Then the QInstrument Hardware tab (items 8 to 11), the largest gap
relative to pyfab and built on code that already exists.
