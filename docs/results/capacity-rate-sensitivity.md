# Battery sizing: how the saving responds to capacity and power rating

**Instance:** the summer weekday of `docs/figures/web/schedule_real_day.json`
(Golden, CO; AMY-2018 day 192; Xcel RE-TOU). **Method:** every point re-solved
exactly with `dp_solve`, not evaluated from a formula — the formula below is then
checked against the solver at every point. **Regenerate:**
`python scripts/make_real_schedule_figure.py`; the numbers land in the
`sensitivity` block of that JSON.

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

## The part that is useful before buying hardware

Vendors quote kWh. The binding number is the smaller of kWh and
`rate × peak-window length`. A 10 kWh battery with a 2 kW inverter, on a
four-hour peak window, is an 8 kWh battery as far as the bill is concerned —
and the fix is a bigger inverter, not a bigger pack: at 10 kWh, going from 2 kW
to 2.5 kW buys more ($1.94 → $2.42) than going from 8 kWh to 20 kWh at 2 kW
buys ($1.94 → $1.94, i.e. nothing).

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
