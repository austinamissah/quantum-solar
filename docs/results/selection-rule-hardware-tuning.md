# The selection rule, replicated incidentally while tuning hardware circuits

> **This was not pre-registered.** Every other study under `docs/results/` was
> registered before it ran and can be checked against `git log`; this one was not,
> because nobody set out to measure it. It fell out of tuning the circuits for
> [`../plans/hardware-run-depth.md`](../plans/hardware-run-depth.md). An
> unregistered result is weaker evidence than a registered one — there was no
> stated prediction to fail — and it is reported here as a corroborating
> observation rather than as a study.

No QPU and no sampling: exact statevector throughout. The numbers below are all
derivable from [`hardware_params_depth.json`](hardware_params_depth.json), which
records every restart, and `tests/test_selection_tuning_tables.py` pins them to it.

**Instance:** T=3, **seed 0**, `checkpoint(3)`, α = 0.021, m = 6. The registered
selection-rule work used seed 1, so this is a fresh instance for the claim.

## What was measured

One pool of **40 restarts** per arm — the candidates a single
`QAOASolver(n_starts=40, seed=1234)` run draws — with both selection rules applied
to that same pool. Selecting on feasible mass is leg 3's rule; selecting on lowest
⟨H⟩ is what `QAOASolver` does internally.

| arm | rule | ⟨H⟩ | optimal mass | feasible mass | rank by mass |
|---|---|---:|---:|---:|---:|
| reps=1 | lowest ⟨H⟩ | 0.461316 | 0.044852 | 0.278502 | 13/40 |
| reps=1 | feasible mass | 0.465339 | 0.046249 | 0.287354 | 1/40 |
| reps=2 | lowest ⟨H⟩ | 0.328999 | 0.083772 | 0.428888 | 2/40 |
| reps=2 | feasible mass | 0.336258 | 0.089250 | 0.453128 | 1/40 |

Selecting on mass gains **3.18%** feasible mass at reps=1 and **5.65%** at reps=2
(optimal mass **3.11%** and **6.54%**). In both arms the rule takes a **worse ⟨H⟩**
to get there, which is the whole mechanism: ⟨H⟩ is a proxy, and the restart that
minimizes it is not the restart that concentrates mass.

⟨H⟩ and feasible mass correlate at **−0.9681** (reps=1) and **−0.9554** (reps=2).
The registered work reports **−0.918** and describes the proxy as working through
the bulk and decoupling where the decision is made. Both figures here are
consistent with that: a strong correlation overall, and the top-ranked point still
wrong.

**Against the published margin.** `selection-rule.md` and its replications report a
median margin of **5.0%** for the rule. The reps=2 margin here is 5.65%, on an
instance none of them used.

## The corollary: searching the proxy harder made the circuit worse

This is how the effect was noticed, and it is a sharper statement than the ranking
result.

Raising the ⟨H⟩ restart budget from 5 to 40 and changing nothing else moved the
reps=2 arm from ⟨H⟩ = 0.336258 to 0.328999 — a better ⟨H⟩, as more search
should give — and feasible mass from 0.453128 **down** to 0.428888. The 5-start
search had landed on the mass-best restart by luck; the larger ⟨H⟩ search found a
lower-⟨H⟩ point and walked off it.

So on this instance more optimization of the standard objective is not merely
inefficient but **counterproductive** for the quantity that matters, and the damage
grows with the search budget rather than shrinking. Both circuits it names appear
in the table above and in the artifact.

Unlike the table, this comparison is **not pinned to a committed artifact** — the
5-start params file was overwritten by the 40-start one. It reproduces with:

```
python scripts/experiment_hardware.py optimize --plan depth --n-starts 5  --overwrite
python scripts/experiment_hardware.py optimize --plan depth --n-starts 40 --overwrite
```

The reps=1 arm is unchanged between the two budgets under lowest ⟨H⟩, which is what
a single-basin landscape implies (`basin-structure.md`) and is a small independent
check that the two runs differ only where they should.

## What this does and does not add

- It is a **replication on a fresh instance** of a finding whose registered
  evidence was seed 1: the rule wins, by a margin in the same range, in the same
  direction, by accepting a worse proxy value.
- It is **one instance, one α, one encoding, two depths**. It establishes nothing
  about the size of the effect in general.
- It was **not pre-registered**, so it cannot be cited as a test the rule passed;
  it is an observation that the rule behaves as described where it was applied.
- The **pool differs** from the registered studies' design. They drew 40 tunings as
  independent runs; this pool is the 40 restarts inside one solver call. That is
  deliberate — it is the candidate set the default rule actually chooses between,
  so the head-to-head is like-for-like — but it is not the same sampling scheme,
  and the two are not interchangeable. An earlier version of this measurement used
  40 independent single-start solves and produced a **worse pool** whose argmax
  (feasible mass 0.4227 at reps=2) was beaten by both rules on the pool above.
