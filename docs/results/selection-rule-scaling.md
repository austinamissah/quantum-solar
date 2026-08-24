# Does the selection rule survive a size you cannot enumerate? — results

**Pre-registered:** [`../plans/selection-rule-scaling.md`](../plans/selection-rule-scaling.md),
committed at `41ae679` **before the sweep ran**. Simulator and exact computation only
— **no QPU**. 80 tunings (4 sizes × 20 seeds), ~25 min.

Instance seed 1, `checkpoint(3)`, reps=2, α\* = 0.021, `shots=4096`.

## Verdict: both predictions held

| | prediction | measured | outcome |
|---|---|---|---|
| **P1** | at T=7 the optimum is recoverable in fewer than half the tunings | **7 of 20** | **held** |
| **P2** | feasible mass ≥ `<H>` in more sizes than not | **4 wins, 0 losses** | **held** |

**The study is informative.** The plan's escape clause — that a size where no tuning
beats uniform is a choice among noise — **did not fire**: every size has tunings above
uniform, by 4.2× to 7.5×. The T=7 probe that suggested otherwise was one tuning and
was wrong about the population.

## The result

| T | qubits | best mass | best / uniform | feasible mass picks | `<H>` picks | rank `<H>` gives the best |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 8 | 0.016278 | 4.2× | **0.016278** | 0.016049 | 5 |
| 5 | 10 | 0.005626 | 5.8× | **0.005626** | 0.005459 | 4 |
| 6 | 12 | 0.001835 | 7.5× | **0.001835** | 0.001820 | 4 |
| 7 | 14 | 0.000257 | 4.2× | **0.000257** | 0.000249 | 2 |

**Feasible mass picked the argmax tuning at every size — rank 1, four for four.**
`<H>` picked it at none, ranking it 5th, 4th, 4th and 2nd. The property found at T=3
does not degrade over the range tested; it holds at 8, 10, 12 and 14 qubits.

## The mechanism the study exists to test, and it fired

The direct rule — select on measured optimal mass — needs the optimum to appear in the
sample. It does not, at size:

| T | qubits | mean identifiability | median | tunings ≥ 0.5 | best tuning |
|---:|---:|---:|---:|---:|---:|
| 4 | 8 | 1.00 | 1.00 | 20 / 20 | 1.00 |
| 5 | 10 | 0.80 | 1.00 | 16 / 20 | 1.00 |
| 6 | 12 | 0.83 | 0.97 | 15 / 20 | 1.00 |
| 7 | 14 | **0.28** | **0.10** | **7 / 20** | **0.68** |

At 14 qubits and 4,096 shots the optimum is recovered from a sample in **28%** of
draws on average, and the *best-behaved tuning in the sweep* manages only **68%**.
There is no tuning at that size on which the direct rule is reliable.

So the two rules separate exactly where the plan said they would. **Feasible mass keeps
picking the argmax at a size where the rule that beat it at T=3 can no longer be
applied.** That was the untested claim in `selection-rule.md` and it now has evidence.

## What this does not show, and the honest size of it

- **The margin is small at every size.** `<H>`'s pick is worse by 1.4%, 3.0%, 0.8% and
  3.2%. `<H>` is not catastrophic here — it simply never picks the best. That is a
  much weaker failure than at T=3 on the hard instance, where its pick **missed the
  bar entirely** and the stakes were binary. **Do not quote the T=3 stakes with these
  ranks.**
- **T=7 is still enumerable** — 16,384 states. This tests the regime **by shot
  budget**, not by intractability. A genuinely non-enumerable instance is untested and
  this is not a substitute for one.
- **Four sizes is four comparisons**, on **one instance** at **one α**, with **N=20**.
  P2 is weak by construction and was registered as such.
- **Concentration is not monotone in T** (4.2×, 5.8×, 7.5×, 4.2×), so T=4 and T=7 do
  not clear the scaled 5×-uniform bar while T=5 and T=6 do. **I cannot explain the
  shape**, and 20 tunings is thin enough that it may not be real. It is reported
  because smoothing it would be the more comfortable choice, not the right one.
- **Identifiability is not monotone either** (1.00, 0.80, 0.83, 0.28). The T=5 dip
  below T=6 is within what 20 tunings can produce by chance.

## What it changes

`selection-rule.md` closed on the caveat that feasible mass "only earns its place
where the optimum cannot be identified — and that case has not been tested". **It has
been now, and feasible mass earns it**: at 14 qubits the direct rule is unusable on
13 of 20 tunings while feasible mass still selects the best one available.

The caveat that replaces it is narrower and should be carried forward: this is a
**shot-budget** demonstration on **one instance**, and the regime that would settle it
— too large to enumerate at all — remains out of reach of this test.
