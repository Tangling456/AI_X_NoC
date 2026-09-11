# results — Experiment Data, Figures and Reports

This directory contains the experiment outputs of the gem5/Garnet labs: the
summary data and figures of Labs 2–4, and the LaTeX reports of Labs 1–4.
The simulator changes under test live in `../src_modified/`, and the run + plot
scripts that produced everything here live in `../scripts/`.

```
results/
├── data/      # one summary CSV per experiment (parsed gem5 statistics)
├── figures/   # figures generated from the CSVs and the Lab 4 flowcharts
└── reports/   # LaTeX reports (Lab1–Lab4) and the Lab4 report template
```

## data/ — summary CSVs

| CSV | Script | Experiment |
|-----|--------|------------|
| `lab2_task1.csv` | `lab2_task1.py` | 8×8 Mesh_XY (64 nodes); 5 traffic patterns × injection rate 0.01–0.50; 10,000 cycles |
| `lab2_task2.csv` | `lab2_task2.py` | Mesh_XY, `uniform_random`; sweeps `--vcs-per-vnet` {1,2,4,8}, `--router-latency` {1,2,4}, `--link-width-bits` {32,64,128,256} |
| `lab3_task1.csv` | `lab3_task1.py` | 16-node Ring (`--routing-algorithm=3`); 3 patterns; rates 0.02–0.70; 100,000 cycles; `deadlocked` flag |
| `lab3_task2.csv` | `lab3_task2.py` | Ring; wormhole comparison `vc1_d1` / `vc16_d1` / `vc1_d16_wh`; 3 patterns; rates 0.01–0.70; 100,000 cycles |
| `lab4_bubble.csv` | `lab4_bubble.py` | Ring; bubble vs. escape vs. naive at VC = 1/2/4; 3 patterns; rates 0.01–0.70; 100,000 cycles |
| `lab4_escape.csv` | `lab4_escape.py` | Ring (4 VCs); escape-VC sweep 0–4; `--inj-vnet` = -1 and 0; rates 0.05–0.70; 100,000 cycles + deadlock probe |

Each row is one simulation run.  Columns store latency (packet/flit,
network/queueing), average hops, received packets/flits and per-node
throughput; `lab2_task1` additionally records link utilization and VC load.
Ring runs carry deadlock information: a `deadlocked` flag (`lab3_task1`), or
`deadlock` / `deadlock_type` plus probe columns (`lab4_escape`), where a short
probe re-run distinguishes true deadlock from plain saturation — the figures
mark those points separately.

## figures/ — flowcharts and generated figures 

| Figure(s) | Source |
|-----------|--------|
| `lab2_task1_analysis.png` | `data/lab2_task1.csv` |
| `lab2_task2_{vcs,router,linkwidth}_analysis.png` | `data/lab2_task2.csv` |
| `lab3_task1_analysis.png` | `data/lab3_task1.csv` |
| `lab3_task2_{uniform_random,bit_complement,bit_reverse}_analysis.png` | `data/lab3_task2.csv` |
| `lab4_bubble_{vc1,vc2,vc4}_analysis.png` | `data/lab4_bubble.csv` |
| `lab4_escape_injvnet-1_analysis.png`, `lab4_escape_injvnet0_analysis.png` | `data/lab4_escape.csv` |
| `impl_escape_vc_flow.png`, `impl_bubble_flow.png` | Lab 4 implementation flowcharts (static images; used in `reports/Lab4_report.tex`) |

## reports/ — LaTeX reports

The four lab reports (`Lab1_report.tex` … `Lab4_report.tex`) and the original
`Lab4_report_template.tex`.  All figures are resolved from `../figures/`
(`\graphicspath{{../figures/}}`), so compile each report from inside this
`reports/` directory.

## Reproducing

- **Figures only** (no simulation): `python3 ../scripts/<script>.py --plot-only`
  reads the committed CSV in `data/` and re-draws the figures.
- **Full re-run**: apply `src_modified/` to a gem5 source tree, build
  `build/Garnet_standalone/gem5.opt`, then run the scripts (set `GEM5_ROOT` if
  the gem5 tree is not at the default location).  The scripts write the summary
  CSV into `results/data/` and the figures into `results/figures/`; per-run outputs
  (`stats.txt`, configs, logs) go to `results/raw/` (not committed).
- **Environment**: all runs use a 1 GHz global frequency (1 cycle = 1 tick) and
  single-flit `--inj-vnet=0` synthetic traffic, except `lab4_escape.py`, which
  also runs `--inj-vnet=-1`.
