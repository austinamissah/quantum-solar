# Does the selection rule replicate on fresh instances? — results

**Pre-registered:** [`../plans/selection-rule-replication.md`](../plans/selection-rule-replication.md),
committed at `b2cc191` **before the sweeps ran**. Simulator and exact computation only
— **no QPU**. 1,200 tunings (3 instances × 10 α × 40 seeds), ~2¼ h.

Instances **4, 5 and 6** — seeds never used in any prior study here. T=3,
`checkpoint(3)`, reps=2, N=40, bar `5 / 2**6` = **0.078125**.

## Verdict: all three held, and P3 was estimable after all

| | prediction | measured | outcome |
|---|---|---|---|
| **P1** | feasible mass picks the argmax in ≥80% of band cells | **12 of 12 (100%)** | **held** |
| **P2** | it beats `<H>` in strictly more cells than it loses | **12 wins, 0 losses** | **held** |
| **P3** | where `<H>` misses the bar but something clears, it clears in >half | **3 of 3** | **held** |

**P3 is the one that mattered, and the plan expected it might be empty.** It is not.
One of the three fresh instances is hard, and on it the two rules separate exactly as
they did on instance 1.

## The instance that made the study work

| instance | band cells | best mass | `<H>` misses the bar in |
|---:|---:|---|---:|
| 4 | 4 | 0.0949 – 0.1334 | **0 of 4** |
| 5 | 5 | 0.0932 – 0.1270 | **0 of 5** |
| **6** | 3 | **0.0787 – 0.0823** | **3 of 3** |

Instances 4 and 5 are **easy** — every band cell clears under both rules, exactly the
uninformative pattern instances 2 and 3 showed. They contribute to P1 and P2 and say
nothing about which rule to prefer.

**Instance 6 is hard**, with best masses sitting right on the bar, and there `<H>`'s
pick misses in **every** cell while feasible mass clears in every one:

| cell | `<H>` picks | misses by | feasible mass picks | clears by |
|---|---:|---:|---:|---:|
| instance 6, α = 0.0209 | 0.07496 | 0.00316 | **0.08084** | 0.00272 |
| instance 6, α = 0.021 | 0.07501 | 0.00311 | **0.08225** | 0.00413 |
| instance 6, α = 0.030 | 0.07510 | 0.00302 | **0.07875** | 0.00062 |

## What this changes

`selection-rule.md`'s central weakness was that **the only comparison that
discriminated between the two rules came from instance 1 — the instance the rules were
fitted on.** That is no longer true. Instance 6 is a fresh seed, chosen before it was
inspected, and it reproduces the discrimination cell for cell.

The finding is therefore no longer fitted to its discovery instance.

## What it still does not establish

- **P3's three cells all come from one instance.** They are three α rungs of instance
  6, not three independent tests, and they should be counted as roughly one
  independent observation. **The registered criterion was met; the effective sample is
  smaller than the number 3 suggests.**
- **Hard instances are rare in this family.** Of six seeds now swept at reps=2
  (1, 2, 3, 4, 5, 6), **two** are hard — instance 1 and instance 6. A rule comparison
  that needs the hard case will keep spending most of its budget on instances that
  cannot supply one, and future work should consider constructing hard instances
  rather than sampling for them.
- **The tightest margin is thin.** At instance 6, α = 0.030, feasible mass clears
  by **0.00062**. That is a real clearance under exact computation, but it is not a
  margin that would survive a modest shot budget, and nothing here says it would.
- **T=3, reps=2, one α ladder, one encoding.** The scaling behavior is covered
  separately in [`selection-rule-scaling.md`](selection-rule-scaling.md) and is not
  re-established here.
- **The rules were not changed**, deliberately. Introducing a new candidate after
  seeing three more instances would be the fitting problem again.

## Margins, for calibration

Across all 12 band cells, feasible mass's pick beats `<H>`'s by a **median of 5.0%**
(minimum 0.8%, maximum 8.8%) in optimal mass. On the easy instances that difference
changes nothing, because both picks clear. **On the hard instance it is the difference
between clearing the bar and missing it**, which is why the median margin is the wrong
number to quote on its own.
