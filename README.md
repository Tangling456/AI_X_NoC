# gem5 Garnet Labs

Labs 1–4 built on gem5's Garnet 3.0 network simulator: synthetic-traffic
statistics (Lab 1), performance analysis of an 8×8 mesh (Lab 2), a 1D-ring
topology with wormhole flow control (Lab 3), and deadlock-free flow control on
the ring — escape virtual channels and bubble flow control (Lab 4).

## Repository layout

```
.
├── src_modified/   # the gem5 files we modified, in their original tree layout
├── scripts/        # experiment run + plot scripts (Labs 2–4)
├── results/        # experiment data (CSV), figures (PNG) and LaTeX reports
└── assignments/    # lab handouts (Lab0–Lab4)
```

- **`src_modified/`** — the only gem5 files changed for these labs, kept in
  gem5's relative paths (`configs/...`, `src/mem/ruby/network/garnet/...`) so
  they can be overlaid on a gem5 checkout; `src_modified/README.md` describes
  every change, lab by lab.
- **`scripts/`** — Python 3 scripts that run the simulations and draw the
  figures; `scripts/README.md` has the experiment matrix and usage.
- **`results/`** — committed outputs: summary CSVs (`data/`), figures
  (`figures/`) and the lab reports (`reports/`); see `results/README.md`.
- **`assignments/`** — the original lab handouts this work follows.

## Labs at a glance

| Lab | Topic | Highlights |
|-----|-------|------------|
| 1 | Synthetic traffic & statistics | global frequency set to 1 GHz (unified with the simulation clock); statistic units completed; new **reception rate** metric |
| 2 | Performance analysis | 8×8 Mesh_XY, 5 traffic patterns; sweeps of `--vcs-per-vnet`, `--router-latency`, `--link-width-bits` |
| 3 | Topology & flow control | new **Ring** (1D-torus) topology (`--routing-algorithm=3`) with minimal adaptive routing; **wormhole** flow control (`--wormhole`, depth 16) |
| 4 | Project: deadlock-free flow control | **escape virtual channels** (`--escape-vc-per-vnet=N`, Duato's theorem) and **bubble flow control** (`--bubble`) eliminate deadlocks on the ring |

All experiments use the standalone Garnet build with a 1 GHz global frequency
(1 cycle = 1 tick) and single-flit `--inj-vnet=0` synthetic traffic; the
escape-VC runs additionally use `--inj-vnet=-1`.

## Quick start

1. Install the gem5 build dependencies (Ubuntu/Debian example — the same list
   as in `assignments/Lab0_Preliminary.md`; see the
   [gem5 building docs](https://www.gem5.org/documentation/general_docs/building)
   for other platforms):

   ```bash
   sudo apt install build-essential git m4 scons zlib1g zlib1g-dev \
       libprotobuf-dev protobuf-compiler libprotoc-dev libgoogle-perftools-dev \
       python3-dev libboost-all-dev pkg-config
   ```

2. Download a gem5 source tree; the full gem5 checkout is not part of this
   repository.  The changes were developed against the `v23.0.0.1` release, so
   clone that tag (or download a release archive from
   [gem5.org](https://www.gem5.org/)):

   ```bash
   git clone --depth 1 --branch v23.0.0.1 https://github.com/gem5/gem5.git
   pip install -r gem5/requirements.txt   # optional (gem5 dev tooling)
   pip install matplotlib                 # for the plotting step
   ```

3. Replace the corresponding files in the gem5 tree with the versions from
   `src_modified/` (they mirror gem5's own paths, so copying the tree over
   replaces exactly the files that were changed), then build the standalone
   Garnet binary (from this repository's root):

   ```bash
   cp -r src_modified/. /path/to/gem5/
   cd /path/to/gem5
   scons build/Garnet_standalone/gem5.opt -j $(nproc)
   ```

   This produces `build/Garnet_standalone/gem5.opt` — the binary the
   experiment scripts expect (equivalent to the handout's
   `scons build/NULL/gem5.opt PROTOCOL=Garnet_standalone`, i.e. the same
   configuration in a differently named build directory).  The build takes
   about 15–30 min and several GB of memory (6–9 GB) — reduce `-j` if you are
   short on RAM or swap.

4. Run an experiment from `scripts/`, or simply re-draw its figures from the
   committed CSV (fast, no simulation and no gem5 build needed):

   ```bash
   cd scripts
   python3 lab4_bubble.py --plot-only    # figures only
   export GEM5_ROOT=/path/to/gem5        # needed for actual simulations
   python3 lab4_bubble.py                # full re-run (hours)
   ```

   Without `GEM5_ROOT`, the scripts expect the gem5 tree at `../gem5`
   (relative to the directory you run them from).

5. Compile any report from `results/reports/` (e.g. `pdflatex
   Lab4_report.tex`); figures are resolved from `../figures/`.

The modified gem5 files keep their original license headers.
