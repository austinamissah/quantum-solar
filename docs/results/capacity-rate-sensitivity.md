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
| 6 | $1.45 | | 2.0 | $1.94 |
| 8 | **$1.94** | | 2.5 | **$2.42** |
| 10, 12, 16, 20 | $1.94 (flat) | | 5.0 | $2.42 (flat) |

Linear, then flat. The saving is

```
saving = min(capacity_kWh, rate_kW × peak_hours) × price_spread
```

which reproduces all thirteen solved points to the cent — here
`min(10, 2×4) × $0.24183 = $1.9346`.

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
| baseline | $455.72/yr | — |
| rating 2 kW → **2.5 kW** | $569.65/yr | **+$113.93/yr** |
| capacity 10 kWh → **20 kWh** | $455.72/yr | **+$0.00/yr** |

Doubling the pack earns nothing. A 25% larger inverter earns 25% more. **If
someone is buying anyway, rate is the axis that pays.**

(The per-day gap is $0.48 on a summer weekday, but annualizing that would
overstate it: winter's spread is $0.207 against summer's $0.242, so the winter
weekdays contribute less and the true annual gain is $113.93, not the ~$126 a
summer-only extrapolation gives.)

## Payback: the arithmetic a buyer actually needs

At $455.72/yr against a swept installed cost, with a warranty of **10 years** for
this class of system:

| installed cost | payback @ 2 kW | payback @ 2.5 kW | within warranty? |
|---:|---:|---:|:--:|
| $5,000 | 11.0 yr | 8.8 yr | only at 2.5 kW |
| $7,000 | 15.4 yr | 12.3 yr | no |
| $9,000 | 19.7 yr | 15.8 yr | no |
| $11,500 | 25.2 yr | 20.2 yr | no |
| $14,000 | 30.7 yr | 24.6 yr | no |

**These are upper bounds on the savings, so lower bounds on the payback.** The
model is lossless and assumes buy = sell; round-trip losses cut both the delivered
energy and the effective spread, and export credited below import lowers the
ceiling. Real payback is *longer* than every number above.

### The honest conclusion

**On a two-tier tariff, arbitrage alone does not pay for the hardware within its
warranted life.** At a typical ~$11,500 installed cost the battery pays back in
about 25 years against a 10-year warranty — it needs to outlive its guarantee
roughly two and a half times over, on savings figures that are already optimistic.
Only the cheapest configuration in the table (a $5,000 install with a 2.5 kW
inverter, at 8.8 years) clears the warranty at all, and it does so on the
optimistic side of assumptions that all point the same way.

This is a statement about **arbitrage**, not about batteries. Home batteries are
also bought for backup power and resilience during outages, and that value is real
— it is simply not something this model prices, because a cost-minimizing schedule
against a known price curve has no term for "the power stayed on". A buyer who
wants backup may well be making a sound decision. What does not survive the
arithmetic is the *savings* pitch.

## Caveats

**The v1 caveats apply, and they cut in opposite directions.** The model is
lossless with a single buy = sell price
(see [`../ARCHITECTURE.md`](../ARCHITECTURE.md)):

- **Round-trip losses would reduce both terms.** Less energy arrives than was
  stored, so both the delivered kWh and the effective spread shrink; every number
  above is an upper bound.
- **Export paid below import would lower the ceiling.** The spread that a
  discharge actually earns is set by what the utility credits, not by the import
  price, so `price_spread` here is the optimistic case.
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
