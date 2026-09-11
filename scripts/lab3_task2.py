#!/usr/bin/env python3
"""Lab3 Task 2 — wormhole flow control on the Ring topology.

Compares three flow-control configurations using single-flit traffic
(``--inj-vnet=0``, i.e. HEAD_TAIL flits):

* ``vc1_d1``     : 1 VC,  depth 1  (default credit-based flow control)
* ``vc16_d1``    : 16 VCs, depth 1  (default credit-based flow control)
* ``vc1_d16_wh`` : 1 VC,  depth 16 (``--wormhole``)

Setup: Ring (16 nodes), ring routing (``--routing-algorithm=3``), 100000 cycles.

Outputs
-------
* ``results/data/lab3_task2.csv``
* ``results/figures/lab3_task2_<pattern>_analysis.png``

Usage
-----
::

    python3 lab3_task2.py               # run all sims, then plot
    python3 lab3_task2.py --plot-only   # re-plot from the existing CSV
"""
import sys
from common import *

CONFIGS = {
    "vc1_d1": {"label": "VC=1, Depth=1", "args": ["--vcs-per-vnet=1"]},
    "vc16_d1": {"label": "VC=16, Depth=1", "args": ["--vcs-per-vnet=16"]},
    "vc1_d16_wh": {"label": "VC=1, Depth=16 (wormhole)",
                   "args": ["--vcs-per-vnet=1", "--wormhole"]},
}
PATTERNS = ["uniform_random", "bit_complement", "bit_reverse"]
RATES = [0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7]
NUM_CPUS = 16
SIM_CYCLES = 100000
ROUTING = 3

CSV = DATA / "lab3_task2.csv"
RAW_DIR = RAW / "lab3_task2"

FIELDS = [
    "config", "pattern", "rate",
    "avg_pkt_latency", "avg_flit_latency",
    "avg_flit_network_latency", "avg_flit_queueing_latency",
    "avg_hops", "avg_link_utilization",
    "packets_received", "flits_received", "sim_cycles",
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
                ] + spec["args"])
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
                        "avg_link_utilization": parse_stat(stats_path, "avg_link_utilization"),
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
                    print(f"[{done}/{total}] {tag} rc={rc} (deadlock/skip)", flush=True)
    write_csv(CSV, FIELDS, rows)
    print(f"wrote {CSV}")


def _load():
    if not CSV.exists():
        run_experiments()
    return read_csv(CSV)


def plot_figures():
    rows = _load()
    plt = matplotlib_plt()

    configs_order = list(CONFIGS.keys())
    markers = ["o", "s", "^", "D", "v"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    # (CSV column, y label, subplot caption, draw ideal line)
    metrics = [
        ("avg_pkt_latency", "Average packet latency (cycles)",
         "Latency vs Injection Rate", False),
        ("accepted_flits_per_node_cycle",
         "Accepted throughput (packets/node/cycle)",
         "Accepted Throughput vs Injection Rate", True),
        ("avg_hops", "Average hops",
         "Average Hops vs Injection Rate", False),
    ]

    max_rate = max(RATES)

    # one figure per traffic pattern: three metrics side by side
    for pat in PATTERNS:
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        for ax, (col, ylabel, caption, ideal) in zip(axes, metrics):
            for ci, cfg in enumerate(configs_order):
                pts = [(float(r["rate"]), float(r[col]))
                       for r in rows
                       if r["config"] == cfg and r["pattern"] == pat]
                pts.sort()
                if pts:
                    ax.plot([p[0] for p in pts], [p[1] for p in pts],
                            marker=markers[ci % len(markers)],
                            color=colors[ci % len(colors)],
                            label=CONFIGS[cfg]["label"])
                    # deadlocked beyond the last surviving rate: no valid value,
                    # so extend the line horizontally (dashed) at the last known
                    # value and mark each deadlocked rate with a red X.
                    if pts[-1][0] < max_rate - 1e-9:
                        dl = [r for r in RATES if r > pts[-1][0] + 1e-9]
                        yref = pts[-1][1]
                        ax.plot([pts[-1][0], max_rate], [yref, yref],
                                linestyle="--", lw=1.5,
                                color=colors[ci % len(colors)])
                        ax.scatter(dl, [yref] * len(dl), marker="x",
                                   color="red", s=50, lw=1.5, zorder=5)
            if ideal:
                ax.plot([0, max_rate], [0, max_rate], "--", color="gray",
                        lw=1, label="ideal (100% accept)")
            ax.set_xlabel("Injection rate (packets/node/cycle)")
            ax.set_ylabel(ylabel)
            ax.set_title(caption)
            ax.grid(True, alpha=0.3)

        # single shared legend below the figure (incl. the deadlock marker)
        axes[0].scatter([], [], marker="x", color="red", s=50, lw=1.5,
                        label="deadlock")
        handles, labels = [], []
        for ax in axes:
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels:
                    handles.append(h)
                    labels.append(l)
        fig.suptitle(f"Flow-control Analysis ({pat}, Ring, 16 nodes, "
                     f"100000 cycles)", fontsize=13)
        fig.tight_layout(rect=[0, 0.10, 1, 0.92])
        fig.legend(handles, labels, loc="lower center", ncol=len(labels),
                   fontsize=9, bbox_to_anchor=(0.5, 0.0))
        fname = FIGURES / f"lab3_task2_{pat}_analysis.png"
        fig.savefig(fname, dpi=150)
        plt.close(fig)
        print("wrote", fname)


def main():
    ensure_dirs()
    if "--plot-only" not in sys.argv or not CSV.exists():
        run_experiments()
    plot_figures()


if __name__ == "__main__":
    main()
