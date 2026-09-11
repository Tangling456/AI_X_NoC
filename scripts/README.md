# scripts — Lab Run + Plot Scripts

Python 3 scripts that run the gem5/Garnet synthetic-traffic experiments of
Labs 2–4 and generate the figures committed under `../results/`.  All
experiments use the standalone Garnet build with the `src_modified/` changes
applied.  Each script does three things: run the simulations, write one
summary CSV, and draw the figures from that CSV.  Ring scripts (Labs 3–4)
detect deadlocked runs from the gem5 log and mark them in the figures.

## Experiment configuration

All experiments run with `--network=garnet` and single-flit synthetic
traffic; Mesh runs use 64 nodes, Ring runs 16.  The table lists each script
together with its sweep and its output files under `../results/`.

| Script | Topology | Traffic | Injection rate | Cycles | Key parameters | Outputs (`../results/`) |
|--------|----------|---------|----------------|--------|----------------|-------------------------|
| `lab2_task1.py` | Mesh_XY 8×8 (64) | uniform_random, shuffle, transpose, tornado, neighbor | 0.01–0.50 (12 points) | 10,000 | 5 patterns × 12 rates | `data/lab2_task1.csv` + `figures/lab2_task1_analysis.png` |
| `lab2_task2.py` | Mesh_XY 8×8 (64) | uniform_random | 0.01–0.50 (12 points) | 10,000 | `--vcs-per-vnet` {1,2,4,8}; `--router-latency` {1,2,4}; `--link-width-bits` {32,64,128,256} | `data/lab2_task2.csv` + 3 figures (`..._{vcs,router,linkwidth}_...`) |
| `lab3_task1.py` | Ring (16) | uniform_random, bit_complement, bit_reverse | 0.02–0.70 (11 points) | 100,000 | `--routing-algorithm=3`; deadlock detection | `data/lab3_task1.csv` + `figures/lab3_task1_analysis.png` |
| `lab3_task2.py` | Ring (16) | uniform_random, bit_complement, bit_reverse | 0.01–0.70 (15 points) | 100,000 | `vc1_d1` (1 VC) · `vc16_d1` (16 VCs) · `vc1_d16_wh` (1 VC + `--wormhole`) | `data/lab3_task2.csv` + 3 figures (`..._{pattern}_...`) |
| `lab4_bubble.py` | Ring (16) | uniform_random, bit_complement, bit_reverse | 0.01–0.70 (15 points) | 100,000 | 8 configs: VC=1 (naive / +bubble) · VC=2 (naive / +bubble / 1+1 escape) · VC=4 (naive / +bubble / 3+1 escape) | `data/lab4_bubble.csv` + 3 figures (`..._{vc1,vc2,vc4}_...`) |
| `lab4_escape.py` | Ring (16) | uniform_random | 0.05–0.70 (7 points) | 100,000 | 4 VCs/vnet; escape VCs 0–4; `--inj-vnet` -1 and 0; deadlock probe (49,000 cycles) | `data/lab4_escape.csv` + 2 figures (`..._injvnet-1/0_...`) |

- **Simulation counts**: 60 (`lab2_task1`) · 132 (`lab2_task2`) · 33 (`lab3_task1`) · 135 (`lab3_task2`) · 360 (`lab4_bubble`) · 70 (`lab4_escape`, plus probe re-runs).
- **Exact rate grids** (packets/node/cycle): Lab 2 = 0.01, 0.02, 0.05, then 0.10–0.50 step 0.05; `lab3_task1` = 0.02, 0.05, 0.10–0.30 step 0.05, 0.40–0.70 step 0.10; `lab3_task2` and `lab4_bubble` = 0.01–0.05 step 0.01, 0.075, 0.10–0.30 step 0.05, 0.40–0.70 step 0.10; `lab4_escape` = 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.70.
- **Deadlock handling**: Ring runs (Labs 3–4) classify collapsed runs from the gem5 log (`common.deadlocked()`); `lab4_escape.py` re-runs such points with a short probe to distinguish true deadlock from saturation, and the figures mark them separately.

`common.py` — shared helpers imported by every script:

- `run_gem5()` — runs one simulation (`build/Garnet_standalone/gem5.opt …
  configs/example/garnet_synth_traffic.py`) and saves its stdout/stderr log;
- `deadlocked()` — detects deadlock/panic from a run log;
- `parse_stat()` / `parse_sim_ticks()` / `sum_stat()` — parse gem5 `stats.txt`;
- `write_csv()` / `read_csv()` — CSV I/O;
- `matplotlib_plt()` — matplotlib setup (`Agg` backend).

## Usage

From this directory:

```bash
python3 lab2_task1.py               # run all simulations, write CSV, plot
python3 lab2_task1.py --plot-only   # re-draw the figures from the existing CSV
```

Outputs are written into the repository: the summary CSV into
`../results/data/`, the figures into `../results/figures/`, and the raw
per-run outputs (`stats.txt`, `gem5.stdout`, `gem5.stderr`) into
`../results/raw/` (not committed).  See `../results/README.md` for the
committed outputs.

## Requirements

- A gem5 source tree with the `src_modified/` changes applied, built as
  `build/Garnet_standalone/gem5.opt`; set `GEM5_ROOT` to its location (default
  `../gem5`).
- Python 3 with `matplotlib` for the plotting step.
- `build/NULL` is stale — it predates the Lab 3/4 options (`--wormhole`,
  `--bubble`, `--escape-vc-per-vnet`) and cannot run the current config script
  (Lab 2 was originally run against it).

> A full run is expensive: Lab 2 takes about 5 minutes; Labs 3–4 run hundreds
> of 100,000-cycle simulations and take hours.  The results are already
> committed, so `--plot-only` is usually all you need.
