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
:cite:t:`ashkin1986`.  Its discovery was the subject of Arthur Ashkin's
share of the 2018 Nobel Prize in Physics, awarded "for the optical
tweezers and their application to biological systems"
(`The Nobel Prize in Physics 2018
<https://www.nobelprize.org/prizes/physics/2018/summary/>`_).  In QHOT a plain focused beam is a
:class:`~QHOT.traps.QTweezer.QTweezer`.

Holographic optical trapping
----------------------------

*Holographic optical trapping* divides one laser beam into many
independently controllable traps by imposing a computed phase pattern
on the beam's wavefront before it is focused by the objective lens.
:cite:t:`dufresne1998` introduced the idea of using a
diffractive optical element to project an
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
carry out.  Moving a trap across the field of view involves multiplying
its field by a phase ramp. Moving it along the optical axis involves
adding a quadratic term to the phase of the complex field
(:cite:p:`dufresne2001`). Both are described by
:class:`~QHOT.lib.holograms.optics.Optics`.

Structured traps
----------------

The phase profile of a trapping beam can also shape its focus.
A helical phase
:math:`e^{i\ell\theta}` endows the light with orbital angular momentum
(:cite:p:`allen1992`) and causes it to focus into a bright ring with
a dark core. Such a topological trap is called an optical vortex.
By transferring its orbital angular momentum to illuminated objects,
an optical vortex can cause them to revolve around the optical axis (:cite:p:`he1995`). The dark core of an optical vortex also forms a trap for
absorbing, reflecting and low-index particles that are repelled by light
(:cite:p:`gahagan1996`).
The structure of holographically projected optical vortices
is described by :cite:t:`curtis2003a`, and vortices whose intensity and
phase are modulated around the ring by :cite:t:`curtis2003b`.
:cite:t:`roichman2006` project extended traps of other shapes by
shaping the phase.
In QHOT these are the
:class:`~QHOT.traps.QVortex.QVortex` and
:class:`~QHOT.traps.QRingTrap.QRingTrap`, and a group of traps is
structured by the superposition of its members.

Real-time computation
---------------------

Moving traps in real time requires a new hologram for every video
frame.
:cite:t:`bianchi2010` showed that graphics processors make this
fast, which is the role of the PyTorch, CuPy and numba backends of QHOT.
