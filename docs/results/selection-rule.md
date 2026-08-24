# A selection rule that finds the clearing basin — results

**Pre-registered:** [`../plans/selection-rule.md`](../plans/selection-rule.md),
committed at `67acf0c` **before the held-out sweeps ran**. Simulator and exact
computation only — **no QPU**.

**Run:** two fresh reps=2 sweeps (`--instance 2`, `--instance 3`, 400 tunings each),
then `python scripts/selection_rule_study.py` → `selection_rule.json`. The evaluation
**excludes the discovery cell by construction** and asserts the exclusion.

## Verdict: both predictions held, and P2 held for a reason that does not flatter it

| | prediction | measured | outcome |
|---|---|---|---|
| **P1** | feasible mass beats `<H>` in strictly more held-out cells than it loses | **7 wins, 2 losses, 6 ties** | **held** |
| **P2** | feasible mass finds a clearing tuning in more than half the cells that have one | **7 of 9** | **held** |

**P2 held and proves almost nothing**, which is worth saying before anything else:
**`<H>` also scored 7 of 9.** The two held-out instances clear easily — best masses of
0.08 to 0.14 against a 0.078125 bar — so on them almost any sane rule clears, and P2
does not discriminate. It was registered as a floor and it behaved like one.

The discrimination is elsewhere, and it is sharp.

## The result: in the band you would actually operate in, feasible mass picks the argmax

Restricting to cells that are both **sound** (the QUBO's minimiser is feasible) and
**reproducible** (α ≤ 0.03, before basin count runs away):

| pool | cells | feasible mass clears | `<H>` clears | feasible mass picked the *best available* tuning |
|---|---:|---:|---:|---:|
| held-out (instances 2, 3) | 7 | 7 | 7 | **7 / 7** |
| instance 1, other sound rungs *(weaker)* | 2 | **2** | **0** | **2 / 2** |

**Feasible mass did not merely beat `<H>` — it selected the single best tuning in the
cell, in all nine.** That is a stronger property than either prediction asked for.

**And the two pools say different things.** On instances 2 and 3 both rules clear
everything, because those instances are easy. **On instance 1 — the pre-designated
primary, the hard one — feasible mass clears 2 of 2 and `<H>` clears 0 of 2.** That is
the comparison the whole question was about, and it is **weaker evidence by design**:
instance 1 is the instance the candidate rules were chosen on, which is exactly why
its α\* cell is excluded and why these two rungs are reported apart.

## Why it works, and it is not subtle

The penalty weight exists to move probability onto the feasible subspace. Selecting on
how much got there is selecting on whether the penalty did its job. `<H>` mixes that
with the objective, and at reps=2 the mixture is dominated by the penalty term — which
is `LESSONS` §1's overshoot showing up in the selection step rather than in solution
quality.

## Where both rules fail completely

At α ≥ 0.06 **both** collapse. Best available mass is 0.07 to 0.14; both rules return
**0.0000 to 0.0145**. The two cells P1 records as *losses* are here:

| cell | feasible mass | `<H>` | best available |
|---|---:|---:|---:|
| instance 3, α = 0.1 | 0.000144 | 0.000147 | 0.0733 |
| instance 3, α = 0.3 | 0.000000 | 0.000000 | 0.1377 |

Losing by 3 × 10⁻⁶ while both rules sit 500× short of the target is not a loss in any
sense that matters, and it is not a reason to prefer `<H>`. **Feasible mass is not a
fix for the irreproducible regime** — nothing tested here is. That regime has 20 to 37
basins and should not be operated in, which `basin-structure-reps2.md` already says.

## The direct rule, and what it costs

Selecting on **mass at the cheapest feasible sampled state** — which *is* measured
optimal mass, since decoding 4,096 shots and taking the cheapest feasible outcome
recovers the true optimum in 40 of 40 tunings — finds a clearing tuning in **9 of 9**
cells, including the high-α ones where every shape rule fails. Mean selected mass
**0.0894** against 0.0448 for the best shape rule.

**It is not free, and on the hard instance it is not reliable at the budget this
project uses.** On instance 1 at α\* the best tuning leads the runner-up by 0.00162
against a shot-noise sd of 0.00424 at 4,096 shots. Selection by measured mass picks
the clearing tuning **26%** of the time there, rising to 46% at 16,384, 73% at 65,536
and **98% at 262,144** — **64× the shots** for a reliable answer.

So there are two answers depending on what is scarce. **Shots cheap: select on
measured optimal mass.** **Shots dear, or the instance too large to enumerate: select
on feasible mass**, which needs only a feasibility check.

## What this does not establish

- **`feasible_mass` and `lowest_participation` pick the same tuning in 14 of 15
  held-out cells.** They are near-duplicates, so the table's agreement between them is
  one result, not two.
- **Seven observables were tried on 40 points.** A clean out-of-sample result makes
  feasible mass *a* rule that works on these three instances at this depth — not *the*
  rule, and not one demonstrated at a size where the optimum cannot be enumerated,
  which is the only size where the distinction pays.
- **Two held-out instances is a small sample**, and both turned out easy. The one
  discriminating comparison comes from the instance the rules were fitted on.
- **`optimizer-budget-study.md` is untouched.** Its verdict concerns *arms* scored on
  their **means**; this is about selecting among tunings after the fact. No arm was
  introduced and no budget was varied.
- **No hardware claim.** No reps=2 `cp3` circuit has ever been submitted.

## What it changes

`basin-structure-reps2.md` closed with the open question *"is there a selection rule
that finds the clearing basin without already knowing the answer?"* — and answered it
only negatively, for `<H>`.

**There is one.** On every sound, reproducible cell tested it picks the best tuning
available, including both cells on the hard instance where `<H>` picks nothing that
clears. The obstacle identified at reps=2 was **selection**, and selection is fixable
— with a rule that was already sitting in the encoding's own design.
