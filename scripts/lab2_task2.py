#!/usr/bin/env python3
"""Lab2 Task 2 — parameter sensitivity on the 8x8 Mesh.

Baseline: uniform_random, Mesh_XY (64 nodes), vnet 0, 10000 cycles.
Sweeps one parameter at a time over the injection-rate range 0.01 .. 0.50:

* ``--vcs-per-vnet``   : 1, 2, 4, 8
* ``--router-latency`` : 1, 2, 4
* ``--link-width-bits``: 32, 64, 128, 256

Outputs
-------
* ``results/lab2_task2.csv``
* ``results/figures/lab2_task2_vcs_latency.png``
* ``results/figures/lab2_task2_vcs_throughput.png``
* ``results/figures/lab2_task2_router_latency.png``
* ``results/figures/lab2_task2_linkwidth_latency.png``

Usage
-----
::

    python3 lab2_task2.py               # run all sims, then plot
    python3 lab2_task2.py --plot-only   # re-plot from the existing CSV
"""
import sys
from common import *

TRAFFIC = "uniform_random"
RATES = [0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
NUM_CPUS = 64
SIM_CYCLES = 10000

# (group name, CLI flag, values)
GROUPS = [
    ("vcs-per-vnet", "--vcs-per-vnet", [1, 2, 4, 8]),
    ("router-latency", "--router-latency", [1, 2, 4]),
    ("link-width-bits", "--link-width-bits", [32, 64, 128, 256]),
]

CSV = RESULTS / "lab2_task2.csv"
RAW_DIR = RAW / "lab2_task2"

STATS = [
    "packets_received::total",
    "average_packet_latency",
    "average_packet_queueing_latency",
    "average_packet_network_latency",
    "average_hops",
]
FIELDS = (["group", "param_value", "injection_rate", "returncode"]
          + STATS + ["reception_rate_pkt"])


def run_experiments():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    total = sum(len(vals) for _, _, vals in GROUPS) * len(RATES)
    done = 0
    for group, flag, values in GROUPS:
        for val in values:
            for rate in RATES:
                tag = f"{group}_{val}_rate{rate:g}"
                outdir = RAW_DIR / tag
                rc = run_gem5(outdir, [
                    "--network=garnet",
                    f"--num-cpus={NUM_CPUS}", f"--num-dirs={NUM_CPUS}",
                    "--topology=Mesh_XY", "--mesh-rows=8", "--inj-vnet=0",
                    f"--synthetic={TRAFFIC}", f"--sim-cycles={SIM_CYCLES}",
                    f"{flag}={val}", f"--injectionrate={rate}",
                ])
                done += 1
                row = {"group": group, "param_value": val,
                       "injection_rate": rate, "returncode": rc}
                stats_path = Path(outdir) / "stats.txt"
                if rc == 0 and stats_path.exists():
                    for s in STATS:
                        row[s] = parse_stat(stats_path, s)
                    rx = row.get("packets_received::total")
                    row["reception_rate_pkt"] = (
                        rx / (NUM_CPUS * SIM_CYCLES) if rx is not None else None)
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

    groups = {}
    for r in rows:
        if r.get("returncode") != "0":
            continue
        v = int(float(r["param_value"]))
        groups.setdefault(r["group"], {}).setdefault(v, []).append(r)
    for g in groups:
        for v in groups[g]:
            groups[g][v].sort(key=lambda r: float(r["injection_rate"]))

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

    group_unit = {
        "vcs-per-vnet": "VCs/vnet",
        "router-latency": "cycles",
        "link-width-bits": "bits",
    }
    group_short = {
        "vcs-per-vnet": "vcs",
        "router-latency": "router",
        "link-width-bits": "linkwidth",
    }
    # (CSV column, y label, subplot caption, draw ideal line)
    metrics = [
        ("average_packet_latency", "Average packet latency (cycles)",
         "Latency vs Injection Rate", False),
        ("reception_rate_pkt", "Accepted throughput (packets/node/cycle)",
         "Accepted Throughput vs Injection Rate", True),
        ("average_hops", "Average hops",
         "Average Hops vs Injection Rate", False),
    ]

    # One figure per parameter group: the 3 metrics plotted side by side.
    # Main caption: "<group> Analysis (uniform_random, 8x8 Mesh, 10000 cycles)".
    for g in ["vcs-per-vnet", "router-latency", "link-width-bits"]:
        if g not in groups:
            continue
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        for ax, (col, ylabel, caption, ideal) in zip(axes, metrics):
            for vi, v in enumerate(sorted(groups[g])):
                xs, ys = xy(groups[g][v], col)
                ax.plot(xs, ys, marker=markers[vi % len(markers)],
                        color=colors[vi % len(colors)],
                        label=f"{v} {group_unit[g]}")
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
        fig.suptitle(f"{g.capitalize()} Analysis "
                     f"(uniform_random, 8x8 Mesh, 10000 cycles)", fontsize=13)
        fig.tight_layout(rect=[0, 0.10, 1, 0.92])
        fig.legend(handles, labels, loc="lower center", ncol=len(labels),
                   fontsize=9, bbox_to_anchor=(0.5, 0.0))
        fname = f"lab2_task2_{group_short[g]}_analysis.png"
        fig.savefig(FIGURES / fname, dpi=150)
        plt.close(fig)
        print("wrote", FIGURES / fname)


def main():
    ensure_dirs()
    if "--plot-only" not in sys.argv or not CSV.exists():
        run_experiments()
    plot_figures()


if __name__ == "__main__":
    main()
