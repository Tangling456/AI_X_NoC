#!/usr/bin/env python3
"""Lab4 — Bubble flow-control experiment on the Ring topology.

Compares, for every (traffic pattern x injection rate):

* naive baselines (no escape VC, no bubble): ``vc1``, ``vc2``, ``vc4``
* bubble flow control (``--bubble``): ``vc1_bubble``, ``vc2_bubble``, ``vc4_bubble``
* escape VC (the other Lab4 technique): ``vc2_escape``, ``vc4_escape``

All runs use single-flit traffic (``--inj-vnet=0``) and the adaptive
shortest-path ring routing (``--routing-algorithm=3``).  Escape VCs are disabled
for the naive/bubble configs so the adaptive-routing deadlock is exposed.
Deadlocked / timed-out runs are skipped (they have no stats).

Outputs
-------
* ``results/data/lab4_bubble.csv``
* ``results/figures/lab4_bubble_{vc1,vc2,vc4}_analysis.png`` — one
  integrated 3x3 grid per VC group (rows: traffic patterns, columns:
  latency / accepted throughput / average hops); the layout follows
  ``generate_bubble_figures.py`` (repo root).

Usage
-----
::

    python3 lab4_bubble.py               # run all sims, then plot
    python3 lab4_bubble.py --plot-only   # re-plot from the existing CSV
"""
import sys
from common import *

CONFIGS = {
    "vc1": {"label": "VC=1 (naive)",
            "args": ["--vcs-per-vnet=1", "--escape-vc-per-vnet=0"]},
    "vc1_bubble": {"label": "VC=1 + bubble",
                   "args": ["--vcs-per-vnet=1", "--escape-vc-per-vnet=0", "--bubble"]},
    "vc2": {"label": "VC=2 (naive)",
            "args": ["--vcs-per-vnet=2", "--escape-vc-per-vnet=0"]},
    "vc2_bubble": {"label": "VC=2 + bubble",
                   "args": ["--vcs-per-vnet=2", "--escape-vc-per-vnet=0", "--bubble"]},
    "vc2_escape": {"label": "VC=2 (1+1 escape)",
                   "args": ["--vcs-per-vnet=2", "--escape-vc-per-vnet=1"]},
    "vc4": {"label": "VC=4 (naive)",
            "args": ["--vcs-per-vnet=4", "--escape-vc-per-vnet=0"]},
    "vc4_bubble": {"label": "VC=4 + bubble",
                   "args": ["--vcs-per-vnet=4", "--escape-vc-per-vnet=0", "--bubble"]},
    "vc4_escape": {"label": "VC=4 (3+1 escape)",
                   "args": ["--vcs-per-vnet=4", "--escape-vc-per-vnet=1"]},
}
PATTERNS = ["uniform_random", "bit_complement", "bit_reverse"]
RATES = [0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7]
NUM_CPUS = 16
SIM_CYCLES = 100000
ROUTING = 3
TIMEOUT = 180

CSV = DATA / "lab4_bubble.csv"
RAW_DIR = RAW / "lab4_bubble"

FIELDS = [
    "config", "pattern", "rate",
    "avg_pkt_latency", "avg_flit_latency",
    "avg_flit_network_latency", "avg_flit_queueing_latency",
    "avg_hops", "packets_received", "flits_received", "sim_cycles",
    "accepted_flits_per_node_cycle",
]


def run_experiments():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    total = len(CONFIGS) * len(PATTERNS) * len(RATES)
    done = 0
    for cfg, spec in CONFIGS.items():
        for pat in PATTERNS:
            for rate in RATES:
                tag = f"{cfg}_{pat}_{rate:g}"
                outdir = RAW_DIR / tag
                rc = run_gem5(outdir, [
                    f"--num-cpus={NUM_CPUS}", f"--num-dirs={NUM_CPUS}",
                    "--network=garnet", "--topology=Ring",
                    f"--routing-algorithm={ROUTING}",
                    f"--synthetic={pat}", f"--injectionrate={rate}",
                    "--inj-vnet=0", f"--sim-cycles={SIM_CYCLES}",
                ] + spec["args"], timeout=TIMEOUT)
                done += 1
                stats_path = Path(outdir) / "stats.txt"
                if rc == 0 and stats_path.exists():
                    flits = parse_stat(stats_path, "flits_received")
                    cycles = parse_sim_ticks(stats_path)
                    row = {
                        "config": cfg, "pattern": pat, "rate": rate,
                        "avg_pkt_latency": parse_stat(stats_path, "average_packet_latency"),
                        "avg_flit_latency": parse_stat(stats_path, "average_flit_latency"),
                        "avg_flit_network_latency": parse_stat(
                            stats_path, "average_flit_network_latency"),
                        "avg_flit_queueing_latency": parse_stat(
                            stats_path, "average_flit_queueing_latency"),
                        "avg_hops": parse_stat(stats_path, "average_hops"),
                        "packets_received": parse_stat(stats_path, "packets_received"),
                        "flits_received": flits,
                        "sim_cycles": cycles,
                        "accepted_flits_per_node_cycle": (
                            flits / (cycles * NUM_CPUS)
                            if (flits is not None and cycles) else None),
                    }
                    rows.append(row)
                    lat = row.get("avg_flit_latency", "N/A")
                    print(f"[{done}/{total}] {tag} rc={rc} latency={lat}", flush=True)
                else:
                    print(f"[{done}/{total}] {tag} rc={rc} (deadlock/timeout, skip)",
                          flush=True)
    write_csv(CSV, FIELDS, rows)
    print(f"wrote {CSV}")


def _load():
    if not CSV.exists():
        run_experiments()
    return read_csv(CSV)


# ---------------------------------------------------------------------------
# Plotting.  The layout follows ``generate_bubble_figures.py`` (repo root):
# one integrated 3x3 grid per VC group, rows = traffic patterns, columns =
# latency / accepted throughput / average hops.  Figures are still written
# into ``results/figures/``.
# ---------------------------------------------------------------------------
# Row order (top -> bottom) of the pattern dimension in every figure.
FIG_PATTERNS = ["bit_complement", "bit_reverse", "uniform_random"]

MARKERS = ["o", "s", "^", "D", "v"]
COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

# (CSV column, subplot caption, y label, draw ideal line)
METRICS = [
    ("avg_pkt_latency",
     "Latency vs Injection Rate",
     "Average packet latency (cycles)", False),
    ("accepted_flits_per_node_cycle",
     "Accepted Throughput vs Injection Rate",
     "Accepted throughput (packets/node/cycle)", True),
    ("avg_hops",
     "Average Hops vs Injection Rate",
     "Average hops", False),
]

# (figure tag, VC label, configs drawn in that figure)
VC_GROUPS = [
    ("vc1", "VC=1", ["vc1", "vc1_bubble"]),
    ("vc2", "VC=2", ["vc2", "vc2_bubble", "vc2_escape"]),
    ("vc4", "VC=4", ["vc4", "vc4_bubble", "vc4_escape"]),
]


def _points(rows, field):
    """[(rate, value), ...] for a (config, pattern) subset, sorted by rate."""
    pts = []
    for r in rows:
        try:
            x, y = float(r["rate"]), float(r[field])
        except (KeyError, TypeError, ValueError):
            continue
        pts.append((x, y))
    pts.sort()
    return pts


def _plot_vc_group(plt, rows, cfg_list, vc_label, out_path, dpi):
    """Draw one 3x3 grid (rows: patterns, columns: metrics) and save it."""
    from matplotlib.lines import Line2D

    max_rate = max(RATES)
    fig, axes = plt.subplots(3, 3, figsize=(15.5, 11.5))
    used_deadlock = False

    for row, pat in enumerate(FIG_PATTERNS):
        for col, (field, caption, ylabel, ideal) in enumerate(METRICS):
            ax = axes[row][col]

            for ci, cfg in enumerate(cfg_list):
                pts = _points([r for r in rows
                               if r["config"] == cfg
                               and r["pattern"] == pat], field)
                if not pts:
                    continue
                color = COLORS[ci % len(COLORS)]
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        marker=MARKERS[ci % len(MARKERS)], ms=4.5, lw=1.4,
                        color=color, label=CONFIGS[cfg]["label"])
                # Runs beyond the last surviving rate are deadlocked/timed
                # out (no stats): dashed extension + red X at skipped rates.
                if pts[-1][0] < max_rate - 1e-9:
                    used_deadlock = True
                    skipped = [q for q in RATES if q > pts[-1][0] + 1e-9]
                    yref = pts[-1][1]
                    ax.plot([pts[-1][0], max_rate], [yref, yref],
                            linestyle="--", lw=1.4, color=color)
                    ax.scatter(skipped, [yref] * len(skipped), marker="x",
                               color="red", s=42, lw=1.4, zorder=5)

            if ideal:
                ax.plot([0, max_rate], [0, max_rate], "--", color="gray",
                        lw=1.0, label="ideal (100% accept)")

            ax.set_xlim(0, max_rate * 1.03)
            if row == 2:
                ax.set_xlabel("Injection rate (packets/node/cycle)",
                              fontsize=9)
            ax.set_ylabel(ylabel, fontsize=9)
            if row == 0:
                ax.set_title(caption, fontsize=11.5)
            ax.grid(True, alpha=0.3)
            ax.tick_params(labelsize=9)

    # Proxy handle for the shared legend (only if some run died).
    if used_deadlock:
        axes[0][0].scatter([], [], marker="x", color="red", s=42, lw=1.4,
                           label="deadlock / timeout (run skipped)")

    # One shared legend below the grid.
    handles, labels = [], []
    for ax in axes.flat:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)

    fig.suptitle(f"Flow-control Analysis ({vc_label}, Ring, 16 nodes, "
                 f"100000 cycles)", fontsize=14)
    fig.subplots_adjust(left=0.115, right=0.985, top=0.925, bottom=0.10,
                        hspace=0.42, wspace=0.30)

    # Row headers (traffic pattern), rotated on the left of each row.
    for row, pat in enumerate(FIG_PATTERNS):
        pos = axes[row][0].get_position()
        fig.text(pos.x0 - 0.075, (pos.y0 + pos.y1) / 2.0, pat,
                 rotation=90, ha="center", va="center",
                 fontsize=12, fontweight="bold", color="#333333")

    # Explicit separator line between the traffic-pattern rows.
    for row in range(1, len(FIG_PATTERNS)):
        y_lo = axes[row][0].get_position().y1
        y_hi = axes[row - 1][0].get_position().y0
        y_sep = (y_lo + y_hi) / 2.0
        fig.add_artist(Line2D([0.025, 0.985], [y_sep, y_sep],
                              transform=fig.transFigure,
                              color="#777777", lw=1.1))

    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               fontsize=10, bbox_to_anchor=(0.5, 0.005), framealpha=0.9)

    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


def plot_figures():
    rows = _load()
    plt = matplotlib_plt()
    for vc_tag, vc_label, cfg_list in VC_GROUPS:
        out = FIGURES / f"lab4_bubble_{vc_tag}_analysis.png"
        _plot_vc_group(plt, rows, cfg_list, vc_label, out, dpi=150)
        print("wrote", out)


def main():
    ensure_dirs()
    if "--plot-only" not in sys.argv or not CSV.exists():
        run_experiments()
    plot_figures()


if __name__ == "__main__":
    main()
