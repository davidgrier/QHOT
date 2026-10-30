Holographic optical trapping
============================

This page describes the ideas that QHOT puts to work, and where to find
them in the code.  The sources are cited with their DOIs in the
:doc:`references`.

Optical tweezers
----------------

A single tightly focused beam of light can hold a small dielectric
particle near its focus, because the gradient of the light's intensity
pulls the particle toward the brightest point.  This single-beam gradient
force trap, the *optical tweezer*, was demonstrated by
:cite:t:`ashkin1986`.  In QHOT a plain focused beam is a
:class:`~QHOT.traps.QTweezer.QTweezer`.

Holographic optical trapping
----------------------------

*Holographic optical trapping* divides one laser beam into many
independently controllable traps, by imposing a computed phase pattern
on the beam's wavefront before it is focused by the objective lens.
:cite:t:`dufresne1998` used a diffractive optical element to project an
array of optical tweezers from a single beam, and :cite:t:`dufresne2001`
made the pattern *dynamic* with a spatial light modulator (SLM) addressed
by a computer-generated hologram.  Reviews of the field are given by
:cite:t:`grier2003` and :cite:t:`grier2006`, and, from the broader
perspective of optical micromanipulation, by :cite:t:`padgett2011` and
:cite:t:`dholakia2011`.  Liquid-crystal displays were also used to
write holograms for optical trapping by :cite:t:`reicherter1999` and
:cite:t:`liesener2000`.

The phase-only hologram
-----------------------

An SLM changes only the phase of the light.  The field that creates a
set of traps is a superposition of the field that creates each trap, and
the hologram is the phase of that sum (:cite:p:`curtis2002`).  This is
the algorithm that :mod:`QHOT.lib.holograms.reference` states as plainly
as possible, and that the backends in :mod:`QHOT.lib.holograms.backends`
carry out.  Moving a trap multiplies its field by a phase ramp, and
moving it along the optical axis adds a quadratic phase
(:cite:p:`dufresne2001`); both are described by
:class:`~QHOT.lib.holograms.optics.Optics`.

Structured traps
----------------

The phase of a trap can also shape the focus.  A helical phase
:math:`e^{i\ell\theta}` gives the light orbital angular momentum
(:cite:p:`allen1992`) and a ring-shaped focus with a dark core, which
can twist the particles it holds (:cite:p:`he1995`) or trap them in the
dark (:cite:p:`gahagan1996`).  The structure of such holographic vortices
is described by :cite:t:`curtis2003a`, and vortices whose intensity and
phase are modulated around the ring by :cite:t:`curtis2003b`.
:cite:t:`roichman2006` project extended traps of other shapes by
shaping the phase.  In QHOT these are the
:class:`~QHOT.traps.QVortex.QVortex` and
:class:`~QHOT.traps.QRingTrap.QRingTrap`, and a group of traps is
structured by the superposition of its members.

Real-time computation
---------------------

Moving traps in real time requires a new hologram for every video
frame.  :cite:t:`bianchi2010` showed that graphics processors make this
fast, which is the role of the PyTorch, CuPy and numba backends of QHOT.
