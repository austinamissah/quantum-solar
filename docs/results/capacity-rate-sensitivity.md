# Battery sizing: how the saving responds to capacity and power rating

**Instance:** the summer weekday of `docs/figures/web/schedule_real_day.json`
(Golden, CO; AMY-2018 day 192; Xcel RE-TOU), plus synthetic two-tier tariffs for
the peak-window sweep. **Method:** every point re-solved exactly with `dp_solve`,
not evaluated from a formula — the formula below is then checked against the
solver at every point. **Regenerate:**
`python scripts/make_real_schedule_figure.py` (the `sensitivity` block of that
JSON) and `python scripts/battery_sizing_study.py`
(`docs/results/capacity_rate_sensitivity.json`).

## The result

Sweeping capacity at a fixed 2 kW rating, then rating at a fixed 10 kWh:

| capacity (kWh) @ 2 kW | saving | | rating (kW) @ 10 kWh | saving |
|---:|---:|---|---:|---:|
| 2 | $0.48 | | 0.5 | $0.48 |
| 4 | $0.97 | | 1.0 | $0.97 |
| 6 | $1.45 | | 2.0 | $1.93 |
| 8 | **$1.93** | | 2.5 | **$2.42** |
| 10, 12, 16, 20 | $1.93 (flat) | | 5.0 | $2.42 (flat) |

Linear, then flat. The saving is

```
saving = min(capacity_kWh, rate_kW × peak_hours) × price_spread
```

which reproduces all thirteen solved points to the cent — here
`min(10, 2×4) × $0.24183 = $1.9346`.

Those figures are for a **lossless** battery. Round-trip losses replace
`price_spread` with an effective spread `p_peak·η_d − p_off/η_c` and change
nothing else — **the knee stays put**, so every sizing conclusion below holds
either way. Only the dollar amounts shrink (see Caveats).

## Why: this is the forced-discharge result in another form

The optimum census on this same day
([`slack-free-encoding.md`](slack-free-encoding.md) is the sibling study; the
census itself is described under `optima_census` in
[`../ARCHITECTURE.md`](../ARCHITECTURE.md)) found that of 2,448 tied minimal
schedules, **the only forced decisions are discharging in all four peak hours**.
All 20 off-peak hours are free.

That is the same fact as this one. If every optimal plan empties the battery
across the whole peak window and nothing else is determined, then the only energy
that earns anything is the energy the rating can push out *during that window*.
Capacity beyond `rate × peak_hours` is never discharged at the high price, so it
cannot pay. On the tested 10 kWh / 2 kW battery, **8 kWh is the most that can be
delivered and 2 kWh never moves.**

## Does the rule generalize? Peak-window sweep

The rule turns entirely on `peak_hours`, and Colorado's 4-hour block was the only
window tested. Re-running on synthetic two-tier tariffs at 3, 4, 5 and 6 peak
hours, spread held fixed at $0.24183 (`python scripts/battery_sizing_study.py`):

| peak hours | window | `rate × hours` | measured knee | daily ceiling |
|---:|---:|---:|---:|---:|
| 3 | 18–20 | 6 kWh | **6 kWh** | $1.45 |
| 4 | 17–20 | 8 kWh | **8 kWh** | $1.93 |
| 5 | 16–20 | 10 kWh | **10 kWh** | $2.42 |
| 6 | 15–20 | 12 kWh | **12 kWh** | $2.90 |

The saturation point moves exactly to `rate × peak_hours`, and all **56** swept
points (4 windows × 9 capacities + 4 × 5 ratings) match the rule — zero
mismatches. So the rule is a property of two-tier tariff structure, not of this
one tariff: **read your peak-window length off your own bill and multiply by your
inverter rating** to get the capacity beyond which more kWh earns nothing.

### Which rate? The discharge one

Spec sheets quote a charge rating and a discharge rating, and they are often
different. Only the **discharge** rating appears in the rule:

```
saving = min(capacity, DISCHARGE_rate × peak_hours) × effective_spread
```

Verified across asymmetric pairs at 10 kWh on a 4-hour peak — 1.0-in/2.0-out and
4.0-in/2.0-out both save $1.93, exactly as 2.0/2.0 does, while 2.0-in/1.0-out saves
$0.97 and 2.0-in/0.5-out $0.48. The charge rating drops out entirely. That follows
from the forced-discharge result again: only energy pushed out *during* the peak
earns, so only the rating that governs pushing it out can matter.

**The one exception is a charge rating too slow to refill.** At 0.5 kW in against
2.0 kW out the saving falls to **$1.45**, below the $1.93 the rule predicts,
because the battery cannot be returned to its starting level within the available
off-peak hours and so cannot empty itself during the peak. So: **buy on the
discharge rating, and check the charge rating is merely adequate** rather than
matched.

One construction detail that matters. The window *ends* at hour 20 and grows
backward as it lengthens, which is how utilities actually widen an evening peak.
Growing it forward instead would eat the post-peak hours the battery needs to
return to its starting level, and that constraint — not the rule under test —
would bind. Holding the refill window at 3 hours keeps the sweep measuring what
it claims to.

## The part that is useful before buying hardware

Vendors quote kWh. The binding number is the smaller of kWh and
`rate × peak-window length`. A 10 kWh battery with a 2 kW inverter, on a
four-hour peak window, is an 8 kWh battery as far as the bill is concerned —
and the fix is a bigger inverter, not a bigger pack. Over a full year on the real
tariff:

| upgrade from 10 kWh / 2 kW | annual battery savings | gain |
|---|---:|---:|
| baseline | $404.28/yr | — |
| rating 2 kW → **2.5 kW** | $505.35/yr | **+$101.07/yr** |
| capacity 10 kWh → **20 kWh** | $404.28/yr | **+$0.00/yr** |

*(At the 0.90 round trip. Losslessly these were $455.72, $569.65 and +$113.93; the
asymmetry is unchanged, only scaled.)*

### One constant generates all of these numbers

Below the knee the annual value is **exactly** linear in delivered peak energy, at

```
$56.9646 /yr per kWh/day of peak-window throughput      (lossless, this tariff)
```

which is nothing more than the year's price spreads summed: 86 summer weekdays ×
$0.24183 + 175 winter weekdays × $0.20667 + 104 weekends × $0. Verified to the cent
at eight (capacity, rate) points spanning both the capacity-bound and rate-bound
sides of the knee — every one returns the same constant per kWh/day.

So each headline figure is a small multiple of it, and the multiplier is just how
much daily peak throughput the change adds or removes:

| change | Δ useful kWh/day | annual |
|---|---:|---:|
| rating 2 → 2.5 kW (useful 8 → 10 kWh/day) | +2 | **+$113.93** |
| capacity 10 → 20 kWh (useful stays 8) | 0 | $0.00 |
| `cp5band` → `cp5`, the last four qubits (`slack-free-encoding.md`) | −2 | **−$113.93** |
| `cp5` → `cp3` (useful 6 → 2 kWh/day) | −4 | −$227.86 |

**The repeated $113.93 is a real identity, not a transcription.** It reads like a
copy-paste — the same figure to the cent for a hardware upgrade and for a qubit
count — and it is worth knowing that it is not. The two are computed by different
code paths (this study varies `capacity`/`charge_energy` through
`annual_from_inputs` with the exact DP; the encoding study passes `qubo_min_exact`
in through the same function's `solver` hook), and they coincide because both
happen to move 2 kWh/day of peak throughput. Re-derived independently on
2026-08-07, both to $113.9293.

Doubling the pack earns nothing. A 25% larger inverter earns 25% more. **If
someone is buying anyway, rate is the axis that pays.**

(Don't annualize the per-day gap. Winter's spread is $0.207 against summer's
$0.242, so winter weekdays contribute less; extrapolating the summer weekday alone
overstates the gain by about 11%. Both figures above come from the full 365-day
DP via `annual_from_inputs`.)

## Payback: the arithmetic a buyer actually needs

**Round-trip losses are now priced** (they were assumed away when this section was
first written — see the retraction below). A residential Li-ion system with its
inverter is typically specified around a **0.90 AC round trip**, which is the
headline used here; the loss is split evenly across the two legs.

Losses cost about **11% of the annual saving**, and the payback moves with it:

| round trip | annual saving | vs lossless | payback @ $11,500 |
|---:|---:|---:|---:|
| 1.00 *(old model)* | $455.72 | — | 25.2 yr |
| 0.95 | $430.53 | −5.5% | 26.7 yr |
| **0.90** | **$404.28** | **−11.3%** | **28.4 yr** |
| 0.85 | $376.85 | −17.3% | 30.5 yr |
| 0.80 | $348.10 | −23.6% | 33.0 yr |

At the 0.90 headline, against a warranty of **10 years** for this class of system:

| installed cost | payback @ 2 kW | payback @ 2.5 kW | within warranty? |
|---:|---:|---:|:--:|
| $5,000 | 12.4 yr | 9.9 yr | only at 2.5 kW, barely |
| $7,000 | 17.3 yr | 13.9 yr | no |
| $9,000 | 22.3 yr | 17.8 yr | no |
| $11,500 | **28.4 yr** | 22.8 yr | no |
| $14,000 | 34.6 yr | 27.7 yr | no |

### The export credit, and why it does not rescue the case

Both v1 assumptions are now priced. Sweeping the export credit at the 0.90 round
trip, reporting **both legs** because they move in opposite directions:

| export credit | solar $/yr | battery $/yr | payback @ $11,500 |
|---:|---:|---:|---:|
| 1.00 *(full-retail net metering)* | $970.61 | $404.28 | 28.4 yr |
| 0.75 | $859.09 | $414.96 | 27.7 yr |
| 0.50 | $747.57 | $441.52 | 26.0 yr |
| 0.25 | $636.05 | $469.51 | 24.5 yr |
| 0.10 *(near avoided-cost)* | $569.14 | **$486.94** | **23.6 yr** |

**A worse export credit makes the battery *more* valuable, not less** — the
opposite of what this document previously asserted. The intuition that a poor
credit hurts ("a discharge earns less") covers only discharges that would have
been exported, and misses the larger effect: a poor credit creates
**self-consumption** value. A surplus kWh that would have been dumped at the
export rate can instead be stored and used to avoid buying at retail, and that
gain grows as the credit falls. The *solar* leg moves the other way, losing ~40%
between full retail and avoided cost — which is why the three-way split reports
them separately and why they must never be added into one "system savings".

The consequence for the conclusion is that it **no longer depends on the
assumption at all**. Payback at $11,500 is bracketed in **[23.6, 28.4] years**
across the whole plausible range, against a 10-year warranty. Every remaining
uncertainty has been swept, and none of it reaches the bar.

### The honest conclusion

**On a two-tier tariff, arbitrage alone does not pay for the hardware within its
warranted life.** At a typical ~$11,500 installed cost the battery pays back in
**23.6–28.4 years** — across every value of both formerly-optimistic assumptions —
against a 10-year warranty. It must outlive its guarantee between two and three
times over. Nothing in a plausible cost range clears the warranty at 2 kW; the
single case that does, a $5,000 install with a 2.5 kW inverter at **9.9 years**,
clears it by six weeks. That is not a margin anyone should buy on.

This conclusion is now **bracketed rather than bounded**. It used to rest on
assumptions that were flagged as optimistic and pointed one way; both have since
been priced, one of them turned out to point the *other* way, and the conclusion
survives either way. That is a stronger claim than the original, and it is the
reason the modeling work was worth doing.

> **Retraction, 2026-08-07.** This section originally reported $455.72/yr and a
> ~25-year payback from a **lossless** battery, flagged as an upper bound but not
> quantified. Losses are now modeled and the true figures are $404.28/yr and
> ~28 years. The direction was right and the magnitude was understated: the
> lossless model overstates the saving by 11%. The old $5,000-at-2.5 kW case
> (8.8 yr, comfortably inside warranty) becomes 9.9 yr, i.e. marginal. Left here
> rather than silently updated, because "flagged as an upper bound" is weaker than
> "measured" and the gap between them is the whole point.
>
> **Second retraction, same date.** This section also said an export credit below
> import "reduces what each discharge earns, so these paybacks are still lower
> bounds". That was wrong in *direction*, not just magnitude: a worse credit raises
> the battery's saving through self-consumption and shortens payback (28.4 → 23.6
> years at $11,500). The reasoning missed that avoided imports are worth more when
> exports are worth less. Both assumptions are now swept rather than argued about,
> which is the only reason the error surfaced.

This is a statement about **arbitrage**, not about batteries. Home batteries are
also bought for backup power and resilience during outages, and that value is real
— it is simply not something this model prices, because a cost-minimizing schedule
against a known price curve has no term for "the power stayed on". A buyer who
wants backup may well be making a sound decision. What does not survive the
arithmetic is the *savings* pitch.

## Caveats

**Losses are modeled; one optimistic assumption remains**
(see [`../ARCHITECTURE.md`](../ARCHITECTURE.md)):

- **Round-trip losses change the multiplier, not the knee.** With efficiencies the
  rule becomes
  `saving = min(capacity, rate × peak_hours) × (p_peak·η_d − p_off/η_c)` — the
  bracket is an *effective* spread ($0.2148 at a 0.90 round trip, against $0.2418
  lossless). Verified: at round trips of 1.0, 0.9 and 0.8 the knee stays at 8 kWh
  and only the ceiling moves ($1.93 / $1.72 / $1.48). **So every sizing conclusion
  on this page is unaffected by losses** — buy for `rate × window` regardless.
- **Where the loss sits matters, not just the round trip.** Arbitrage buys cheap
  and sells dear, so energy lost charging is wasted at the off-peak price and
  energy lost discharging at the peak price. Same round trip, different bill.
  Only the break-even ratio depends on the product alone.
- **Losses introduce a break-even the lossless model had no notion of.** A cycle
  pays only where `p_peak/p_off > 1/round_trip`. Xcel's summer ratio is **2.74**
  against a threshold of **1.11** at a 0.90 round trip, so arbitrage stays firmly
  profitable here — it would not on a tariff with a spread under ~11%.
- **Export paid below import is now modeled, and it helps the battery.** It
  raises the battery leg (self-consumption) while cutting the solar leg; see the
  export sweep above. It does change the sizing arithmetic on a solar-bearing day,
  because whether a slot imports or exports now matters — the daily figures on this
  page are computed under net metering and are the conservative case for the
  battery.
- **The optimal plan stops ignoring solar and load.** Under net metering the bill
  separates and the plan depends on the price curve alone. An export credit below
  import puts a kink at `net == 0`, which finally couples the plan to the
  household — the thing round-trip losses were wrongly expected to do.
- The **saving is measured against idling the same battery**, so it is the
  battery's contribution alone and excludes solar's.

**Swept ratings are restricted to ones that divide the capacity.** The SoC grid
has step `rate`, so off-grid pairs (10 kWh at 3 kW) have no exact representation
and are now rejected by `require_soc_on_grid`. Before that guard existed the DP
*rounded* them, and 10 kWh at 6 kW silently became a 12 kWh battery — a schedule
reaching 12.0 kWh reported as optimal and feasible. The quantized points are also
genuinely non-monotonic (10 kWh at 4 kW delivers 8 kWh, less than at 2.5 kW),
which is a discretization artifact rather than anything about batteries, and is
why they are kept out of a table meant to inform a purchase.

**One instance, one tariff.** The shape (linear then flat, with the knee at
`rate × peak_hours`) follows from the structure of a two-level time-of-use tariff
and should carry; the dollar figures are one Colorado day and should not be
extrapolated. Weekend days on this tariff are flat-priced and save **$0** at any
size or rating — no sizing helps when there is no spread to capture.
