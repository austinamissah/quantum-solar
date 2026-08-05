# Pre-registration: reopening the encoding gate with iterations-per-restart as a rung

Written **before** any run. Every threshold, arm, seed and analysis rule below is
fixed here. Supersedes nothing: this **reopens** a question closed in
[`hardware-run-encoding.md`](hardware-run-encoding.md), it does not revise its
result.

## Why it is being reopened

That question was closed without an answer because no circuit cleared a
pre-registered ideal-mass gate:

> at the a-priori penalty weight, reps=2 ideal mass saturated at ~0.075 against a
> required 0.078125, and all twelve pre-registered optimizer arms failed to close
> it.

[`eval-censoring.md`](../results/eval-censoring.md) showed that "saturated" was
the **budget**, not a ceiling. Every COBYLA arm in that study ran at ≥99% of its
own evaluation cap (`cobyla-5` ~1,000 of 5×200; `cobyla-25` ~4,950 of 25×200;
`cobyla-50` ~9,900 of 50×200), and the ladder varied `n_starts` only —
**`maxiter` was fixed at 200 on every rung.** In a separate paired test, raising
`maxiter` 5× moved capped cells' ideal mass by a median of 100%.

So ~0.075 is a lower bound and the shortfall against 0.078125 is an upper bound.
The gap that closed the question may not exist.

## The confound this design fixes

`cobyla-5/25/50` changed **two things at once**: the allocation of budget (more
restarts) *and* the total budget (5× and 10× more evaluations). It therefore
cannot distinguish "more budget does not help" from "budget spent on restarts does
not help". The distinction matters because restarts and iterations do different
things: more restarts sample more basins, more iterations descend further into the
one you are in.

Two arm families, run together:

**(A) Iterations ladder** — `n_starts` fixed at 5, `maxiter` varied. Isolates the
axis never tested. `s5_m200` is *exactly* the original `cobyla-5`.

**(B) Matched-cap allocation** — evaluation cap fixed at 10,000, split differently.
Isolates allocation from budget. `s50_m200` is *exactly* the original `cobyla-50`.

| arm | n_starts | maxiter | eval cap | family | note |
|---|---:|---:|---:|---|---|
| `s5_m200` | 5 | 200 | 1,000 | A | = original `cobyla-5` |
| `s5_m1000` | 5 | 1,000 | 5,000 | A | |
| `s5_m5000` | 5 | 5,000 | 25,000 | A | |
| `s50_m200` | 50 | 200 | 10,000 | B | = original `cobyla-50` |
| `s10_m1000` | 10 | 1,000 | 10,000 | B | |
| `s2_m5000` | 2 | 5,000 | 10,000 | B | |

Two arms reproduce original rungs by construction. **If they do not reproduce
their original numbers, the harness has drifted and the run is void** — that check
comes before any comparison.

## Fixed, and not to be re-chosen

Carried over unchanged from `optimizer-study.md`. **The bar does not move and the
primary instance is not reselected**, whatever the result.

- Instance: synthetic `T=3`, **seed 1**, designated PRIMARY in advance.
- `ALPHAS = (0.021, 0.030)`; both reported; the gate applies per α.
- Encoding `checkpoint(3)` (m=6), `reps=2`.
- **BAR = 5/2⁶ = 0.078125** ideal optimal mass.
- Tuning seeds 101–110 (N=10).
- **PASS** = mean mass ≥ BAR. **RELIABLE** = clears on ≥ 8/10 tuning seeds.
- Objective is the shot-based `<H>`; mass and `<H>` are reported at the exact
  statevector. Same `Objective` class as the original study, reused rather than
  reimplemented, so the arms are comparable by construction.

Instances 2 and 3 may be run as robustness. They are **secondary and cannot change
the primary verdict** — that rule is what made the original study's
instance-dependence finding a finding rather than a selection effect.

## Every analysis choice, pinned

The defect this project keeps repeating is pinning the threshold and leaving the
*population* loose ([LESSONS §5](../LESSONS.md)). In the immediately preceding
experiment an unpinned classifier flipped a verdict from 100% to 8.0%. So:

1. **"Censored"** means `actual_evals == n_starts × maxiter` exactly. Reported per
   arm as a count out of 10. It detects **full** censoring only; an arm below its
   cap may still contain capped restarts. Where the distinction could matter the
   one-sidedness is stated, never silently.
2. **"Budget-limited"** means the arm's actual spend rose when its cap rose,
   comparing `s5_m200 → s5_m1000 → s5_m5000` on the same tuning seed. This is the
   operational definition, and it is the one used for any claim about whether
   budget mattered.
3. **Primary comparison** is `s5_m1000` and `s5_m5000` against `s5_m200`, paired on
   tuning seed. Paired, because tuning seed is the dominant variance source.
4. **Mean** = arithmetic mean over the 10 tuning seeds. **sd** = sample sd
   (`ddof=1`). Fractions are exact counts, never rounded before comparison.
5. No arm is dropped for any reason. Every configured run is reported, failures
   included.

## Verdicts, and the check that each is reachable

Per (instance, α):

| condition | verdict |
|---|---|
| some arm PASS+RELIABLE | **REOPENED-AND-CLEARED** — the gate closes on budget; the original closure was an artifact |
| some arm PASS, none RELIABLE | **PARTIAL** — the bar is reachable but not reliably; same status the original reached |
| no arm PASS | **CONFIRMED-CLOSED** — the shortfall is real and survives 25× the original per-restart budget |

**Reachability** (LESSONS §4 — a test that cannot return one of its own verdicts
is not a test). All three are reachable: the original study observed a maximum
single-seed mass of **0.0879** on this instance, which clears 0.078125, so
clearing is possible; and it observed 0/10 clearing at `cobyla-5`, so failing is
possible. Unlike the earlier n=5 spread test, no verdict is arithmetically
excluded.

**Secondary, pre-specified:** does mass increase monotonically with *actual*
evaluations spent, pooled across arms and paired by tuning seed? A budget effect
should be monotone; a non-monotone result would indicate the extra evaluations are
finding different basins rather than descending further, which is a different
mechanism and would be reported as such.

## Direction of the risk

Unlike the censoring experiment, this one can cut either way, and that is stated
in advance:

- **CONFIRMED-CLOSED strengthens the original conclusion** — the hardware question
  was closed correctly and the qualification added on 2026-08-04 was cautionary
  rather than consequential.
- **REOPENED-AND-CLEARED means a published closure was wrong**, and
  `hardware-run-encoding.md` needs a retraction in place rather than a
  qualification.

No result here makes the α\* penalty-weight finding weaker; that is derived a
priori and does not depend on any optimizer.

## Cost

120 runs (6 arms × 10 seeds × 2 α). Caps total ~1.4 M evaluations worst case at
~7.6 ms each; COBYLA converging early will cut that substantially, and **the
actual-vs-cap spend is itself a reported result**. Simulator only — **no quantum
time is spent**, so this is cheap in the resource that matters.
