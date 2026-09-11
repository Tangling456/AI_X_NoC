#!/usr/bin/env python3
"""Lab3 Task 1 — Ring (1D-torus) topology with the ring routing algorithm.

Runs synthetic traffic on a 16-node Ring topology with the custom ring routing
(``--routing-algorithm=3``):

* patterns : uniform_random, bit_complement, bit_reverse
* rates    : 0.02 .. 0.7 (11 points)
* cycles   : 100000

The 1-VC-class ring has a wrap-around cyclic dependency, so high injection
rates deadlock.  Deadlocked runs are detected from the gem5 stderr log and
marked on the plots.

Outputs
-------
* ``results/data/lab3_task1.csv``
* ``results/figures/lab3_task1_analysis.png`` (latency / hops / link-utilization panels)

Usage
-----
::

    python3 lab3_task1.py               # run all sims, then plot
    python3 lab3_task1.py --plot-only   # re-plot from the existing CSV
"""
import sys
from common import *

PATTERNS = ["uniform_random", "bit_complement", "bit_reverse"]
RATES = [0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7]
NUM_CPUS = 16
SIM_CYCLES = 100000
ROUTING = 3  # ring routing (outportComputeRing)

CSV = DATA / "lab3_task1.csv"
RAW_DIR = RAW / "lab3_task1"

FIELDS = [
    "pattern", "rate",
    "avg_pkt_latency", "avg_flit_latency",
    "avg_flit_network_latency", "avg_flit_queueing_latency",
    "avg_hops", "avg_link_utilization",
    "packets_received", "flits_received", "sim_cycles", "deadlocked",
]


def run_experiments():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    total = len(PATTERNS) * len(RATES)
    done = 0
    for pat in PATTERNS:
        for rate in RATES:
            tag = f"algo{ROUTING}_{pat}_{rate:g}"
            outdir = RAW_DIR / tag
            rc = run_gem5(outdir, [
                f"--num-cpus={NUM_CPUS}", f"--num-dirs={NUM_CPUS}",
                "--network=garnet", "--topology=Ring",
                f"--routing-algorithm={ROUTING}",
                f"--synthetic={pat}", f"--injectionrate={rate}",
                "--inj-vnet=0",
                f"--sim-cycles={SIM_CYCLES}",
            ])
            done += 1
            stats_path = Path(outdir) / "stats.txt"
            ok = rc == 0 and stats_path.exists()
            row = {
                "pattern": pat, "rate": rate,
                "avg_pkt_latency": None, "avg_flit_latency": None,
                "avg_flit_network_latency": None,
                "avg_flit_queueing_latency": None,
                "avg_hops": None, "avg_link_utilization": None,
                "packets_received": None, "flits_received": None,
                "sim_cycles": 0, "deadlocked": 0,
            }
            if ok:
                row["avg_pkt_latency"] = parse_stat(stats_path, "average_packet_latency")
                row["avg_flit_latency"] = parse_stat(stats_path, "average_flit_latency")
                row["avg_flit_network_latency"] = parse_stat(
                    stats_path, "average_flit_network_latency")
                row["avg_flit_queueing_latency"] = parse_stat(
                    stats_path, "average_flit_queueing_latency")
                row["avg_hops"] = parse_stat(stats_path, "average_hops")
                row["avg_link_utilization"] = parse_stat(stats_path, "avg_link_utilization")
                row["packets_received"] = parse_stat(stats_path, "packets_received")
                row["flits_received"] = parse_stat(stats_path, "flits_received")
                row["sim_cycles"] = parse_sim_ticks(stats_path)
            if not ok and deadlocked(outdir):
                row["deadlocked"] = 1
            rows.append(row)
            lat = row.get("avg_flit_latency", "N/A")
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

    style = {
        "uniform_random": dict(color="tab:blue", marker="o", label="uniform_random"),
        "bit_complement": dict(color="tab:green", marker="s", label="bit_complement"),
        "bit_reverse": dict(color="tab:orange", marker="^", label="bit_reverse"),
    }

    data = {}
    for p in PATTERNS:
        data[p] = {k: [] for k in
                   ["rate", "pkt_lat", "hops", "util", "deadlock"]}
        for r in rows:
            if r["pattern"] != p:
                continue
            rate = float(r["rate"])
            if int(float(r.get("deadlocked") or 0)):
                data[p]["deadlock"].append(rate)
                continue
            if r.get("avg_pkt_latency") in (None, "", "None"):
                continue
            data[p]["rate"].append(rate)
            data[p]["pkt_lat"].append(float(r["avg_pkt_latency"]))
            data[p]["hops"].append(float(r["avg_hops"] or 0))
            data[p]["util"].append(float(r["avg_link_utilization"] or 0))

    # (metric key, y label, subplot caption)
    panels = [
        ("pkt_lat", "Average packet latency (cycles)",
         "Latency vs Injection Rate"),
        ("hops", "Average hops", "Average Hops vs Injection Rate"),
        ("util", "Average link utilization", "Link Utilization vs Injection Rate"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    def draw(ax, key):
        for p in PATTERNS:
            d = data[p]
            s = style[p]
            ax.plot(d["rate"], d[key], marker=s["marker"], color=s["color"],
                    ms=6, label=s["label"])
            dl = sorted(d["deadlock"])
            if dl and d["rate"]:
                yref = d[key][-1]
                # after deadlock: markers become red X; the dashed line keeps
                # the pattern colour and extends from the last valid point
                ax.plot([d["rate"][-1]] + dl, [yref] * (len(dl) + 1),
                        color=s["color"], linestyle="--", lw=1.5, zorder=4)
                ax.scatter(dl, [yref] * len(dl), marker="x", color="red",
                           s=50, lw=1.5, zorder=5)

    for ax, (key, ylabel, caption) in zip(axes, panels):
        draw(ax, key)
        ax.set_xlabel("Injection rate (packets/node/cycle)")
        ax.set_ylabel(ylabel)
        ax.set_title(caption)
        ax.grid(True, alpha=0.3)

    # latency spans several orders of magnitude -> log scale
    axes[0].set_yscale("log")

    # single shared legend below the figure (incl. the deadlock marker)
    axes[0].scatter([], [], marker="x", color="red", s=50, lw=1.5, label="deadlock")
    handles, labels = [], []
    for ax in axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)
    fig.suptitle("Traffic-pattern Analysis on Ring (16 nodes, 100000 cycles)",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0.10, 1, 0.92])
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               fontsize=9, bbox_to_anchor=(0.5, 0.0))
    fig.savefig(FIGURES / "lab3_task1_analysis.png", dpi=160)
    plt.close(fig)
    print("wrote", FIGURES / "lab3_task1_analysis.png")

    # textual summary
    print("\nDeadlock onset (first deadlocked injection rate):")
    for p in PATTERNS:
        d = data[p]
        if d["deadlock"]:
            print(f"  {p:16s} deadlocks at rate >= {min(d['deadlock'])}")
        else:
            print(f"  {p:16s} no deadlock up to {max(RATES)}")


def main():
    ensure_dirs()
    if "--plot-only" not in sys.argv or not CSV.exists():
        run_experiments()
    plot_figures()


if __name__ == "__main__":
    main()
