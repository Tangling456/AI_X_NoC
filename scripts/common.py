#!/usr/bin/env python3
"""Shared helpers for the lab execution scripts (run experiment + plot).

Each ``labX_taskX.py`` script does three things:

1. run the gem5 ``garnet_synth_traffic`` experiments,
2. write one summary CSV into ``results/data/``,
3. generate figures into ``results/figures/``.

Binary note
-----------
All scripts use the standalone Garnet build
(``build/Garnet_standalone/gem5.opt``).  The ``build/NULL`` binary predates the
``--wormhole`` / ``--bubble`` / ``--escape-vc-per-vnet`` parameters that were
added to ``configs/example/garnet_synth_traffic.py`` for Labs 3 and 4, so it
refuses to run the current config script.  Rebuild ``build/NULL`` if you want
to use it instead (Lab2 was originally run against ``build/NULL``).
"""
import os
import subprocess
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

# gem5 source tree location. Override it via the GEM5_ROOT environment
# variable; the repository only ships src_modified/, not a full gem5 checkout.
GEM5_ROOT = os.environ.get("GEM5_ROOT", "../gem5")
CONFIG = os.path.join(GEM5_ROOT, "configs", "example", "garnet_synth_traffic.py")
GEM5 = os.path.join(GEM5_ROOT, "build", "Garnet_standalone", "gem5.opt")
GEM5_NULL = os.path.join(GEM5_ROOT, "build", "NULL", "gem5.opt")  # stale, see docstring

# results/ is a sibling of scripts/ in the repository layout.
RESULTS = HERE.parent / "results"
DATA = RESULTS / "data"
FIGURES = RESULTS / "figures"
RAW = RESULTS / "raw"


def ensure_dirs():
    RESULTS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)


def run_gem5(outdir, extra_args, timeout=1800, gem5=None):
    """Run one synthetic-traffic simulation.

    Returns the process return code (``-124`` on timeout).  The process
    stdout/stderr are captured and stored in ``<outdir>/gem5.stdout`` and
    ``<outdir>/gem5.stderr`` so deadlock / panic messages can be inspected.
    """
    gem5 = gem5 or GEM5
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [gem5, f"--outdir={outdir}", CONFIG] + [str(a) for a in extra_args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=GEM5_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        rc, out, err = -124, b"", b"timed out"
    (outdir / "gem5.stdout").write_bytes(out)
    (outdir / "gem5.stderr").write_bytes(err)
    return rc


def deadlocked(outdir):
    """True if the run log indicates a network deadlock / panic."""
    p = Path(outdir) / "gem5.stderr"
    if not p.exists():
        return False
    text = p.read_text(errors="replace").lower()
    return ("deadlock" in text) or ("panic" in text)


def parse_stat(stats_path, name):
    """Return a numeric scalar stat, or the ``::total`` of a vector stat.

    Handles gem5's two representations for vector stats: a per-component
    distribution line (starting with ``|``) followed by a ``::total`` line.
    """
    key = "system.ruby.network." + name
    try:
        with open(stats_path, "r") as f:
            for line in f:
                if not line.startswith(key):
                    continue
                rest = line[len(key):]
                if rest.startswith("::total"):
                    rest = rest[len("::total"):]
                elif rest.startswith("::"):
                    continue  # skip per-component entries
                parts = rest.split()
                if not parts or parts[0] == "|":
                    continue  # skip the distribution header line
                try:
                    return float(parts[0])
                except ValueError:
                    continue
    except OSError:
        return None
    return None


def parse_sim_ticks(stats_path):
    """Return ``simTicks`` from a stats.txt file."""
    try:
        with open(stats_path, "r") as f:
            for line in f:
                parts = line.split()
                if parts and parts[0] == "simTicks":
                    try:
                        return float(parts[1])
                    except ValueError:
                        return 0.0
    except OSError:
        return 0.0
    return 0.0


def sum_stat(stats_path, suffix):
    """Sum a per-router scalar stat (e.g. ``escaped_flits``) over all routers."""
    total = 0.0
    try:
        with open(stats_path, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0].endswith("." + suffix):
                    try:
                        total += float(parts[1])
                    except ValueError:
                        pass
    except OSError:
        pass
    return total


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def matplotlib_plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt
