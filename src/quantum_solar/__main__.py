"""``python -m quantum_solar`` — the one-command demo.

Runs the whole classical pipeline on real Colorado data and prints it: one day's
optimal battery plan, the exact 365-day three-way savings split, the sizing rule,
and the payback arithmetic. ``--quantum`` adds the QAOA half.

Three things it is built around:

* **No network, no API key, no notebook.** Everything comes from data already
  committed to the repo — the annual PVWatts/URDB snapshot in
  ``docs/figures/annual_golden_co.json`` and the packaged ResStock load profiles.
  ``data/cache/`` is gitignored, so before this the interesting half of
  ``notebooks/demo.ipynb`` could not run on a fresh clone at all.
* **No dependencies beyond numpy.** The classical solvers are numpy-only by
  design (``__init__`` defers every qiskit import), so this module renders in text
  rather than reaching for matplotlib, and ``--quantum`` is the only path that
  needs a quantum stack installed.
* **The exact solvers, not a re-implementation.** Every dollar figure goes through
  ``annual.annual_from_inputs`` — the same call the README quotes — so the two
  cannot drift. ``tests/test_cli.py`` pins them against the README.

The reporting rules the repo cares about are enforced here rather than left to the
reader: forced hours are separated from tied ones, the solar and battery legs are
never summed, and the net-metering caveat is printed next to the plan rather than
buried, because under a single buy/sell price the optimal plan provably ignores
solar and load entirely.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .annual import annual_from_inputs
from .data.calendar import day_to_month, day_type, is_weekend
from .data.load_profile import load_profile
from .data.nrel import build_instance, to_slots
from .dynamic_programming import dp_solve, optima_census

SNAPSHOT = "docs/figures/annual_golden_co.json"

# Payback context. Warranties in this class are typically 10 years, which is the
# number the payback has to beat; the install cost is the README's midpoint.
INSTALLED_COST = 11_500.0
WARRANTY_YEARS = 10

# Sweep points for the sizing section. Every rate divides every capacity, which
# `require_soc_on_grid` requires: an off-grid pair silently became a *larger*
# battery before that guard existed.
SWEEP_CAPACITIES = (2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0)
SWEEP_RATES = (0.5, 1.0, 2.0, 2.5, 5.0)

BLOCKS = "▁▂▃▄▅▆▇█"


def _find_snapshot() -> Path:
    """Locate the committed annual snapshot by walking up from this file."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / SNAPSHOT
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"Could not find {SNAPSHOT}.\n"
        "This demo reads the committed snapshot from a source checkout of the "
        "repository; it is not packaged with an installed wheel. Run it from a "
        "clone, or use quantum_solar.annual_savings(lat, lon) with an NREL_API_KEY "
        "to fetch the inputs live."
    )


def _bar(values: np.ndarray, lo: float, hi: float) -> str:
    """Render values as block characters, without inventing structure.

    A constant series renders as one flat level rather than being stretched over
    the full block range — auto-scaling a flat price onto its own noise once made
    a constant look like a signal in a committed figure.
    """
    if hi - lo < 1e-9:
        return BLOCKS[0] * len(values)
    idx = np.clip(((values - lo) / (hi - lo) * (len(BLOCKS) - 1)).round(), 0,
                  len(BLOCKS) - 1).astype(int)
    return "".join(BLOCKS[i] for i in idx)


def _plan_row(charge: np.ndarray, discharge: np.ndarray) -> str:
    return "".join("C" if c else "D" if d else "·" for c, d in zip(charge, discharge))


def _ruler(n: int) -> str:
    row = [" "] * n
    for h in range(0, n, 3):
        for k, ch in enumerate(str(h)):
            if h + k < n:
                row[h + k] = ch
    return "".join(row)


def _forced_runs(forced: dict[int, str]) -> list[str]:
    """Collapse ``{hour: action}`` into runs — "17:00–20:00 discharge".

    A flat-price day forces all 24 hours, and listing them one by one buries the
    one thing the line exists to say.
    """
    runs: list[str] = []
    for hour in sorted(forced):
        action = forced[hour]
        if runs and runs[-1][2] == action and runs[-1][1] == hour - 1:
            runs[-1][1] = hour
        else:
            runs.append([hour, hour, action])
    return [f"{a:02d}:00 {act}" if a == b else f"{a:02d}:00–{b:02d}:00 {act}"
            for a, b, act in runs]


def _money(x: float) -> str:
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def _bold(text: str) -> str:
    """Bold on a terminal, plain when piped to a file or a pager."""
    return f"\033[1m{text}\033[0m" if sys.stdout.isatty() else text


def _load_snapshot():
    snap = json.loads(_find_snapshot().read_text())
    generation = np.array(snap["generation"], dtype=float)
    weekday = np.array(snap["price_weekday"], dtype=float)
    weekend = np.array(snap["price_weekend"], dtype=float)

    def price_for(month: int, is_wknd: bool) -> np.ndarray:
        return weekend[month] if is_wknd else weekday[month]

    return snap, generation, price_for


def _annual(generation, price_for, *, capacity, rate, round_trip, export_ratio):
    """The three-way split. Identical call to the one the README's table quotes.

    The round trip is split evenly across the two legs as sqrt(round_trip): where
    the loss sits changes the bill, not just the product, because energy lost
    charging is wasted at the off-peak price and energy lost discharging at the
    peak price.
    """
    leg = float(np.sqrt(round_trip))
    return annual_from_inputs(
        generation, price_for, load_profile,
        capacity=capacity, charge_energy=rate, discharge_energy=rate,
        charge_efficiency=leg, discharge_efficiency=leg, export_ratio=export_ratio,
    )


def _day_problem(generation, price_for, day, *, capacity, rate, round_trip, export_ratio):
    leg = float(np.sqrt(round_trip))
    month, wknd, dtype = day_to_month(day), is_weekend(day), day_type(day)
    return build_instance(
        to_slots(generation, day, 24),
        to_slots(load_profile(month, dtype), day=0, num_slots=24),
        price_for(month, wknd),
        capacity=capacity, charge_energy=rate, discharge_energy=rate,
        charge_efficiency=leg, discharge_efficiency=leg, export_ratio=export_ratio,
    ), dtype


def section(title: str) -> None:
    print(f"\n{_bold(title)}")
    print("─" * 72)


def show_day(problem, dtype, day, *, quiet_caveats=False) -> None:
    solution = dp_solve(problem)
    census = optima_census(problem)
    charge, discharge = problem.decode(solution.x)
    soc = problem.soc_trajectory(charge, discharge)[:problem.num_slots]
    idle = np.zeros(problem.num_decision_vars, dtype=np.int8)
    idle_bill = problem.grid_cost(*problem.decode(idle))

    price = problem.price
    flat = price.max() - price.min() < 1e-9

    section(f"ONE DAY — day {day} of 2018, a {dtype}")
    print(f"  hour       {_ruler(problem.num_slots).rstrip()}")
    print(f"  price      {_bar(price, price.min(), price.max())}"
          f"   {'flat all day' if flat else f'${price.min():.3f} … ${price.max():.3f}/kWh'}")
    print(f"  plan       {_plan_row(charge, discharge)}   C charge · D discharge · · idle")
    print(f"  level      {_bar(soc, 0.0, problem.capacity)}   0 … {problem.capacity:g} kWh")
    print()
    print(f"  bill {_money(solution.true_energy)}   ·   idle battery {_money(idle_bill)}"
          f"   ·   battery saves {_money(idle_bill - solution.true_energy)}")

    forced = census.forced()
    free = problem.num_slots - len(forced)
    if forced:
        runs = _forced_runs(forced)
        print(f"\n  Forced   {len(forced)}/{problem.num_slots} hours — every optimal plan "
              f"agrees here:")
        print(f"           {', '.join(runs)}")
    else:
        print("\n  Forced   nothing — no hour's action is determined.")

    if census.n_minimal == 1:
        print(f"  Unique   exactly one minimal-cost plan, so the picture above IS the "
              f"answer,\n           not one of many.")
    else:
        print(f"  Tied     {census.n_minimal:,} minimal-cost plans tie"
              f"{f', differing over the other {free} hours' if free else ''}.")
        print(f"           The plan above is one arbitrary pick among them — read the "
              f"forced hours,\n           not the individual bars.")
    if flat and not quiet_caveats:
        print("           A flat price means no arbitrage exists, so idling is optimal.")

    if not quiet_caveats:
        print("\n  Note     Under net metering (buy price == sell price) the optimal plan "
              "provably\n           depends on the PRICE curve alone — it is unchanged by "
              "zero solar, triple\n           solar, or any load. Not real-world advice to "
              '"charge on surplus solar".')


def show_year(result, *, capacity, rate, round_trip, export_ratio) -> None:
    section("FULL YEAR — 365 exact DP solves, no sampling of representative days")
    print(f"  no system      (no solar, no battery)        {_money(result.no_system_cost):>12}")
    print(f"  solar only     (battery idle)                {_money(result.solar_only_cost):>12}"
          f"    solar saves   {_money(result.solar_savings):>10}")
    print(f"  solar + optimal battery                      {_money(result.optimized_cost):>12}"
          f"    battery adds  {_money(result.battery_savings):>10}")
    print("\n  The battery figure holds solar fixed, so it is the battery ALONE. Do not add")
    print("  the two: under an export credit below retail they move in OPPOSITE directions")
    print("  (a poor credit hurts solar and helps the battery, via self-consumption).")

    if result.battery_savings > 0:
        years = INSTALLED_COST / result.battery_savings
        verdict = "beats" if years <= WARRANTY_YEARS else "does NOT beat"
        print(f"\n  Payback  {_money(INSTALLED_COST)} install ÷ {_money(result.battery_savings)}/yr"
              f" = {_bold(f'{years:.0f} years')}")
        print(f"           against a ~{WARRANTY_YEARS}-year warranty — it {verdict} it. "
              f"On a two-tier tariff,\n           arbitrage alone does not pay for the hardware "
              f"within its warranted life.\n           (Backup and resilience are real value this "
              f"model does not price.)")
        if round_trip == 1.0:
            print(f"           These are the library's LOSSLESS defaults. A realistic 0.90 "
                  f"round trip\n           costs ~11% of the battery leg: try "
                  f"--round-trip 0.90.")


def show_sizing(generation, price_for, *, capacity, rate, round_trip, export_ratio) -> None:
    section("SIZING — what actually earns")

    def battery(cap, rt):
        return _annual(generation, price_for, capacity=cap, rate=rt,
                       round_trip=round_trip, export_ratio=export_ratio).battery_savings

    caps = [(c, battery(c, rate)) for c in SWEEP_CAPACITIES]
    rates = [(r, battery(capacity, r)) for r in SWEEP_RATES]
    left_w = 30
    print(f"  {f'capacity sweep at {rate:g} kW':<{left_w}}rate sweep at {capacity:g} kWh")
    for i in range(max(len(caps), len(rates))):
        left = (f"{caps[i][0]:>7.1f} kWh {_money(caps[i][1]):>11}/yr"
                if i < len(caps) else "")
        right = (f"{rates[i][0]:>6.1f} kW {_money(rates[i][1]):>11}/yr"
                 if i < len(rates) else "")
        print(f"  {left:<{left_w}}{right}")

    # The sizing rule is a PURE-ARBITRAGE result and is only verified under net
    # metering. Below-retail export couples the plan to solar and load, so the
    # battery earns self-consumption value on top of arbitrage: the knee stops
    # existing and the rate column stops being monotonic. Narrating the rule over
    # those numbers would be a confidently wrong claim, so it is not printed there.
    if export_ratio != 1.0:
        print(f"\n  The sizing rule below is derived under NET METERING and does not apply at")
        print(f"  an export credit of {export_ratio:g}× retail. Paying less for exports than")
        print(f"  imports makes the bill depend on the sign of the household's net, which")
        print(f"  couples the plan to solar and load and adds self-consumption value on top")
        print(f"  of arbitrage. The figures above are still the exact DP's answer; they are")
        print(f"  just not the rule's. Re-run without --export-ratio to see the rule hold.")
        return

    print("\n  Every optimal plan discharges through the whole peak window and nothing else")
    print("  is forced, so the only energy that can pay is what the inverter pushes out")
    print("  INSIDE that window:      saving = min(capacity, rate × peak_hours) × spread")

    ceiling = max(s for _, s in caps)
    knee = min(c for c, s in caps if abs(s - ceiling) < 0.005)
    print(f"\n  The capacity column flattens at {knee:g} kWh: past that the inverter cannot")
    print(f"  deliver the extra energy inside the peak window, so it never earns.")
    print(f"  {_bold('Rate is the axis that pays.')}")
    lo, hi = rates[SWEEP_RATES.index(2.0)], rates[SWEEP_RATES.index(2.5)]
    print(f"  {lo[0]:g} → {hi[0]:g} kW is worth {_money(hi[1] - lo[1])}/yr; "
          f"{knee:g} → {SWEEP_CAPACITIES[-1]:g} kWh is worth "
          f"{_money(ceiling - dict(caps)[knee])}/yr.")
    if round_trip != 1.0:
        print(f"  Losses move the multiplier, not the knee — it is at {knee:g} kWh either way.")
    print("\n  Read your own peak-window length off your bill and multiply by your inverter")
    print("  rating. Vendors quote kWh; the binding number is the smaller of the two.")


def show_quantum(seed: int) -> None:
    """The QAOA half, on an instance small enough to verify exactly."""
    section("QUANTUM — QAOA against the exact solvers")
    try:
        from .ising import qubo_to_ising  # noqa: F401
        from .qaoa import QAOASolver
    except ImportError as exc:
        print("  Needs the quantum stack, which the classical path deliberately does not:")
        print(f"    {exc}")
        print("  Install it with:  pip install -r requirements.txt")
        return

    from .brute_force import brute_force_solve, enumerate_bitstrings
    from .problem import synthetic_instance
    from .qubo import PenaltyWeights, build_qubo, default_weights
    from .statevector import qaoa_probabilities

    problem = synthetic_instance(2, seed=seed, capacity=3.0, charge_energy=1.0,
                                 initial_soc=1.0)
    base = default_weights(problem)
    # alpha* = objective span over feasible schedules / penalty scale.
    costs = [problem.energy(x) for x in enumerate_bitstrings(2 * problem.num_slots)
             if problem.is_feasible(x)]
    a_star = (max(costs) - min(costs)) / base.soc_bounds

    print(f"  A {problem.num_slots}-slot instance, small enough that brute force can check "
          f"the encoding.")
    dp = dp_solve(problem)
    print(f"  exact DP        {_money(dp.true_energy)}")
    print(f"  brute force     {_money(brute_force_solve(problem, build_qubo(problem, base)).true_energy)}"
          f"   (enumerates the QUBO)")

    for label, weights in (("default", base),
                           ("α* = %.4f" % a_star,
                            PenaltyWeights(a_star * base.mutual_exclusion,
                                           a_star * base.soc_bounds,
                                           a_star * base.terminal))):
        qubo = build_qubo(problem, weights)
        result = QAOASolver(reps=2, n_starts=5, shots=4096, seed=1234).solve(problem, qubo)
        x = enumerate_bitstrings(qubo.num_vars).astype(float)
        energy = np.einsum("bi,ij,bj->b", x, qubo.Q, x) + qubo.offset
        probs = qaoa_probabilities(energy, result.optimal_params, 2)
        mass = float(probs[np.isclose(energy, energy.min(), atol=1e-6)].sum())
        ratio = mass * 2 ** qubo.num_vars
        ratio_str = f"{ratio:.2f}×" if ratio < 1 else f"{ratio:.1f}×"
        print(f"  QAOA @ {label:<12} {_money(result.true_energy)}   "
              f"P(optimal) = {mass:.4f}   ({ratio_str} uniform)")

    print(f"\n  Same circuit, same optimizer — only the constraint penalty scale differs.")
    print(f"  Penalties at the usual rule of thumb are ~{1 / a_star:.0f}× the span of the")
    print(f"  electricity cost, so QAOA optimizes the constraints and ignores the price.")
    print(f"  Every solver agrees on the COST either way; what the weight ruins is how")
    print(f"  often the circuit hands you the right schedule.")
    print(f"\n  Angles are tuned fresh here, so these land near — not exactly on — the")
    print(f"  committed figure's 0.0011 / 0.1398: the tuning is deterministic per run but")
    print(f"  its trajectory is not stable across code paths.")
    print(f"  See docs/figures/web/penalty_weight.png and docs/LESSONS.md §1.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m quantum_solar",
        description="Home battery scheduling under time-of-use pricing — "
                    "exact classical solvers, and QAOA. Runs offline from data "
                    "committed to this repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  python -m quantum_solar\n"
               "  python -m quantum_solar --round-trip 0.90 --export-ratio 0.25\n"
               "  python -m quantum_solar --day 17 --day-only\n"
               "  python -m quantum_solar --quantum\n",
    )
    p.add_argument("--capacity", type=float, default=10.0, metavar="KWH",
                   help="battery capacity in kWh (default: 10)")
    p.add_argument("--rate", type=float, default=2.0, metavar="KW",
                   help="charge/discharge rating in kW; must divide the capacity "
                        "(default: 2)")
    p.add_argument("--round-trip", type=float, default=1.0, metavar="EFF",
                   help="AC round-trip efficiency, split evenly across both legs. "
                        "1.0 = lossless, 0.90 is typical (default: 1.0)")
    p.add_argument("--export-ratio", type=float, default=1.0, metavar="R",
                   help="export credit as a fraction of the import price. "
                        "1.0 = full-retail net metering (default: 1.0)")
    p.add_argument("--day", type=int, default=192, metavar="N",
                   help="0-based day of year to plan, AMY 2018 (default: 192, a "
                        "summer weekday)")
    p.add_argument("--day-only", action="store_true",
                   help="just the single-day plan; skip the year and the sizing sweep")
    p.add_argument("--quantum", action="store_true",
                   help="also run QAOA against the exact solvers (needs qiskit)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not 0 <= args.day < 365:
        raise SystemExit("--day must be in 0..364 (AMY 2018 is non-leap)")
    if not 0 < args.round_trip <= 1:
        raise SystemExit("--round-trip must be in (0, 1]")
    if not 0 <= args.export_ratio <= 1:
        raise SystemExit("--export-ratio must be in [0, 1]")

    snap, generation, price_for = _load_snapshot()
    knobs = dict(capacity=args.capacity, rate=args.rate,
                 round_trip=args.round_trip, export_ratio=args.export_ratio)

    print(f"quantum-solar — {snap['location']}, {snap['system_kw']:g} kW PV, "
          f"{args.capacity:g} kWh battery at {args.rate:g} kW")
    losses = "lossless" if args.round_trip == 1 else f"{args.round_trip:g} round trip"
    export = ("net-metered" if args.export_ratio == 1
              else f"export at {args.export_ratio:g}× retail")
    print(f"{losses}, {export} · Xcel RE-TOU tariff, snapshot {snap['snapshot_date']} "
          f"· no network, no API key")

    try:
        problem, dtype = _day_problem(generation, price_for, args.day, **knobs)
        show_day(problem, dtype, args.day)

        if not args.day_only:
            show_year(_annual(generation, price_for, **knobs), **knobs)
            show_sizing(generation, price_for, **knobs)
    except ValueError as exc:
        # require_soc_on_grid: the SoC grid is the GCD of the two energy quanta, so
        # a capacity that is not a multiple of the rate has no exact grid. Rounding
        # it once silently turned a 10 kWh battery into a 12 kWh one.
        raise SystemExit(f"\n{exc}\n\nPick a --rate that divides --capacity exactly.")

    if args.quantum:
        show_quantum(seed=0)

    print("\nFull write-ups: README.md · docs/LESSONS.md · docs/ARCHITECTURE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
