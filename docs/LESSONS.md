# What went wrong, and what it cost

This is a field report from a small quantum-computing project: scheduling a home
battery against time-of-use electricity prices, formulated as a QUBO and solved
with QAOA on IBM hardware. You do not need to have read the rest of this repo.

**The mistakes are the content.** Most write-ups present a clean result and hide
the detours. The detours are where the transferable knowledge is, so they are the
structure here. Every lesson comes with the number it cost, because a lesson
without a number does not transfer — "be careful with penalty weights" is
forgettable; "our penalty weight was 48× too large and made the objective
invisible" is not.

Assumed background: a little linear algebra, a little probability. Terms are
explained as they appear.

---

## 1. The penalty weight was 48× too large, and it broke everything downstream

**The setup.** A QUBO ("quadratic unconstrained binary optimization") can only
minimize one number. Real problems have constraints — a battery cannot hold more
than 10 kWh, cannot end the day emptier than it started. The standard trick is to
fold each constraint into the objective as a *penalty*: add a large term that is
zero when the constraint holds and positive when it is violated. Pick the penalty
weight large enough and the optimizer avoids violations on its own.

**What we did.** We sized penalties at ~10× the objective's scale, a common rule
of thumb. It works for a *classical* solver: any infeasible solution loses
outright, so the optimum is correct.

**Why it broke QAOA.** QAOA does not find the minimum. It prepares a quantum
state and minimizes the *expectation value* `⟨H⟩` — an average over everything the
state contains. With penalties 48× the objective's span, `⟨H⟩` is almost entirely
penalty. The cost we actually cared about was a rounding error inside it.

The optimizer did exactly what we asked and nothing we wanted:

| | reps=1 | reps=2 |
|---|---:|---:|
| achieved `⟨H⟩` (lower is better) | 16.08 | **1.14** |
| probability on the *optimal* schedule | 0.045 | **0.0002** |
| probability on *any feasible* schedule | 0.29 | **0.94** |

The deeper circuit was **14× better** at the job it was given and **200× worse** at
the job we wanted. It found the feasible region and stopped caring about price.

**The fix, which generalizes.** The right weight is derivable before running
anything:

> **α\* = (objective span across feasible solutions) / (penalty scale)**

For us, 0.3095 / 14.81 = **0.0209**. Below it the surrogate's optimum stops being
the true optimum; at or above it, exact on 200 test instances (61% at α = 0.010,
6% at 0.005, 1.5% at 0.003 — a cliff, not a slope). Rescaling moved reps=2's
optimal-state probability by **440×** with the encoding and the optimizer
untouched.

**If you take one thing from this document, take this:** for any constrained
problem you hand to a variational quantum algorithm, compute the ratio between
your constraint penalties and the spread of your actual objective. If it is much
above 1, the algorithm is not optimizing what you think.

### The same mistake, one level down

We twice declared an *encoding* useless when the *weight* was the problem. One
candidate lost 100% of the battery's value at the default weight — apparently
catastrophic. Swept across weights, it lost **28.79%**. Still not competitive, but
not catastrophic, and the earlier verdict was an artifact.

**You cannot rule out a design by testing it at one arbitrary value of a free
parameter.** If something has a knob, a single reading tells you about that knob's
setting, not about the thing.

---

## 2. We spent the first phase optimizing the wrong resource

Everyone counts qubits. Qubits are how quantum computers are advertised, and our
encoding was spending most of them on bookkeeping — extra "slack" variables used
to express an inequality. We designed a cleverer encoding and cut a 6-slot problem
from **22 qubits to 12**.

Then we looked at the data from a run that had already happened:

| circuit | qubits | 2-qubit gates | measured degradation |
|---|---:|---:|---:|
| A | 6 | 37 | 0.119 |
| B | 6 | 77 | 0.203 |
| C | 10 | 124 | 0.383 |
| D | 10 | 290 | 0.459 |

Degradation tracks **gate count**, monotonically, across a 7.8× range. Qubit count
takes two values and explains nothing — circuits A and B have identical qubit
counts and differ by 71% in degradation.

Gates matter because each two-qubit gate is a physical operation with an error
rate (~0.3–1% on current hardware), and errors compound multiplicatively. A qubit
that sits idle costs you comparatively little; a gate costs you every time.

**What this changed.** The 6-slot problem we had been targeting needs ~269 gates
even with the improved encoding — worse than circuit D above, which had produced
essentially no usable signal. **No encoding makes it submittable.** We had spent a
phase optimizing a resource that was not the binding constraint.

**Lesson: find out what actually limits you before optimizing anything.** Fifteen
minutes with the existing data would have reordered the whole project.

---

## 3. Check your metric is measurable before you spend anything

Of four circuits in an earlier hardware run, **three had a target signal below the
level of random guessing** — not because the hardware was bad, but because the
*ideal, noiseless* circuit had almost no signal to begin with. One expected
**0.4 counts out of 4096**. You cannot measure that. No amount of hardware
improvement would have helped, because the shortfall was in the circuit, not the
device.

Here is the sharpest single example, from a simulator sweep:

> One cell had a true optimal-state probability of **7×10⁻⁶** and sampled
> **0 counts in 4096** — an expectation of **0.03 counts**. You would need roughly
> **143,000 shots** to expect one. The same cell after the weight fix: probability
> 0.0152, **78 counts**.

The recorded value was "0" in both a case where the truth was 10⁻⁶ and cases where
it was 10⁻³. The metric was not noisy; it was **three orders of magnitude below its
own resolution**, and reported a number anyway.

This ruined a figure. Our scaling chart showed optimal-state probability declining
with problem size — the headline trend. At the two largest sizes it was **exactly
zero in all eighteen cells**. The "trend" at those sizes was the metric bottoming
out. That is a *separate* defect from the weight bug: it was present at both
weights and would not have been fixed by fixing the weight.

**The fix costs nothing.** In simulation the exact probability is available from
the statevector directly — no sampling, no floor, one extra computation. We had
been sampling a simulator, which is like rolling dice to estimate a number
printed on the box.

**Then the fix itself failed, silently, in the same shape.** We implemented that
exact-probability column with the library's obvious call — build the circuit, ask
for its statevector. The library realizes the circuit's cost layer by
**exponentiating a 2ⁿ × 2ⁿ matrix**, which is fine at 6 qubits and dies of
`MemoryError` at 14. The column had **never produced a value at the sizes it was
added for**; the sweep ran for hours and died at the same place every time.

The expensive object was never the statevector — 2¹⁸ amplitudes is 4 MB — it was
the operator the library built on the way there. Written directly (the cost
Hamiltonian is diagonal, so it is one elementwise multiply and one rotation per
qubit) it agrees to **3×10⁻¹⁶** and does 22 qubits in five seconds.

**Two lessons, and the second is the one we keep relearning.** A metric can be
unmeasurable because it is below your resolution *or* because the code computing
it cannot reach your problem size — check both. And a fix prescribed in a
retrospective is not a fix until something runs it at full scale: this one was
written down as the lesson from §3 and shipped broken.

**Before you spend anything, compute what your metric will read if your hypothesis
is true.** If the answer is smaller than your resolution, you are not going to
learn anything, and you should find that out for free.

### The same trap at the other end: a number sitting on its ceiling

The floor case above reports a value that is below its own resolution. The ceiling
case reports a value that is **the limit you imposed**, and it is harder to see
because the number looks perfectly reasonable.

We capped our classical optimizer at 5 restarts × 200 iterations and recorded, per
run, how many evaluations it used. Many runs reported **1000** — which is exactly
5 × 200. That is not a measurement of how much work the optimizer wanted; it is
the budget, read back to us.

Two things followed, and the second is the nastier one:

> **The cap bound the result, not just the count.** Given 5× the budget, runs that
> had been at the cap moved the quantity we actually cared about by a median of
> **100%** — one doubled — while runs that had genuinely converged moved by
> **0.0%**. Every headline number from the capped configuration was a lower bound.
> The 0.0% control is what makes this causal rather than noise: the pipeline is
> deterministic, so the movement is real.

> **Both arms of our comparison were capped, so the comparison read as a clean
> null.** We were comparing effort between two configurations. Numerator at 1000,
> denominator at 1000, ratio 1.000 — "no difference", tidy and false. A ratio of
> two censored quantities is dragged toward 1.0 *by construction*. Restricted to
> the pairs where neither side was capped, one configuration used **41% fewer**
> evaluations (95% CI [0.479, 0.708]) — a large effect in the opposite direction,
> hidden by the ceiling.

A floor makes a real effect look like zero. **A ceiling makes a real difference
look like agreement**, which is worse, because "no difference" is a conclusion
people are happy to accept and stop.

### The correction to that, which we also got wrong

Having found the ceiling, we wrote that a conclusion resting on it "is not
supported". That was the natural next step and it was an overreach, so we went and
checked: 120 runs varying the capped axis directly.

> The budget **was** binding — the baseline hit its cap on 10 of 10 runs. Lifting
> it 25× **did** help, by a statistically clear margin. And the conclusion
> **survived**, because the gap it had to close was three times larger than the
> effect the cap was hiding.
>
> The tell was that the extra budget went unspent: given 25× the allowance, the
> optimizer used 38% of it and stopped. It was no longer being cut off. Whatever
> limits it now is not the budget.

**A censored measurement invalidates a claim's precision, not automatically its
direction.** "This number is a bound, not a measurement" and "the conclusion drawn
from it is wrong" are different statements, and the second does not follow from the
first. Both of our steps were necessary: finding the ceiling was right, and
assuming it overturned the result was not. The only way to know which was to lift
the cap and look.

There is a cheap diagnostic in there. **If you raise a limit and the extra
allowance goes unused, the limit was not what was binding** — whatever the old
numbers looked like.

**Record the cap next to the count and flag equality.** It is one column and one
warning line. And note that the obvious test is one-sided: a total *below*
5 × 200 can still contain individual restarts that hit 200. Ours undercounted
badly — the aggregate test flagged 5 of 12 cells; 8 of 12 actually consumed more
when offered more. **The honest check is whether the run takes more budget when you
offer it**, which costs exactly one re-run.

### A related trap: fitting a model to the wrong observable

We fit a noise model to one observable (optimal-state probability), then used it to
predict a different one (a full-distribution distance). It overpredicted by
**+33%, +76%, +36%, +6%**. Refit directly on the quantity being predicted, it
worked. A model is calibrated *for a purpose*; it is not a general-purpose truth.

---

## 4. Statistics with small n, which is all you get on real hardware

Quantum hardware time is scarce, so every experiment has few repeats. Small-sample
statistics are therefore not an academic nicety — they are the daily reality, and
they are deeply unintuitive.

### A spread from two samples tells you almost nothing

We estimated run-to-run variability from **two** measurements. For two draws,

```
sd|X₁ − X₂| / E|X₁ − X₂| = √(2 − 4/π) / (2/√π) = 0.756
```

**~76% relative uncertainty.** Our observed spread of 0.0389 was consistent with
anything from 10% to 73% of the effect we were trying to protect — spanning
"negligible" to "as large as the signal". The test could not decide.

We had blamed the failure on vague wording (the threshold said "comparable to"
without a number). That was true but not the real problem:

> **A pre-fixed numeric threshold would not have saved it.** A 76%-uncertain
> estimate straddles any threshold in the plausible range. The design failed on
> *power*, not wording. Fixing the number is necessary and not sufficient.

How many repeats you need:

| replicates | degrees of freedom | uncertainty in the estimate |
|---:|---:|---:|
| 2 | 1 | **71%** |
| 3 | 2 | 50% |
| 5 | 4 | 35% |
| 10 | 9 | 24% |

Three is a floor, not a target.

### Check your design can produce every verdict it defines

The follow-up used 5 replicates and defined three outcomes: RESOLVED, UNRESOLVED,
INDETERMINATE. Working through the arithmetic *before* running it:

> At n = 5, **RESOLVED was unreachable**. Even with the true variance exactly zero,
> the statistical upper bound landed at 0.048 against a threshold of 0.034. The
> test could only ever return "bad" or "don't know". It could not return "fine".

We raised it to 10 replicates for ~15 extra seconds of quantum time. **A test that
cannot return one of its own verdicts is not a test** — and this is invisible
unless you simulate your own decision rule before collecting data.

### At n = 3 you cannot compare two variances

We measured run-to-run variability as 0.02437 and within-run as 0.01743 and wrote
that the former "exceeds" the latter. On 2 degrees of freedom the first has a 95%
interval of **[0.0127, 0.1532]** — a 12× span that contains the second. They were
**statistically indistinguishable**. We had compared two point estimates without
their intervals, which is the same error this document criticizes elsewhere.

---

## 5. Do not count the same noise twice

Two instances, both subtle, both changing conclusions.

**Bootstrapping something that was never sampled.** To get error bars we resampled
our data — standard. But we resampled *both* the measurement and the reference,
when the reference was computed exactly and carried no sampling error at all. That
injected noise the real quantity does not have. The symptom was visible and we
nearly missed it: the confidence intervals **did not contain their own point
estimates**. Fixing it moved the interval's lower bound from 0.0038 to **0.0291** —
an 8× improvement in margin, from "barely significant" to "comfortable". We had
been reporting our own result as far weaker than it was.

**Subtracting shot noise, or not.** A measured spread contains both device
fluctuation *and* ordinary counting noise. Our confidence interval already
accounted for counting noise. Comparing the *total* spread against the effect
charged us twice for the same term. Removing it:

```
σ_device = √(σ_total² − σ_shot²)
```

At the margin, the verdict **flipped** depending on which was used. If a decision
turns on an unstated choice, the choice is part of the method.

### The recurring version of this

Across three pre-registered experiments, **each one left an analysis choice
unspecified that could have decided the outcome** — which of two quantities went in
a denominator, whether a threshold applied to an estimate or its interval, whether
noise was subtracted. Stating a threshold in advance is not enough. **Every
quantity that feeds it has to be pinned too.**

**Then we did it a fourth time, in an experiment written specifically to avoid
it.** The pre-registration for the budget-ceiling test above fixed the threshold
(10%), the subset of runs, the interpretation table, and the direction of the risk.
It left the **classifier** loose — what counts as a "capped" run. Under the
registered definition the effect is 100% and the verdict fires; under the more
inclusive definition it is 8.0% and the verdict flips. The one thing we forgot to
pin is the one that decided it.

The pattern is worth naming: we keep pinning the *threshold* and forgetting the
**population it applies to**. A threshold is a number and feels like the decision;
the subgroup definition is a sentence and feels like description. It is not.

---

## 6. Process steps that caught real errors

Cheap habits, each of which caught something that would have wasted real
resources.

**Dry-run everything that spends.** Our submit script had a dry-run mode. Running
it showed the script rebuilding *the previous experiment's* circuits — it had never
been taught about the new one. Submitting would have burned ~20 seconds of quantum
time re-answering a question we had already answered. The dry run cost nothing.

**Look at the artifact, not the exit code.** Two examples. A figure generator
returned success while producing a chart whose title ran off both edges, and a
flat price line auto-scaled onto a $0.014 axis so that a *constant* price looked
like structure. Both were only visible by opening the image. Exit code 0 means the
program did not crash; it does not mean the output is right.

**Verify a fast implementation against a slow one.** We replaced a library
simulator with hand-written NumPy for a 300× speed-up, then checked it against the
original on random inputs: agreement to **3×10⁻¹⁵**. The check took a minute and
made every number downstream trustworthy. The script refuses to report if the
check fails.

**Make comparisons differ in exactly one thing.** We nearly compared error
mitigation on/off using circuits that had been *independently* compiled — 113 vs 98
gates for what was supposed to be the same circuit. The comparison would have
measured compilation randomness alongside the effect. Compiling once and reusing
fixed it.

**Process matching is a string search over command lines — including your own.**
This one cost three separate incidents in a single afternoon, and the last two
were *silent*:

1. `pkill -f optimizer_study.py` matched the very shell command that invoked it,
   and killed the parent instead of the target.
2. We killed a long job by PID — but the PID belonged to the shell *wrapper*, not
   the program. It ran for **another hour at 784% CPU**, invisibly, while we
   reported it stopped and drew conclusions from timings taken during the
   contention it was causing.
3. A queued experiment waited on `while pgrep -f "[s]tdbuf ..."` — but the
   waiting shell's own command line *contained that string*, in the line that
   would later launch the job. It waited on itself. **Fifty-one minutes at 0.0%
   CPU, reported twice as "running", having never started.**

The `[s]tdbuf` bracket trick stops the *pattern literal* from matching itself. It
does nothing when the same text appears elsewhere on the same command line — which
it always does when one shell invocation both waits for a job and launches one.

Match on a PID you captured, or on a marker that cannot appear in the launcher.

**The failure mode matters more than the bug.** In (2) and (3) the system reported
success while doing nothing. A `while pgrep` loop sitting at 0% CPU is
indistinguishable from a job in progress unless you check something the process
cannot fake — the child's CPU time, or whether the output file has grown. That is
the same lesson as "look at the artifact, not the exit code", applied to process
state instead of program output. **If you are going to report that something ran,
check evidence it produced, not that its supervisor is alive.**

**Prefer measurements that are immune to your own mistakes.** In the middle of that
mess we compared two configurations by *iteration count* rather than wall-clock
time. Iteration counts are unaffected by CPU contention; timings are not. We chose
it for an unrelated reason and it was the only reason the comparison survived.

---

## 7. Silent correctness bugs — the dangerous kind

None of these crashed. All produced plausible numbers.

**Inconsistent inputs.** Solar generation came from a chosen day of the year while
household demand and prices were always read from July. Summer solar with winter
demand, and nothing to indicate it. The fix derives *all three* from the same day
index so they cannot disagree by construction. **When several inputs must agree,
derive them from one source rather than trusting yourself to keep them aligned.**

**Stale committed artifacts.** A figure in the repo paired 21 June solar output
with a price schedule labelled July. It had been generated before the fix and
never regenerated. **Derived artifacts checked into a repository are claims, and
they go stale silently.** Regenerate them from the code that is current.

**`round(2.5)` is 2 in Python.** Banker's rounding rounds halves to even. A
"half-full battery" default silently became 40% full. Every result computed with
it was internally consistent and wrong. **Know your language's rounding rule.**

**Extrapolating from a toy case.** We estimated a cost on one synthetic day and
scaled it to a year. Computed properly over 365 real days, it was **more than 2×
larger**. Our reasoning about *why* was also wrong: we predicted the many zero-value
days would dilute the average, but a zero-value day contributes to neither the
numerator nor the denominator — it drops out entirely. The real mechanism was that
value concentrates into a few high-spread days, which are exactly the days the
approximation handled worst. **Toy cases mislead about magnitude and direction.**

---

## 8. Retract in place

We withdrew several claims. One example, because the reasoning error is common:

> **Claim:** "Device drift cannot explain this, because drift would have shifted
> both circuits and one of them didn't move."
>
> **Why it was wrong:** that circuit had no earlier measurement. "It didn't move"
> was never observable. The argument sounded like evidence and referred to nothing.
>
> **What we later measured:** drift was real and accounted for 43% of the shift.

A second, because the error is the opposite shape — over-correcting rather than
over-claiming:

> **Claim:** having discovered that an optimizer's evaluation counts were pinned
> at the budget we set, we wrote that a conclusion resting on them "is not
> supported".
>
> **Why it was wrong:** a censored measurement invalidates a claim's *precision*,
> not automatically its *direction*. We went from "this number is a bound, not a
> measurement" to "the conclusion drawn from it is wrong", and the second does not
> follow from the first.
>
> **What we later measured:** 120 runs varying the capped axis directly. The
> budget really was binding, and lifting it 25× really did help — by a
> statistically clear margin. The conclusion survived anyway, because the gap it
> had to close was three times larger than the effect the cap was hiding.

Others: a claim that an optimizer was "failing outright" (it was succeeding at a
mis-specified objective); a claim that no procedure could clear a threshold (the
top of the relevant range grazed just above it); the variance comparison in §4.

We struck these through **in place**, next to the original, with the reasoning that
failed — rather than quietly editing them away. Anyone rereading sees both the
claim and its correction. Quiet editing destroys exactly the information a reader
needs to calibrate how much to trust everything else.

**The pattern worth internalizing:** almost every retraction here was *a point
estimate compared without its uncertainty*. Two numbers, one bigger, conclusion
drawn. It is the single most common way to be confidently wrong with real data.

The exception is the second one above, and it is worth separating because the
instinct that produced it is the *good* one. Finding a defect in how something was
measured feels like finding the answer, and the honest move is smaller: a bad
measurement tells you that you do not know, which is not the same as knowing the
opposite. **Scepticism about a result is not evidence against it.** We had to run
the experiment to find out, and it went the other way.

---

## 9. The negative results taught more than the positive one

The project's positive result is real and useful: a better encoding captures the
full economic value of the battery at **52 qubits instead of 117**, at no cost.

But the negative results were worth more:

- The **optimizer study** — twelve configurations, all failing — is what exposed
  the penalty-weight problem, which is the finding that generalizes beyond this
  project entirely.
- The **failed measurability gate** stopped a hardware run that would have produced
  uninterpretable data, and produced the rule about checking resolution first.
- The **underpowered variance test** taught more by being underpowered than it
  would have by working, because it forced us to compute what a design *can*
  conclude before running it.

**The single most useful decision in the project was declining to spend quantum
time.** We planned a 10-hour run at the largest problem size, then noticed that the
metric had already bottomed out two sizes earlier: it would have returned nine
zeros. Not running it was worth more than running it, and no result would have
been published either way.

That generalizes past quantum computing. The instinct is to collect more data when
a result is unclear. Often the honest move is to work out what the data *could*
show, discover it is nothing, and spend the effort on a measurement that can
discriminate.

---

## A short checklist

1. Compare your constraint penalties to your objective's spread. Ratio ≫ 1 means
   you are optimizing the constraints.
2. Work out which resource actually limits you. It is usually not the one that is
   easy to count.
3. Compute what your metric will read if your hypothesis is true. If that is below
   your resolution, redesign before spending. Check the code computing it reaches
   your largest size, too — "unmeasurable" includes "the implementation dies there".
4. Simulate your own decision rule. Check it can return every verdict it defines,
   and pin the *population* it applies to, not just the threshold.
5. Never compare two point estimates without their intervals. Check neither is
   sitting on a limit you imposed — a ratio of two capped numbers is 1.0 by
   construction, and reads as a clean null. Then check whether the cap actually
   changed the answer: raise it, and if the extra allowance goes unused, it was
   never what was binding.
6. Do not let the same noise into your analysis twice.
7. Dry-run anything that spends; open the artifact rather than trusting exit
   codes; verify fast paths against slow ones. Before reporting that a job ran,
   check evidence it produced — not that its supervisor is alive.
8. Derive inputs that must agree from a single source.
9. Write down what would falsify you *before* you look, including the wording of
   the retraction.
10. Retract in place.
