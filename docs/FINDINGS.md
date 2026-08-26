# What is actually new here, and what is not

This repository contains three results about getting QAOA to work on a *constrained*
problem. **One of them appears to be new. Two are rediscoveries of published work**,
kept because the measurements are worth having, not because the ideas are ours.

The prior-art searches were run with an AI assistant; every source named below was
then checked by me. Disclosure in the README.

This file exists so that a reader who knows the literature can see, quickly, which is
which — and so that nobody cites the wrong one. A prior-art scan was run on
2026-08-24 (about a dozen searches plus a domain survey); its limits are recorded at
the bottom.

Every number below is measured in this repository and checked by a test. The
write-up each one lives in is linked, and `tests/test_*_tables.py` pins it to the
artifact it came from.

---

## The three legs

A constrained problem handed to QAOA needs three separate things to be right. Each
failure is **invisible in the metric one would naturally watch**, which is the reason
all three are worth writing down together.

| | what must be right | what goes wrong if it is not | new? |
|---|---|---|---|
| 1 | **the encoding is sound** | mass piles onto states that are not schedules, and the metric reports success | **apparently yes** |
| 2 | **the penalty weight** | the landscape stops being reproducible | no — known |
| 3 | **the tuning selection rule** | the run that would have worked is not the one kept | no — known |

---

## Leg 1 — encoding soundness. **This is the contribution.**

`Checkpoint` pins the battery's state of charge every `k` slots instead of carrying a
slack register at every interior hour. Pinning bounds the between-checkpoint
excursion by `⌊k/2⌋`, so **every zero-penalty assignment is genuinely feasible**
whenever `⌊k/2⌋ ≤ min(k₀, n_max − k₀)` — the condition `max_sound_spacing()`
computes. This is a *proved* property of the encoding, not a bias.

**Why that is the part worth having.** Removing slack variables is a crowded field —
unbalanced penalization, exponential and Heaviside custom penalties, Lagrangian and
augmented-Lagrangian duals, and in this application domain a
Powell–Hestenes–Rockafellar formulation for stochastic unit commitment. **All of them
bias the search toward feasibility. None of them guarantees that the minimum-energy
assignment is feasible.** A 2026 survey of quantum computing for unit commitment —
the application area with exactly this constraint structure — records no encoding
with such a guarantee and describes feasibility as an open challenge.

**So the qubit count is not the headline.** 117 qubits → 52 on the real instance is
real, and it is the *contested* half: several published methods also remove slack.
The uncontested half is that ours removes slack **and keeps a guarantee**.

**What it costs when the guarantee is absent, measured.** At a penalty weight below
the soundness threshold, the QUBO's own minimum-energy assignment is infeasible — and
the standard metric cannot tell:

> At α = 0.006, **32 of 40 tunings "clear" the concentration bar**, with the best
> putting 0.0959 mass on the QUBO's minimizer — against a bar of 0.078125. Every one
> of those is mass on a state that is not a schedule.
> — [`results/basin-structure-reps2.md`](results/basin-structure-reps2.md)

Read the clearing column without the exactness column and weak penalties look like
the best setting on the page. That is the failure mode a soundness guarantee
removes.

**Where the evidence is.** Three tests, covering three different strengths of the
claim, all in `tests/test_qubo_search.py`:

| test | what it establishes |
|---|---|
| `test_every_zero_penalty_assignment_is_feasible` | **the published sentence, exhaustively** — enumerating the whole register on three instances (T = 3 and 4, banded and unbanded, every sound spacing), *every* zero-penalty assignment is feasible |
| `test_checkpoint_is_sound_at_scale` | the **minimum-energy** assignment is feasible at T ∈ {6, 12, 24}, past brute-force range, for every sound spacing |
| `test_the_soundness_guard_refuses_an_unsound_spacing` | past `max_sound_spacing` the encoding **refuses to build** rather than silently biasing |

The exhaustive test isolates the penalty by differencing against a zero-weight QUBO
on the same encoding, so it exercises `build_qubo`'s penalty terms directly rather
than any reimplementation. It is non-vacuous: the instances carry 7, 7 and 19
zero-penalty assignments respectively, and none is infeasible.

Also: the condition and its derivation in `src/quantum_solar/encodings.py`
(`max_sound_spacing`); qubit accounting and the annual cost of over-checkpointing in
[`results/slack-free-encoding.md`](results/slack-free-encoding.md); the trap
quantified in [`results/basin-structure-reps2.md`](results/basin-structure-reps2.md).

**What is *not* established: that the bound is tight.** Nothing here shows that a
spacing one past `max_sound_spacing` would actually admit an infeasible zero-penalty
assignment — the guard refuses to construct it, so the question cannot be probed
without disabling the guard. The claim is that the condition is **sufficient** and
enforced, not that it is necessary.

**The competing approach a reader will raise.** Feasibility-preserving mixers (the
quantum alternating operator ansatz, XY mixers) guarantee feasibility *by
construction* by never leaving the feasible subspace. That is an alternative and it
is not addressed here. The relevant differences: XY mixers conserve excitation
number, which fits fixed-cardinality constraints rather than an interval constraint
holding at every step; they need explicit structural knowledge of the feasible set and
a non-trivial feasible initial state; and all-to-all topologies carry a barren-plateau
risk. **None of that is measured here** — it is why the alternative exists, not a
finding against it.

---

## Leg 2 — the penalty weight. **Known idea; the reproducibility cost is the part worth reading.**

`α* = (objective span across feasible solutions) / (penalty scale)` = **0.0209** on
the worked instance. The default rule of thumb is ~10× the objective scale, which on
these instances is a **48× overshoot**.

**This is a rediscovery.** Setting a QUBO penalty from the objective's range, and
seeking the smallest sufficient penalty, are both established practice — the standard
tutorial guidance is 10–100× the maximum coefficient, and published work already
evaluates penalty weights *as fractions of the objective range* and finds small values
beat conservative bounds. **Our `default_weights` implements the standard heuristic,
so "48× overshoot" is a critique of common practice rather than of a local mistake.**

**What does not appear in the sources scanned** is the consequence measured here:
overshoot costs **reproducibility**, not just solution quality or convergence speed.

> At reps=1 the basin count is **1** at α\* and at every α below it, rising to **19**
> at the default weight. The usable window is `0.010 ≤ α ≤ 0.021` and **α\* sits at
> its upper edge** — 1.4× above it the count already doubles.
> — [`results/basin-structure.md`](results/basin-structure.md)

That study was **pre-registered and its prediction was falsified** — it predicted a
U-shape with a strict minimum at α\*; there is no lower branch. The mechanism was
real but invisible to the metric: below α\* the search converges just as reproducibly,
to a single *wrong* basin.

At reps=2 the single-basin regime does not survive at all — **15 basins at α\***, and
11 is the smallest count anywhere on the ladder
([`results/basin-structure-reps2.md`](results/basin-structure-reps2.md)).

---

## Leg 3 — the tuning selection rule. **Known metric; the head-to-head is the part worth reading.**

Multi-start tuning produces many candidate parameter sets. The standard choice is the
one with the lowest `⟨H⟩` — which is what `QAOASolver` applies. **Selecting on total
feasible mass instead picks a better circuit.**

**This is close to published work.** The quantity has a name — *in-constraint
probability*, the proportion of feasible samples — and the same failure modes are
already documented in the literature: a penalty too large gives "a nearly uniform
mixture of feasible states", too small gives low in-constraint probability. Published
work uses it as a lower-bound constraint *inside* the optimizer. **Using it as a
post-hoc selector among restarts, benchmarked head-to-head against `⟨H⟩`, is the only
part I did not find** — and it is a small step from what is published.

What is measured here:

> At reps=2 on the pre-designated primary instance, a point above the bar **exists**
> — one tuning of 40 reaches 0.07952 against 0.078125. **`⟨H⟩` ranks that tuning
> 12th of 40**, and the rule returns one at 0.07546, **3.4% short**, which is the
> entire remaining gap. `⟨H⟩` and mass correlate at **−0.918**: it is not a broken
> proxy, it works through the bulk and decouples exactly where the decision is made.
> — [`results/basin-structure-reps2.md`](results/basin-structure-reps2.md)

Selecting on feasible mass picks the **argmax** tuning in **9 of 9** sound
reproducible cells ([`results/selection-rule.md`](results/selection-rule.md)), in
**12 of 12** on three fresh instances
([`results/selection-rule-replication.md`](results/selection-rule-replication.md)),
and in **4 of 4** sizes from 8 to 14 qubits
([`results/selection-rule-scaling.md`](results/selection-rule-scaling.md)) — where the
alternative of selecting on *measured optimal mass* stops working, because at 14
qubits the optimum is recoverable from a 4,096-shot sample in only 7 of 20 tunings.

**The limits**, all recorded in those write-ups and pinned by tests: the
discriminating comparison rests on **two hard instances out of six seeds**; the
margin over `⟨H⟩` is a median 5.0% and only matters at the bar; and the largest size
tested is still enumerable, so it probes the regime by *shot budget*, not by
intractability.

---

## Scope, and what this is not

- **One problem family** — residential battery scheduling under a two-tier tariff —
  at T = 3 to 7, 6 to 14 qubits, `checkpoint(3)`, reps ∈ {1, 2}.
- **Not a claim of quantum advantage.** `dp_solve` returns the exact optimum for
  every instance here in microseconds. These are claims about *how to run the
  algorithm*, not about beating a classical solver.
- **No hardware claim for legs 2 and 3.** Three runs on `ibm_fez` (146 QPU-seconds)
  support the device-degradation result in
  [`results/slack-free-encoding.md`](results/slack-free-encoding.md). A reps=2
  `cp3` circuit has since flown, on 2026-08-25
  ([`results/hardware-run-depth.md`](results/hardware-run-depth.md)), but it
  measured **depth**, not the penalty weight or the selection rule; legs 2 and 3
  remain simulator findings.

## How the claims are supported

Every study here was **pre-registered before it ran** (`docs/plans/` then
`docs/results/`), and the sweep scripts refuse to run against an uncommitted plan, so
the ordering is checkable in `git log` rather than asserted. **Four registered
predictions were falsified and are reported as such.** Every number in every write-up
is pinned by a test to the artifact that produced it, and the limiting sentences —
the caveats — are pinned too, because a document that keeps its findings and loses
its qualifications has every number right and the conclusion wrong. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) §Conventions.

## Limits of the prior-art scan

Roughly a dozen searches on 2026-08-24 across encoding, penalty, mixer and
application vocabularies, plus a 2026 domain survey. **No citation-graph traversal
was done.** The leg-1 novelty claim rests on not finding something, which is weaker
evidence than finding it; the encoding literature is large and moves quickly. If you
know of a slack-free encoding with a proved feasibility guarantee for a sequential
running-sum constraint, that claim should come down, and the issue tracker is the
place to say so.
