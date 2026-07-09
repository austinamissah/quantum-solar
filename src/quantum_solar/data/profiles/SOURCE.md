# Source: `co_residential_summer_weekday.csv`

Representative Colorado residential household load, 24 hourly kWh for a typical
summer weekday.

- **Dataset:** NREL *End-Use Load Profiles for the U.S. Building Stock* (ResStock),
  release `resstock_amy2018_release_2` (2024). OEDI submission 4520.
- **Source file (state aggregate, single-family detached, baseline upgrade 0):**
  `https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2024/resstock_amy2018_release_2/timeseries_aggregates/by_state/upgrade=0/state=CO/up00-co-single-family_detached.csv`
- **Dataset landing page:** https://data.openei.org/submissions/4520
- **Documentation:** https://www.nlr.gov/buildings/end-use-load-profiles

## How this profile was derived

The aggregate CSV is a 15-minute, year-long (AMY 2018) sum of electricity across
all represented Colorado single-family-detached dwellings. We:

1. computed per-dwelling load =
   `out.electricity.total.energy_consumption.kwh / units_represented`
   (`units_represented` ≈ 1.49M CO single-family detached homes),
2. kept every **July weekday** (22 days; July matches the URDB summer TOU price
   schedule used elsewhere),
3. mapped each interval-ending timestamp to its interval-start hour and summed the
   four 15-minute intervals into hourly kWh,
4. averaged over the 22 July weekdays.

Result: a representative summer-weekday profile totaling **~30.5 kWh/day**, with
an overnight low (~0.65 kWh) and an evening peak (~1.96 kWh at 19:00) — the
expected residential diurnal shape. Single-family detached is the most common
Colorado home type, chosen as the representative household.

Regenerating this file requires re-downloading the ~40 MB aggregate CSV; the
derived 24-value profile is committed here so no network is needed at runtime.
