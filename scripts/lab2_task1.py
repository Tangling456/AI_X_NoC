#!/usr/bin/env python3
"""Lab2 Task 1 — latency/throughput of 5 traffic patterns on an 8x8 Mesh.

Runs ``configs/example/garnet_synth_traffic.py`` for:

* traffic      : uniform_random, shuffle, transpose, tornado, neighbor
* injection    : 0.01 .. 0.50 (12 points)
* topology     : Mesh_XY, 8 rows -> 64 nodes
* other params : vnet 0 (1-flit packets), 10000 cycles

Outputs
-------
* ``results/data/lab2_task1.csv``
* ``results/figures/lab2_task1_analysis.png``    (5 metrics side by side:
  packet latency, throughput, hops, network latency, queueing latency)

Usage
-----
::

    python3 lab2_task1.py               # run all 60 sims, then plot
    python3 lab2_task1.py --plot-only   # re-plot from the existing CSV
"""
import sys
from common import *

TRAFFICS = ["uniform_random", "shuffle", "transpose", "tornado", "neighbor"]
RATES = [0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
NUM_CPUS = 64
SIM_CYCLES = 10000

CSV = DATA / "lab2_task1.csv"
RAW_DIR = RAW / "lab2_task1"

STATS = [
    "packets_injected::total",
    "packets_received::total",
    "flits_injected::total",
    "flits_received::total",
    "average_packet_latency",
    "average_flit_latency",
    "average_packet_queueing_latency",
    "average_packet_network_latency",
    "average_hops",
    "avg_link_utilization",
    "avg_vc_load::total",
]
FIELDS = (["traffic", "injection_rate", "returncode"] + STATS
          + ["reception_rate_pkt", "accepted_flits_per_node_cycle"])


def run_experiments():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    total = len(TRAFFICS) * len(RATES)
    done = 0
    for traffic in TRAFFICS:
        for rate in RATES:
            tag = f"{traffic}_rate{rate:g}"
            outdir = RAW_DIR / tag
            rc = run_gem5(outdir, [
                "--network=garnet",
                f"--num-cpus={NUM_CPUS}", f"--num-dirs={NUM_CPUS}",
                "--topology=Mesh_XY", "--mesh-rows=8", "--inj-vnet=0",
                f"--synthetic={traffic}", f"--sim-cycles={SIM_CYCLES}",
                f"--injectionrate={rate}",
            ])
            done += 1
            row = {"traffic": traffic, "injection_rate": rate, "returncode": rc}
            stats_path = Path(outdir) / "stats.txt"
            if rc == 0 and stats_path.exists():
                for s in STATS:
                    row[s] = parse_stat(stats_path, s)
                rx = row.get("packets_received::total")
                fx = row.get("flits_received::total")
                row["reception_rate_pkt"] = (
                    rx / (NUM_CPUS * SIM_CYCLES) if rx is not None else None)
                row["accepted_flits_per_node_cycle"] = (
                    fx / (NUM_CPUS * SIM_CYCLES) if fx is not None else None)
            rows.append(row)
            lat = row.get("average_packet_latency", "N/A")
            print(f"[{done}/{total}] {tag} rc={rc} latency={lat}", flush=True)
    write_csv(CSV, FIELDS, rows)
    print(f"wrote {CSV}")


def _load():
    if not CSV.exists():
        run_experiments()
    return read_csv(CSV)


def plot_figures():
    rows = _load()
    plt = matplotlib_plt()

    by_traffic = {}
    for r in rows:
        if r.get("returncode") == "0":
            by_traffic.setdefault(r["traffic"], []).append(r)
    for t in by_traffic:
        by_traffic[t].sort(key=lambda r: float(r["injection_rate"]))

    markers = ["o", "s", "^", "D", "v"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    def xy(rrows, key):
        xs, ys = [], []
        for r in rrows:
            v = r.get(key)
            if v not in (None, "", "None"):
                xs.append(float(r["injection_rate"]))
                ys.append(float(v))
        return xs, ys

    metrics = [
        ("average_packet_latency", "Average packet latency (cycles)",
         "Latency vs Injection Rate", False),
        ("reception_rate_pkt", "Accepted throughput (packets/node/cycle)",
         "Accepted Throughput vs Injection Rate", True),
        ("average_hops", "Average hops",
         "Average Hops vs Injection Rate", False),
        ("average_packet_network_latency", "Average network latency (cycles)",
         "Network Latency vs Injection Rate", False),
        ("average_packet_queueing_latency", "Average queueing latency (cycles)",
         "Queueing Latency vs Injection Rate", False),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = list(axes.ravel())
    fig.delaxes(axes.pop())  # drop the unused 6th subplot
    for ax, (col, ylabel, caption, ideal) in zip(axes, metrics):
        for i, t in enumerate(TRAFFICS):
            if t in by_traffic:
                xs, ys = xy(by_traffic[t], col)
                ax.plot(xs, ys, marker=markers[i], color=colors[i], label=t)
        if ideal:
            ax.plot([0, 0.5], [0, 0.5], "--", color="gray", lw=1,
                    label="ideal (100% accept)")
        ax.set_xlabel("Injection rate (packets/node/cycle)")
        ax.set_ylabel(ylabel)
        ax.set_title(caption)
        ax.grid(True, alpha=0.3)

    # single shared legend below the three subplots
    handles, labels = [], []
    for ax in axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)
    fig.suptitle("Traffic Patterns Analysis (8x8 Mesh, 10000 cycles)",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0.10, 1, 0.92])
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               fontsize=9, bbox_to_anchor=(0.5, 0.0))
    fig.savefig(FIGURES / "lab2_task1_analysis.png", dpi=150)
    plt.close(fig)
    print("wrote", FIGURES / "lab2_task1_analysis.png")


def main():
    ensure_dirs()
    if "--plot-only" not in sys.argv or not CSV.exists():
        run_experiments()
    plot_figures()


if __name__ == "__main__":
    main()
