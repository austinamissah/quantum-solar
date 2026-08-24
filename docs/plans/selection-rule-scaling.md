# Pre-registration: does the selection rule survive a size you cannot enumerate?

**Status:** registered, not yet run. **Simulator and exact computation only — no QPU.**
Written **2026-08-24**.

[`selection-rule.md`](../results/selection-rule.md) found that selecting on **total
feasible mass** picks the best available tuning in every sound, reproducible cell
tested. It also recorded the reason that result may not matter: **every test was at
T=3, m=6, where all 64 states can be enumerated** — and there the *direct* rule
(select on measured optimal mass) is available and strictly better, 9 of 9 including
cells where feasible mass fails.

Feasible mass only earns its place where the optimum **cannot be identified**. That
case has not been tested. This tests it.

## The mechanism under test

The state space is `4**T`. The optimum is a **single** state at every size. So the
optimum's share of the output shrinks with T, and at a fixed shot budget there is a
size past which it is simply **not sampled** — at which point the direct rule has
nothing to select on, because it cannot tell which sampled state is optimal.

Feasible mass has no such dependence: it needs only a feasibility check on sampled
outcomes, and the feasible set grows with the space.

**Disclosed, measured before registration on one tuning per size** (seed 1, α\*,
reps=2), because it is what makes the sizes worth running at all:

| T | qubits | states | feasible | optimal mass | 5 × uniform | feasible mass |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 8 | 256 | 18 | 0.01333 | 0.01953 | 0.1852 |
| 5 | 10 | 1,024 | 46 | 0.00502 | 0.00488 | 0.1464 |
| 6 | 12 | 4,096 | 119 | 0.00132 | 0.00122 | 0.1065 |
| 7 | 14 | 16,384 | 309 | **0.00001** | 0.00031 | 0.0124 |

At T=7 that one tuning puts **0.04 expected counts** on the optimum in 4,096 shots.
**This is a single tuning per size and is not a result** — it is the reason these
sizes were chosen.

## Design, fixed here

**Instance seed 1, `checkpoint(3)`, reps=2, α\* = 0.021, T ∈ {4, 5, 6, 7}.**
**N = 20 tuning seeds** per size, `n_starts=5`, `maxiter=200`, `shots=4096`.

N=20 rather than the 40 used at T=3 is a **budget choice made in advance** (~25 min
total); it is recorded here so it cannot be presented later as anything else. It
halves the resolution on rank statistics and is why the predictions below are stated
as majorities rather than as counts.

**The bar scales with the space:** `5 / 2**m` at each size, the same "5× uniform"
definition the project uses at m=6. It is reported, not used to decide either
prediction — these predictions are about **rules**, not about clearing.

## Predictions

**P1 — the direct rule dies with size.** At the largest size tested (T=7), the true
optimum is present in a 4,096-shot sample in **fewer than half** of the 20 tunings.

*Falsified if* it is sampled in half or more.

**P2 — feasible mass does not.** Across the four sizes, selecting by feasible mass
returns a tuning whose true optimal mass is **at least as high** as the one
lowest-`<H>` returns, in **more sizes than not** (i.e. at least 3 of 4, counting ties
as neither).

*Falsified if* it wins in fewer than it loses.

Both are reported at these definitions before any other cut. **P2 is deliberately
weak** — four sizes is four comparisons, and no stronger claim is available at this
budget. Ranks and picked masses are reported per size so a reader can see how much
weight the verdict deserves.

## What would make this study uninformative, stated in advance

If QAOA's optimal mass falls **below uniform** at the larger sizes, then every tuning
there is worthless and "which tuning a rule picks" is a choice among noise. The
disclosed probe suggests this may already be happening at T=7 (0.00001 against a
uniform of 0.00006). **If that holds at N=20, P2's result at that size means nothing
and will be reported as meaningless rather than as a win or a loss.** The honest
outcome may be that the interesting regime — large enough not to enumerate, small
enough for QAOA to still concentrate — does not exist for this problem family at
reps=2.

## Procedure

1. `python scripts/selection_rule_scaling.py` — sweeps the four sizes, writes
   `docs/results/selection_rule_scaling.{csv,json}`. Refuses to run unless this plan
   is committed and clean.
2. Results to `docs/results/selection-rule-scaling.md`, both predictions at the pinned
   definitions first.

## Limitations, recorded in advance

- **One instance and one α.** Instance-dependence is documented in this project and
  is not sampled here at all.
- **N=20**, half the resolution of the studies this extends.
- **T=7 is still enumerable** — 16,384 states — so identifiability is *measured*
  rather than *assumed*. This tests the regime by shot budget, not by true
  intractability, and a reader should not read it as the latter.
- **Nothing here is a hardware claim**, and nothing here revisits
  `optimizer-budget-study.md`, whose verdict concerns arms scored on their means.
