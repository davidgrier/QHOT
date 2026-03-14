# QFab — Future Work

Ideas for upgrades and extensions, in no particular order.

---

## Hardware Acceleration

Accelerate hologram computation for higher frame rates and larger SLMs.

- GPU-based CGH via CUDA/cupy (`lib/holograms/cupyCGH.py` is a starting point)
- Investigate OpenCL for portability across GPU vendors
- Benchmark CPU vs GPU for typical SLM resolutions

---

## Automated Task Framework

A framework for scripted, time-sequenced trap operations.

- Move traps along planned paths (linear, curved, arbitrary)
- Reorganize traps from one configuration to another without collisions
  - Collision-free routing (e.g., A* or RRT on the trap graph)
- Automated colloid interaction measurements
  - Controlled approach/separation curves
  - Force measurement via trap stiffness calibration
- Trap stiffness / calibration measurements
  - Brownian motion analysis
  - Escape-force method
- The `tasks/` directory is reserved for this work

---

## Trap Group Rotation

Interactive and programmatic rotation of trap groups.

- 2D in-plane rotation (around z-axis) of `QTrapGroup` and `QTrapArray`
- 3D rotation (tilt/tumble) of planar trap configurations
- UI handle or mouse gesture for interactive rotation
- Rotation center: group centroid or user-specified pivot

---

## Automated CGH Calibration

Replace manual CGH parameter entry with measurement-based calibration.

- Detect trap positions in camera image (centroid or Gaussian fit)
- Iterative optimization of `xs`, `ys`, `phis`, `xc`, `yc`, `zc`, `thetac`, etc.
- Calibration wizard UI (step-by-step procedure)
- Task-based implementation so calibration can run headlessly or be scripted
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
- Profiles stored in a well-defined location (`~/.config/QFab/` or project-local)
- Migration path from the current `parameters.toml` in `lib/holograms/`

---

## Wireless Phone / Tablet Interface

Remote control of QFab from a mobile device.

- WebSocket or REST API server embedded in QFab
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

## pylorenzmie Integration

Combined holographic manipulation and in-situ characterization.

- Feed live camera frames to pylorenzmie for particle tracking and sizing
- Overlay characterization results (radius, refractive index) on `QFabScreen`
- Closed-loop control: move traps based on characterization output
- Enables automated single-particle measurements
