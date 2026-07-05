"""Plotting helpers for battery schedules (matplotlib imported lazily)."""

from __future__ import annotations

import numpy as np

from .problem import BatteryProblem
from .solution import Solution


def plot_schedule(problem: BatteryProblem, solution: Solution):
    """Plot price/load/solar and the resulting battery schedule + SoC.

    Returns the matplotlib ``Figure``.
    """
    import matplotlib.pyplot as plt

    c, d = problem.decode(solution.x)
    t = problem.num_slots
    hours = (np.arange(t) + 0.5) * 24.0 / t
    width = 0.8 * 24.0 / t
    soc = problem.soc_trajectory(c, d)

    fig, (ax_top, ax_bot) = plt.subplots(2, 1, sharex=True, figsize=(9, 6))

    # Top: time-of-use price (left axis) with load and solar (right axis).
    ax_top.plot(hours, problem.price, color="C3", marker="o", label="price")
    ax_top.set_ylabel("price ($/kWh)", color="C3")
    ax_top.tick_params(axis="y", labelcolor="C3")
    ax_energy = ax_top.twinx()
    ax_energy.plot(hours, problem.load, color="C0", label="load")
    ax_energy.plot(hours, problem.generation, color="C1", label="solar")
    ax_energy.set_ylabel("energy (kWh)")
    ax_energy.legend(loc="upper left", fontsize=8)
    ax_top.set_title("Time-of-use price, household load, and solar generation")

    # Bottom: battery action bars (charge +, discharge −) with SoC overlaid.
    action = problem.charge_energy * c - problem.discharge_energy * d
    colors = ["C2" if a > 0 else "C3" if a < 0 else "0.75" for a in action]
    ax_bot.bar(hours, action, width=width, color=colors)
    ax_bot.axhline(0.0, color="0.5", lw=0.6)
    ax_bot.set_ylabel("charge (+) / discharge (−) kWh")
    ax_soc = ax_bot.twinx()
    ax_soc.plot(hours, soc, color="k", marker=".", label="SoC")
    ax_soc.axhline(problem.capacity, ls="--", color="0.5", lw=0.8)
    ax_soc.set_ylim(-0.05 * problem.capacity, 1.15 * problem.capacity)
    ax_soc.set_ylabel("state of charge (kWh)")
    ax_bot.set_xlabel("hour of day")
    ax_bot.set_title(f"Optimal battery schedule — daily cost ${solution.true_energy:.2f}")

    fig.tight_layout()
    return fig
