#!/usr/bin/env python3
"""Lab4 — Ring (1D-torus) Escape-VC experiment.

Sweeps the number of escape VCs on the Ring topology with adaptive
shortest-path routing (``--routing-algorithm=3``).  Total VCs per vnet is fixed
at 4; the rest are adaptive VCs.

* escape VCs : 0 (pure adaptive baseline) .. 4 (all escape)
* traffic    : uniform_random
* rates      : 0.05 .. 0.70
* cycles     : 100000

Deadlock handling: runs that panic are re-run as a short probe
(``sim-cycles=49000``, just below the 50000-cycle deadlock threshold).  A probe
throughput below 2.5 flits/cycle means the adaptive VCs collapsed (true
deadlock); a higher value means the network was merely saturated.

Outputs
-------
* ``results/data/lab4_escape.csv``
* ``results/figures/lab4_escape_injvnet-1_analysis.png``  (inj-vnet=-1, mixed vnets)
* ``results/figures/lab4_escape_injvnet0_analysis.png``  (inj-vnet=0, 1-flit)

Usage
-----
::

    python3 lab4_escape.py               # run all sims, then plot
    python3 lab4_escape.py --plot-only   # re-plot from the existing CSV
"""
import sys
from common import *

ESCAPE_VCS = [0, 1, 2, 3, 4]
RATES = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.70]
NUM_CPUS = 16
SIM_CYCLES = 100000
PROBE_CYCLES = 49000
ROUTING = 3
VCS_PER_VNET = 4
TRAFFIC = "uniform_random"
TRUE_DEADLOCK_THR = 2.5  # flits/cycle

# (inj_vnet value, raw-dir tag suffix, caption label, output figure filename)
INJ_VNETS = [
    (-1, "", "inj-vnet=-1 (mixed)", "lab4_escape_injvnet-1_analysis.png"),
    (0, "_vnet0", "inj-vnet=0 (1-flit)", "lab4_escape_injvnet0_analysis.png"),
]

CSV = DATA / "lab4_escape.csv"
RAW_DIR = RAW / "lab4_escape"

FIELDS = [
    "inj_vnet", "escape", "rate",
    "avg_flit_latency", "avg_flit_network_latency", "avg_flit_queueing_latency",
    "avg_hops", "flits_received", "throughput", "escaped_flits",
    "deadlock", "deadlock_type",
    "probe_flits_received", "probe_throughput",
    "probe_avg_flit_latency", "probe_avg_hops", "probe_escaped_flits",
]


def _base_args(escape, cycles, inj_vnet):
    return [
        f"--num-cpus={NUM_CPUS}", f"--num-dirs={NUM_CPUS}",
        "--network=garnet", "--topology=Ring", f"--routing-algorithm={ROUTING}",
        f"--vcs-per-vnet={VCS_PER_VNET}", f"--escape-vc-per-vnet={escape}",
        f"--synthetic={TRAFFIC}", f"--inj-vnet={inj_vnet}",
        f"--sim-cycles={cycles}",
    ]


def run_experiments():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    total = len(INJ_VNETS) * len(ESCAPE_VCS) * len(RATES)
    done = 0
    for inj_vnet, suffix, _caption, _fname in INJ_VNETS:
        for escape in ESCAPE_VCS:
            for rate in RATES:
                tag = f"escape{escape}{suffix}_rate{rate:.2f}"
                outdir = RAW_DIR / tag
                rc = run_gem5(outdir, _base_args(escape, SIM_CYCLES, inj_vnet)
                              + [f"--injectionrate={rate}"])
                done += 1
                stats_path = Path(outdir) / "stats.txt"

                if rc == 0 and stats_path.exists():
                    flits = parse_stat(stats_path, "flits_received")
                    cycles = parse_sim_ticks(stats_path)
                    row = {
                        "inj_vnet": inj_vnet, "escape": escape, "rate": rate,
                    "avg_flit_latency": parse_stat(stats_path, "average_flit_latency"),
                    "avg_flit_network_latency": parse_stat(
                        stats_path, "average_flit_network_latency"),
                    "avg_flit_queueing_latency": parse_stat(
                        stats_path, "average_flit_queueing_latency"),
                    "avg_hops": parse_stat(stats_path, "average_hops"),
                    "flits_received": flits,
                    "throughput": (flits / cycles) if (flits is not None and cycles) else 0.0,
                    "escaped_flits": sum_stat(stats_path, "escaped_flits"),
                    "deadlock": 0, "deadlock_type": "none",
                    "probe_flits_received": "", "probe_throughput": "",
                    "probe_avg_flit_latency": "", "probe_avg_hops": "",
                    "probe_escaped_flits": "",
                    }
                    rows.append(row)
                    print(f"[{done}/{total}] {tag} rc={rc} lat="
                          f"{row['avg_flit_latency']}", flush=True)
                else:
                    # Panicked: run a short probe to classify true vs pseudo deadlock.
                    probe_dir = RAW_DIR / f"{tag}_probe"
                    run_gem5(probe_dir, _base_args(escape, PROBE_CYCLES, inj_vnet)
                             + [f"--injectionrate={rate}"], timeout=600)
                    pstats = Path(probe_dir) / "stats.txt"
                    pflits = 0.0
                    pcycles = 0.0
                    plat = None
                    phops = None
                    pesc = 0.0
                    if pstats.exists():
                        pflits = parse_stat(pstats, "flits_received") or 0.0
                        pcycles = parse_sim_ticks(pstats)
                        plat = parse_stat(pstats, "average_flit_latency")
                        phops = parse_stat(pstats, "average_hops")
                        pesc = sum_stat(pstats, "escaped_flits")
                    pthr = (pflits / pcycles) if pcycles else 0.0
                    dtype = "collapsed" if pthr < TRUE_DEADLOCK_THR else "saturated"
                    row = {
                        "inj_vnet": inj_vnet, "escape": escape, "rate": rate,
                        "avg_flit_latency": None, "avg_flit_network_latency": None,
                        "avg_flit_queueing_latency": None, "avg_hops": None,
                        "flits_received": 0, "throughput": 0.0,
                        "escaped_flits": 0,
                        "deadlock": 1, "deadlock_type": dtype,
                        "probe_flits_received": pflits,
                        "probe_throughput": round(pthr, 4),
                        "probe_avg_flit_latency": plat,
                        "probe_avg_hops": phops,
                        "probe_escaped_flits": pesc,
                    }
                    rows.append(row)
                    print(f"[{done}/{total}] {tag} rc={rc} -> {dtype} "
                          f"(probe thr={pthr:.4f})", flush=True)
    write_csv(CSV, FIELDS, rows)
    print(f"wrote {CSV}")


def _load():
    if not CSV.exists():
        run_experiments()
    return read_csv(CSV)


def plot_figures():
    rows = _load()
    plt = matplotlib_plt()
    for inj_vnet, _suffix, caption_label, fname in INJ_VNETS:
        sub = [r for r in rows if str(r.get("inj_vnet")) == str(inj_vnet)]
        if not sub:
            continue
        _plot_one(plt, sub, caption_label, fname)


def _plot_one(plt, rows, caption_label, fname):
    style = {
        0: dict(color="tab:red", marker="o", label="escape=0 (adaptive)"),
        1: dict(color="tab:blue", marker="s", label="escape=1"),
        2: dict(color="tab:green", marker="^", label="escape=2"),
        3: dict(color="tab:orange", marker="D", label="escape=3"),
        4: dict(color="tab:purple", marker="v", label="escape=4 (all escape)"),
    }

    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    data = {e: {"rate": [], "lat": [], "thr": [], "esc": [], "hops": [],
                "collapsed": [], "saturated": [], "probe": {}}
            for e in ESCAPE_VCS}
    for r in rows:
        e = int(float(r["escape"]))
        rate = float(r["rate"])
        d = data[e]
        if int(float(r["deadlock"] or 0)):
            if r["deadlock_type"] == "collapsed":
                d["collapsed"].append(rate)
            else:
                d["saturated"].append(rate)
            d["probe"][rate] = {
                "lat": _f(r.get("probe_avg_flit_latency")),
                "hops": _f(r.get("probe_avg_hops")),
                "esc": _f(r.get("probe_escaped_flits")),
                "thr": _f(r.get("probe_throughput")),
            }
        else:
            if r.get("avg_flit_latency") in (None, "", "None"):
                continue
            d["rate"].append(rate)
            d["lat"].append(float(r["avg_flit_latency"]))
            d["thr"].append(float(r["throughput"]))
            d["esc"].append(float(r["escaped_flits"]))
            d["hops"].append(float(r["avg_hops"] or 0))

    def draw(ax, key):
        for e in ESCAPE_VCS:
            d = data[e]
            s = style[e]
            valid = {r: v for r, v in zip(d["rate"], d[key])}
            last_y = d[key][-1] if d["rate"] else None
            collapsed_set = set(d["collapsed"])
            saturated_set = set(d["saturated"])

            # ordered (rate, y, kind) sequence
            pts = []
            for rate in RATES:
                if rate in valid:
                    pts.append((rate, valid[rate], "valid"))
                elif rate in saturated_set:
                    pv = d["probe"].get(rate, {}).get(key)
                    if pv is not None:
                        pts.append((rate, pv, "saturated"))
                elif rate in collapsed_set:
                    if last_y is not None:
                        pts.append((rate, last_y, "collapsed"))
            if not pts:
                continue

            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]

            # dashed line (config colour) through the full sequence
            ax.plot(xs, ys, linestyle="--", lw=1.2, color=s["color"], zorder=3)

            # solid segments only between consecutive valid points
            prev = None
            for (rate, y, kind) in pts:
                if kind == "valid":
                    if prev is not None:
                        ax.plot([prev[0], rate], [prev[1], y], linestyle="-",
                                color=s["color"], lw=1.5, zorder=4)
                    prev = (rate, y)
                else:
                    prev = None

            # valid markers (carry the legend label)
            vx = [p[0] for p in pts if p[2] == "valid"]
            vy = [p[1] for p in pts if p[2] == "valid"]
            if vx:
                ax.scatter(vx, vy, marker=s["marker"], color=s["color"],
                           s=36, label=s["label"], zorder=4)

            # panicked markers: saturated -> grey hollow circle (probe value),
            # collapsed -> red X (last valid value)
            for (rate, y, kind) in pts:
                if kind == "saturated":
                    ax.scatter(rate, y, marker="o", facecolor="none",
                               edgecolor="gray", s=40, zorder=5)
                elif kind == "collapsed":
                    ax.scatter(rate, y, marker="x", color="red", s=50,
                               lw=1.5, zorder=5)

    panels = [
        ("lat", "Average flit latency (cycles)", "Latency vs Injection Rate"),
        ("thr", "Throughput (flits/cycle)",
         "Accepted Throughput vs Injection Rate"),
        ("esc", "Escaped flits", "Escaped Flits vs Injection Rate"),
        ("hops", "Average hops", "Average Hops vs Injection Rate"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes_flat = axes.ravel()
    for ax, (key, ylabel, caption) in zip(axes_flat, panels):
        draw(ax, key)
        ax.set_xlabel("Injection rate (packets/node/cycle)")
        ax.set_ylabel(ylabel)
        ax.set_title(caption)
        ax.grid(True, alpha=0.3)

    # latency spans several orders of magnitude -> log scale
    axes_flat[0].set_yscale("log")

    # single shared legend below the figure (incl. deadlock/saturated markers)
    axes_flat[0].scatter([], [], marker="x", color="red", s=50, lw=1.5,
                         label="deadlock (collapsed)")
    axes_flat[0].scatter([], [], marker="o", facecolor="none", edgecolor="gray",
                         s=40, label="saturated (probe)")
    handles, labels = [], []
    for ax in axes_flat:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)
    fig.suptitle(f"Escape VC Analysis (uniform_random, {caption_label}, "
                 f"Ring, 16 nodes, 100000 cycles)", fontsize=13)
    fig.tight_layout(rect=[0, 0.12, 1, 0.92])
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               fontsize=8, bbox_to_anchor=(0.5, 0.0))
    fig.savefig(FIGURES / fname, dpi=160)
    plt.close(fig)
    print("wrote", FIGURES / fname)

    print(f"\nDeadlock summary ({caption_label}):")
    for e in ESCAPE_VCS:
        d = data[e]
        if d["collapsed"]:
            print(f"  escape={e}: COLLAPSED at rates {d['collapsed']}")
        if d["saturated"]:
            print(f"  escape={e}: saturated at rates {d['saturated']}")
        if not d["collapsed"] and not d["saturated"]:
            print(f"  escape={e}: no deadlock up to {max(RATES)}")


def main():
    ensure_dirs()
    if "--plot-only" not in sys.argv or not CSV.exists():
        run_experiments()
    plot_figures()


if __name__ == "__main__":
    main()
