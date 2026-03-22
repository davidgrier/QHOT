# QHOT — Future Work

Ideas for upgrades and extensions, in no particular order.

---

## Hardware Acceleration

Accelerate hologram computation for higher frame rates and larger SLMs.

- GPU-based CGH via CUDA/cupy (`lib/holograms/cupyCGH.py` is a starting point)
- PyTorch-based CGH for cross-platform GPU acceleration (CUDA, MPS, CPU fallback)
- Automatically select the most performant CGH implementation available on the platform
- Investigate OpenCL for portability across GPU vendors
- Benchmark CPU vs GPU for typical SLM resolutions
- Improve efficiency of trap group motion (reduce redundant CGH recomputation on bulk moves)

---

## Task Framework

A *task* is an operation on traps that may also coordinate other subsystems
(camera, stage, laser shutter, data recorder, etc.).  Tasks are the building
block for automated experimental workflows.

**Architecture**

- Each task is a self-contained, asynchronous unit (e.g. a `QThread` subclass
  or coroutine) with a well-defined start, progress signal, and completion signal
- Tasks may read and write trap state via the existing trap/overlay API
- Tasks may subscribe to camera frames, instrument events, or other signals
- Simple tasks can be composed into compound tasks (sequential, parallel, or
  conditional pipelines)
- The `tasks/` directory is reserved for this work

**Example tasks**

- *Rearrangement*: move existing traps from one configuration to another
  without inter-trap collisions (collision-free routing, e.g. A* or RRT on
  the trap graph)
- *Interaction measurement*: combine controlled trap motion with synchronised
  video recording to measure colloidal interaction potentials (approach/separation
  curves, force via trap stiffness)
- *Automatic trapping*: detect particles in the camera field of view and
  create tweezers to capture them (integrates with the Automatic Object
  Detection section above)
- *Compound task*: chain simple tasks — e.g. automatically trap a set of
  particles and then rearrange them into a target pattern

**Supporting infrastructure**

- Task queue / scheduler so multiple tasks can be enqueued and run in order
- Progress and status reporting back to the main UI
- Trap stiffness calibration primitives (Brownian motion analysis, escape-force
  method) usable as building blocks inside larger tasks

---

## Trap Group Rotation

Interactive and programmatic rotation of trap groups.

- 2D in-plane rotation (around z-axis) of `QTrapGroup` and `QTrapArray`
- 3D rotation (tilt/tumble) of planar trap configurations
- UI handle or mouse gesture for interactive rotation
- Rotation center: group centroid or user-specified pivot

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

- Save and load trap configurations (positions, types, parameters) to/from JSON or TOML
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

- Undo/redo for trap operations — accidental moves are common during experiments
- Trap locking: mark individual traps as immovable to prevent accidental repositioning
- Keyboard shortcuts for common actions (add trap, clear all, toggle overlay)
- Copy/paste for trap groups — duplicate a configuration with an offset

---

## Architecture

Structural improvements to the codebase.

- Plugin system for custom trap types so users can add new traps without modifying core code
- Decouple CGH computation rate from display frame rate — separate the two update loops
- Event bus or signal log for debugging signal/slot chains

---

## Testing and Quality

Strengthen the test suite and catch regressions early.

- Property-based tests (e.g. with `hypothesis`) for CGH coordinate mapping
- Performance regression tests — track CGH compute time across commits

---

## Type System

Strengthen type safety across the codebase.

- Create `lib/types.py` defining `Hologram` and `Field` type aliases (e.g. `np.ndarray` specialisations)
- Use those types consistently throughout `lib/holograms/` and `traps/`
- Enables better static analysis and clearer API documentation

---

## Release and Distribution

Prepare QHOT for public release.

- Check appropriateness of current license for a public release
- Create a PyPI package and publish to the Python Package Index
- Create a ReadTheDocs project and publish the Sphinx docs
- Add references to relevant literature (holographic optical trapping, SLM CGH algorithms)

---

## pylorenzmie Integration

Combined holographic manipulation and in-situ characterization.

- Feed live camera frames to pylorenzmie for particle tracking and sizing
- Overlay characterization results (radius, refractive index) on `QHOTScreen`
- Closed-loop control: move traps based on characterization output
- Enables automated single-particle measurements
