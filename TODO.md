# QHOT — Future Work

Ideas for upgrades and extensions, in no particular order.

---

## Hardware Acceleration

Accelerate hologram computation for higher frame rates and larger SLMs.

- ~~GPU-based CGH via CUDA/cupy (`lib/holograms/cupyCGH.py` is a starting point)~~  **Done** (cupyCGH exists)
- ~~PyTorch-based CGH for cross-platform GPU acceleration (CUDA, MPS, CPU fallback)~~  **Done** (v1.1.0, `TorchCGH`)
- ~~Automatically select the most performant CGH implementation available on the platform~~  **Done** (v1.1.0, `choose_cgh()`)
- Investigate OpenCL for portability across GPU vendors
- Benchmark CPU vs GPU for typical SLM resolutions
- Improve efficiency of trap group motion (reduce redundant CGH recomputation on bulk moves)

---

## CGH Diffraction Efficiency

The linear-superposition algorithm in `CGH` already improves diffraction
efficiency by (1) randomizing the relative phases of the traps and (2)
introducing a small amount of position jitter in trap arrays to break
their symmetry.  Further improvements are possible:

- **Phase optimisation** (method 3): iteratively optimize the relative
  phases of all traps to maximize diffraction efficiency, using the
  algorithm described by Curtis et al. (2002).
  https://doi.org/10.1016/S0030-4018(02)01524-9
- **Direct binary search** (method 4): optimize both diffraction
  efficiency and fidelity by direct binary search over the hologram
  pixels, using the method described by Polin et al. (2005).
  M. Polin, K. Ladavac, S.-H. Lee, Y. Roichman, and D. G. Grier,
  "Optimized holographic optical traps," *Opt. Express* **13**, 5831
  (2005). https://doi.org/10.1364/OPEX.13.005831

Both methods are likely too slow for real-time use, but could be applied
in a background thread to iteratively refine static trapping patterns
while the interactive session continues.

---

## Task Framework

~~Core infrastructure: `QTask` (frame-synchronized base class with
PENDING / RUNNING / COMPLETED / FAILED state machine) and
`QTaskManager` (blocking queue + parallel background tasks, driven
by `QHOTScreen.rendered`).~~  **Done** (`lib/tasks/`)

Concrete task implementations still to be written (`tasks/lib/`):

**Timing and control**

- `Delay` — wait N frames before the next task starts; the simplest
  building block for sequenced experiments
- `Repeat` — run a sub-sequence of tasks a fixed number of times

**Trap manipulation**

- `ClearTraps` — remove all traps from the overlay
  (`duration=0`, action in `initialize()`)
- `AddTrap` — add a single tweezer at a specified position
- `Move` — translate a trap or group smoothly from its current
  position to a target along a parameterized trajectory; supports
  linear interpolation and spline smoothing
- `Translate` — convenience wrapper around `Move` for a simple
  displacement vector
- `Circle` — move a trap (or each trap in a group) around a
  circular arc at a controlled angular speed
- `Spiral` — move a trap outward/inward along an Archimedean spiral;
  useful for sweeping a trapping region
- `RotateGroup` — rotate a `QTrapGroup` by a specified angle around
  its centroid over N frames
- `MorphPattern` — interpolate smoothly between two complete trap
  configurations loaded from JSON files

**Recording and I/O**

- `Record` — start the DVR at `initialize()` and stop it at
  `complete()`; runs as a non-blocking background task so that
  motion tasks proceed in parallel
- `Snapshot` — save a single camera frame to disk via `QSaveFile`
- `SaveTraps` — serialise the current overlay to JSON via `QSaveFile`
- `LoadTraps` — deserialise a JSON trap file into the overlay

**Hologram control**

- `SetHologram` — display a pre-computed phase pattern on the SLM
  directly, bypassing the CGH pipeline; useful for replaying
  optimized holograms
- `OptimizePhases` — background task that iteratively improves trap
  phases using the Curtis et al. algorithm; emits updated holograms
  as it converges (see CGH Diffraction Efficiency section)

**Measurement**

- `Approach` — bring two traps together at a controlled rate while
  recording video; foundation for colloidal interaction measurements
- `Separate` — move two traps apart at a controlled rate
- `MeasureStiffness` — hold a trap stationary for N frames, record
  Brownian motion of the trapped particle, and estimate trap
  stiffness from the mean-square displacement
- `EscapeForce` — ramp trap velocity until the particle escapes,
  measuring the escape speed as a proxy for trap stiffness

**Assembly and rearrangement**

- `Assemble` — rearrange traps from an arbitrary initial
  configuration to a target pattern using collision-free routing
  (A* or RRT on the trap graph); pairs naturally with `Record`
- `AutoTrap` — detect candidate particles in the camera field of
  view and place tweezers on them automatically (requires particle
  detection backend; see Automatic Object Detection section)

---

## Trap Group Rotation

~~Interactive and programmatic rotation of trap groups.~~

- ~~2D in-plane rotation (around z-axis) of `QTrapGroup`~~ **Done** (v1.2.0, Alt + drag gesture)
- 3D rotation (tilt/tumble) of planar trap configurations
- ~~UI handle or mouse gesture for interactive rotation~~ **Done** (v1.2.0)
- ~~Rotation center: group centroid or user-specified pivot~~ **Done** (v1.2.0, group centroid)
- More efficient rotation algorithm for large groups (currently O(N) cache invalidations)

---

## CGH Calibration

CGH calibration is inherently manual — all known implementations rely on
operator measurement of system parameters. Improvements in this area:

- Calibration wizard UI (step-by-step procedure with prompts)
- Documentation: calibration procedure guide in `help/`

---

## QInstrument Integration

Unified instrument control layer.

- Connect QInstrument device drivers (stages, shutters, lasers, etc.)
- Coordinate trap state with physical instrument state
- Event-driven architecture: trap events trigger instrument actions

---

## TOML-Based Instrument Profiles

Support different custom trapping instruments without code changes.

- Per-instrument TOML profile: CGH parameters, camera, SLM geometry
- Profile selector at startup or in settings
- Profiles stored in a well-defined location (`~/.config/QHOT/` or project-local)
- Migration path from the current `parameters.toml` in `lib/holograms/`

---

## Wireless Phone / Tablet Interface

Remote control of QHOT from a mobile device.

- WebSocket or REST API server embedded in QHOT
- Minimal browser-based UI for trap manipulation (drag, add, delete)
- Authentication / local-network-only access
- Possible use cases: hands-free trap repositioning during experiments

---

## Automatic Object Detection and Trapping

Detect objects in the camera field of view and trap them automatically.

- Identify candidate particles/objects from live video frames
- Place traps on detected objects with a single action or automatically
- Object detection may become a QVideo capability (video analysis pipeline)
- Potential backends: intensity thresholding, blob detection, ML-based detection
- Closed-loop: update trap positions as detected objects drift before capture

---

## Persistence and Reproducibility

Save and restore experimental state for reproducible measurements.

- ~~Save and load trap configurations (positions, types, parameters) to/from JSON or TOML~~  **Done**
- Experiment log: record trap events, positions, and timestamps automatically
- Export trap trajectories as data files for post-processing

---

## SLM Optics

Expand the range of structured light modes and improve trap quality.

- Wavefront/aberration correction via Zernike polynomial overlays — standard in SLM setups
- Physical unit calibration: pixel ↔ μm mapping so trap positions can be specified in physical units
- Structured light modes beyond vortex and ring (Bessel beams, Laguerre-Gaussian families)

---

## UI and Interaction

Improve the interactive experience during experiments.

- ~~Undo/redo for trap operations — accidental moves are common during experiments~~  **Done** (v1.3.0, `QUndoStack` in overlay; Edit menu)
- ~~Trap locking: mark individual traps as immovable to prevent accidental repositioning~~  **Done** (v1.4.0, Ctrl+Alt+click; `QTrap.locked`; `LockCommand`)
- ~~Keyboard shortcuts for common actions (add trap, clear all, toggle overlay)~~  **Done** (v1.5.0, `_setupShortcuts()`; Ctrl+T, Ctrl+Backspace, Ctrl+\\)
- Copy/paste for trap groups — duplicate a configuration with an offset

---

## Architecture

Structural improvements to the codebase.

- Plugin system for custom trap types so users can add new traps without modifying core code
- ~~Decouple CGH computation rate from display frame rate — separate the two update loops~~  **Done** (hologram timer, `QHOT.COMPUTE_INTERVAL`; `QTrapSync` replicas)
- Event bus or signal log for debugging signal/slot chains

---

## Testing and Quality

Strengthen the test suite and catch regressions early.

- Property-based tests (e.g. with `hypothesis`) for CGH coordinate mapping
- Performance regression tests — track CGH compute time across commits

---

## Type System

~~Strengthen type safety across the codebase.~~

- ~~Create `lib/types.py` defining `Hologram` and `Field` type aliases~~  **Done**
- ~~Use those types consistently throughout `lib/holograms/` and `traps/`~~  **Done**

---

## Release and Distribution

~~Prepare QHOT for public release.~~

- ~~Check appropriateness of current license for a public release~~  **Done** (GPLv3)
- ~~Create a PyPI package and publish to the Python Package Index~~  **Done** (v1.0.0)
- ~~Create a ReadTheDocs project and publish the Sphinx docs~~  **Done**
- Add references to relevant literature (holographic optical trapping, SLM CGH algorithms)

---

## pylorenzmie Integration

Combined holographic manipulation and in-situ characterization.

- Feed live camera frames to pylorenzmie for particle tracking and sizing
- Overlay characterization results (radius, refractive index) on `QHOTScreen`
- Closed-loop control: move traps based on characterization output
- Enables automated single-particle measurements
