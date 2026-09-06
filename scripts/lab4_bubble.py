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
* ``results/lab4_bubble.csv``
* ``results/figures/lab4_bubble_latency_<pattern>.png``
* ``results/figures/lab4_bubble_throughput_<pattern>.png``

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

CSV = RESULTS / "lab4_bubble.csv"
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


def plot_figures():
    rows = _load()
    plt = matplotlib_plt()

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

    # VC count -> (caption label, config keys in that group)
    vc_groups = [
        ("vc1", "VC=1", ["vc1", "vc1_bubble"]),
        ("vc2", "VC=2", ["vc2", "vc2_bubble", "vc2_escape"]),
        ("vc4", "VC=4", ["vc4", "vc4_bubble", "vc4_escape"]),
    ]

    max_rate = max(RATES)

    # 3 traffic patterns x 3 VC counts = 9 figures; each figure: 3 metrics
    for pat in PATTERNS:
        for vc_tag, vc_label, cfg_list in vc_groups:
            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            for ax, (col, ylabel, caption, ideal) in zip(axes, metrics):
                for ci, cfg in enumerate(cfg_list):
                    pts = [(float(r["rate"]), float(r[col]))
                           for r in rows
                           if r["config"] == cfg and r["pattern"] == pat]
                    pts.sort()
                    if pts:
                        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                                marker=markers[ci % len(markers)],
                                color=colors[ci % len(colors)],
                                label=CONFIGS[cfg]["label"])
                        # deadlocked beyond the last surviving rate: no valid
                        # value, so dashed horizontal extension + red X.
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
            fig.suptitle(f"Flow-control Analysis ({vc_label}, {pat}, "
                         f"Ring, 16 nodes, 100000 cycles)", fontsize=13)
            fig.tight_layout(rect=[0, 0.10, 1, 0.92])
            fig.legend(handles, labels, loc="lower center", ncol=len(labels),
                       fontsize=9, bbox_to_anchor=(0.5, 0.0))
            fname = FIGURES / f"lab4_bubble_{pat}_{vc_tag}_analysis.png"
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
