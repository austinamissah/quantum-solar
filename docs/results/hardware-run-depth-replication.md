# Does the depth result replicate? — results

**Pre-registered:** [`../plans/hardware-run-depth-replication.md`](../plans/hardware-run-depth-replication.md),
committed at `5671e5f` **before submission**. One job `da765hk6l22c73dn5et0` on
`ibm_fez`, four circuits, **6.0 QPU seconds**. Calibration snapshot: median 2Q gate
error **0.0026924**, median readout error **0.0097656**, dated
2026-08-25 23:06:23-04:00, about 36 minutes after the first run's.

**The circuits are identical to the first run's** — the same committed angles from
`hardware_params_depth.json`, not re-tuned. The calibration window is the only
thing that moved.

## Verdict: the primary REPLICATES, the mechanism does NOT

| | registered | measured | outcome |
|---|---|---|---|
| primary: Δ hardware optimal mass > 0.00765, same sign | positive, past threshold | **+0.03027** | **REPLICATED** |
| secondary: the two arms' retention agree within 0.02 **in each replicate** | agreement | **0.063** in r1, 0.017 in r2 | **FALSIFIED** |

The plan wrote the reading for this case before the run:

> if the difference replicates but retention does *not* agree between arms, the
> result stands and its stated mechanism does not. That would be reported as the
> mechanism being unsupported, not quietly dropped.

That is what happened, and that is what this document does.

## The primary result across both runs

| | replicate 1 | replicate 2 |
|---|---:|---:|
| run 1, 2026-08-25 | +0.03613 | +0.03320 |
| **run 2, 2026-08-26** | **+0.03027** | **+0.03394** |

Four measurements of the same quantity across two calibration windows, all
positive, all past the 0.00765 threshold, spanning **+0.03027 to +0.03613**. The
between-run difference on replicate 1 is **0.00586**, smaller than the threshold
itself. Bootstrap 95% CI this run: [+0.02051, +0.04004], excluding zero.

**Depth helps on this instance, on this device, across two windows.** That is what
the first run's caveat asked for and it is now supplied.

## The circuits

| circuit | 2Q | hw optimal mass | hw feasible mass | TVD(ideal,hw) | TVD(ideal,unif) | normalized |
|---|---:|---:|---:|---:|---:|---:|
| `cp3` reps=1 r1 | 46 | 0.03857 | 0.25195 | 0.1053 | 0.3945 | **0.2670** |
| `cp3` reps=2 r1 | 112 | 0.06885 | 0.28247 | 0.2389 | 0.5211 | **0.4585** |
| `cp3` reps=1 r2 | 46 | 0.03809 | 0.26611 | 0.1005 | 0.3945 | 0.2547 |
| `cp3` reps=2 r2 | 112 | 0.07202 | 0.28662 | 0.2318 | 0.5211 | 0.4449 |

Secondary statistic, feasible mass: **+0.03052** [+0.01147, +0.04932] on replicate
1 and +0.02051 [+0.00122, +0.03979] on replicate 2. Both positive and both
intervals exclude zero, but both are far below the first run's +0.07959 and
+0.08276. **The secondary is much less stable between runs than the primary**, and
nothing here should be built on it.

## Why the mechanism does not survive

The first run reported that both depths retained the **same fraction** of their
ideal optimal mass, and used that to explain the falsification. Across both runs:

| | reps=1 retention | reps=2 retention | gap |
|---|---:|---:|---:|
| run 1 r1 | 0.850 | 0.845 | 0.005 |
| run 1 r2 | 0.750 | 0.760 | 0.011 |
| **run 2 r1** | **0.834** | **0.771** | **0.063** |
| run 2 r2 | 0.824 | 0.807 | 0.017 |

Normalized TVD shows it more plainly. In run 1 the figure was flat across the gate
increase, 0.3114 against 0.2986. **In run 2 it is not flat at all: 0.2670 against
0.4585.** The deeper circuit is clearly the more degraded one this time, across the
same 2.4x gate increase, with the same angles.

So the equal-retention observation was **substantially a property of that job**, not
of these circuits. The reps=2 arm's retention alone moves from 0.845 to 0.771
between windows 36 minutes apart, a swing of 0.074 that is larger than the entire
gap the first run's mechanism claim rested on.

**What survives.** The deeper circuit's ideal advantage is 1.93x, and that is large
enough for it to finish ahead even when it degrades more: 0.771 x 0.08925 = 0.0688
against 0.834 x 0.04625 = 0.0386. **That, not equal retention, is why depth wins
here.** The correct statement is the weaker one: the deeper circuit degrades more,
by an amount that varies between runs, and by less than its ideal advantage.

**The noise model is still overpredicting.** At ε = 0.457 and 0.774 it sits above
both measured normalized figures in both runs. The third same-direction miss
recorded in [`../LESSONS.md`](../LESSONS.md) §3 stands; this run does not soften it.

## Limits

- **Two runs is not a variance estimate.** The 1-df χ² upper factor of 31.9 that
  [`hardware-run-spread.md`](hardware-run-spread.md) records still applies. The
  depth effect is now *replicated*, not *characterized*.
- **The two windows are 36 minutes apart**, same device, same day, adjacent queue
  positions. That is a weaker test of between-run stability than two runs weeks
  apart would be, and the retention swing observed here is evidence that a longer
  separation could move things further.
- **Same device, instance, encoding, weight and angles.** Only the window moved.
  Nothing generalizes past `ibm_fez` on this problem.
- **Legs 2 and 3 remain simulator findings**, unchanged.
