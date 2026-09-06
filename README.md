# gem5 Garnet Labs — Source Code Modifications

This document describes **only the source-code changes** made to the gem5
Garnet network simulator for Labs 1–4. 

All changes live in two places:

- `configs/` — the synthetic-traffic test script and the new `Ring` topology.
- `src/mem/ruby/network/garnet/` — the Garnet router micro-architecture.

The standalone Garnet build used for all experiments is
`build/Garnet_standalone/gem5.opt`.

---

## 1. Lab 1 — Synthetic Traffic & Statistics

### Task 1: Global frequency

**File:** `configs/example/garnet_synth_traffic.py`

The global tick frequency is changed from the original `1ps` to `1GHz`:

```python
m5.ticks.setGlobalFrequency("1GHz")
```

> Note: the Lab asks for `2GHz`. The experiment results in `labs_copy/` were
> generated with `2GHz`; the working tree currently sets `1GHz`. The choice
> only rescales throughput numbers and does not change latency behaviour.

### Task 2: Statistics units & the reception-rate metric

**Files:** `src/mem/ruby/network/garnet/GarnetNetwork.cc`, `network_stats.txt`

Every statistic registered in `GarnetNetwork::regStats()` gets an explicit
gem5 unit via `.unit(...)`:

- `packets_injected` / `packets_received` / `flits_injected` / `flits_received` → `Count`
- `packet_network_latency` / `packet_queueing_latency` / `flit_network_latency` /
  `flit_queueing_latency` → `Tick`
- `average_*_latency` → `Tick/Count`
- `average_hops` → `Count/Count`
- link utilizations → `Cycle`; `avg_link_utilization` / `avg_vc_load` → `Ratio`

A new metric, **Reception Rate**, is added to `network_stats.txt`:

```
reception_rate = <value> (packets/node/cycle)
```

computed as `packets_received / num_cpus / sim_cycles`.

---

## 2. Lab 2 — Performance Analysis

**No source-code changes.**

Both tasks reuse the existing `garnet_synth_traffic.py` and only sweep its
parameters:

- Task 1: 5 traffic patterns (`uniform_random`, `shuffle`, `transpose`,
  `tornado`, `neighbor`) × injection rates 0.01–0.5 on an 8×8 Mesh_XY.
- Task 2: parameter sensitivity of `--vcs-per-vnet`, `--router-latency`,
  `--link-width-bits` under `uniform_random`.

---

## 3. Lab 3 — Topology & Flow Control

### Task 1: Ring (1D-torus) topology + ring routing

**New file:** `configs/topologies/Ring.py`

`class Ring(SimpleTopology)` places `num_cpus` routers in a closed loop. Each
router has two bidirectional internal links — one leaving via the `"Right"`
outport and arriving at the right neighbour's `"Left"` inport, and one leaving
via `"Left"` and arriving at the left neighbour's `"Right"` inport. External
links attach each controller to its router, as in `Mesh_XY`.

**Files:** `src/mem/ruby/network/garnet/CommonTypes.hh`,
`RoutingUnit.hh/.cc`, `Router.hh/.cc`

- A new routing algorithm id is registered:
  `enum RoutingAlgorithm { ... RING_ = 3, ... }`.
- `RoutingUnit::outportCompute()` dispatches `RING_` to a new
  `outportComputeRing()`, and accepts a new `bool escape` flag that selects
  between adaptive and escape routing.
- `Router::route_compute()` is extended with the same `escape` flag and
  forwards it to the routing unit.

**`outportComputeRing()`** — minimal adaptive ring routing. It computes the
clockwise (`Right`) and counter-clockwise (`Left`) distances to the
destination and picks the shorter direction, tie-breaking toward `Right`
for diametrically opposite routers.

**`outportComputeRingEscape()`** — deadlock-free escape routing used by Lab 4.
It cuts the ring at a dateline between router `0` and router `n-1` and moves
monotonically toward the destination (`Right` if `dest >= me`, else `Left`),
so the escape channel-dependency graph is acyclic.

### Task 2: Wormhole flow control

Enabled with `--wormhole`. By default a VC holds exactly one packet; with
wormhole it can hold up to `WORMHOLE_DEPTH = 16` single-flit packets
(only `HEAD_TAIL_` flits are injected in the experiments).

**Files changed:**

| File | Change |
|------|--------|
| `configs/example/garnet_synth_traffic.py` | `--wormhole` flag, forwarded to `system.ruby.network.wormhole` |
| `GarnetNetwork.py` | new `wormhole` SimObject param |
| `GarnetNetwork.hh/.cc` | store `m_wormhole`, expose `isWormhole()` |
| `CommonTypes.hh` | `#define WORMHOLE_DEPTH 16` |
| `OutVcState.cc` | credit count initialised to `WORMHOLE_DEPTH` instead of the data/ctrl buffer depth |
| `VirtualChannel.hh/.cc` | add `isBufferEmpty()` helper |
| `InputUnit.hh` | add `isBufferEmpty()` wrapper |
| `InputUnit.cc` | a `HEAD_TAIL_` flit may arrive while the VC is already `ACTIVE_`; the VC is only activated on the first flit, and each flit stores its own computed output port |
| `OutputUnit.hh/.cc` | `has_vc_available()` / `select_vc()` — a VC is usable when it has a free buffer slot (positive credit), not only when idle |
| `SwitchAllocator.hh/.cc` | wormhole-specific SA path (below) |
| `NetworkInterface.cc` | `calculateVC()` treats a VC as usable while it has credit |

**Key implementation details in `SwitchAllocator`:**

- Each single-flit packet performs a fresh output-VC allocation; the route is
  read from the flit itself (`t_flit->get_outport()`), not from the VC.
- `send_allowed()` uses `has_vc_available(vnet, wormhole)` — a new packet may
  be sent if *any* VC of the vnet still has a free buffer slot.
- `vc_allocate()` uses `select_vc(vnet, wormhole)`, which prefers to keep
  filling an already-`ACTIVE_` VC and only activates an `IDLE_` VC otherwise.
- Credit return: when a flit leaves an input VC, a **free** credit is sent
  upstream only once the buffer is completely empty
  (`input_unit->isBufferEmpty(invc)`); otherwise a non-free credit returns a
  single buffer slot.

### Comparison matrix (Lab 3 Task 2)

| Config | VCs | Depth | Mechanism |
|--------|-----|-------|-----------|
| `vc1_d1`  | 1  | 1 | default credit-based |
| `vc16_d1` | 16 | 1 | default credit-based |
| `vc1_d16_wh` | 1 | 16 | `--wormhole` |

---

## 4. Lab 4 — Project: Flow Control (Escape VC & Bubble)

Two deadlock-avoidance flow-control techniques are implemented for the Ring,
whose adaptive minimal routing has a cyclic channel dependency and therefore
deadlocks at high load.

### 4.1 Escape virtual channels

Enabled with `--escape-vc-per-vnet=N`. The `N` lowest-indexed VCs of each
virtual network are reserved as **escape VCs**; the remaining VCs are adaptive.

**Files changed:**

| File | Change |
|------|--------|
| `configs/example/garnet_synth_traffic.py` | `--escape-vc-per-vnet` flag |
| `GarnetNetwork.py` | `escape_vc_per_vnet` SimObject param |
| `GarnetNetwork.hh/.cc` | store `m_escape_vc_per_vnet`, expose `getEscapeVcPerVnet()` |
| `CommonTypes.hh` | `enum VCClass { ESCAPE_VC_, ADAPTIVE_VC_ }` |
| `Router.hh/.cc` | `isEscapeVC(vc)` — `vc % vcs_per_vnet < escape_vc_per_vnet`; new `m_escaped_flits` stat (`.escaped_flits`) |
| `VirtualChannel.hh/.cc` | track `m_output_port_adaptive` and `m_output_port_escape` separately |
| `InputUnit.hh/.cc` | on head arrival compute **both** the adaptive and the escape route (`grant_outport_adaptive/escape`) |
| `OutputUnit.hh/.cc` | class-aware `has_free_vc / select_free_vc / has_vc_available / select_vc` plus `vc_class_start()` / `vc_class_size()` |
| `SwitchAllocator.hh/.cc` | class-aware SA with escape fallback (below) |

**Key implementation details in `SwitchAllocator::arbitrate_inports()`**
for a head flit needing an output VC:

1. An **escape-class input VC** always routes along the escape route
   (`vc_class = ESCAPE_VC_`).
2. An adaptive input VC first tries its adaptive output port; if no adaptive
   output VC is free it **falls back** to the escape route when escape VCs are
   configured and one is free.
3. The chosen port is remembered on the VC (`grant_outport`), so body/tail
   flits and the ordering check see the same route.
4. `vc_allocate()` restricts selection to the requested VC class, and heads
   allocated to an escape VC are counted in `m_escaped_flits`.

### 4.2 Bubble flow control

Enabled with `--bubble`. The core idea: **only injection may grow per-direction
ring occupancy** (ring-to-ring forwarding is net-zero), so injection is
restricted to keep at least one idle input VC (a "bubble") in each ring
direction. This provably prevents the ring from filling completely and keeps
it deadlock-free without escape VCs.

**Files changed:**

| File | Change |
|------|--------|
| `configs/example/garnet_synth_traffic.py` | `--bubble` flag |
| `GarnetNetwork.py` | `bubble` SimObject param |
| `GarnetNetwork.hh/.cc` | store `m_bubble`, expose `isBubble()` |
| `CommonTypes.hh` | `BUBBLE_INJECT_MIN_IDLE_VC 2` (injection-side, whole ring), `BUBBLE_ENTER_MIN_IDLE_VC 2` (ring-entry, per direction) |
| `Router.hh/.cc` | `getNumRingVCs()` and `getNumActiveRingVCs(vnet)` — count VCs on all non-`Local` (ring) input ports |
| `InputUnit.hh` | `getNumActiveVCs(vnet)` |
| `OutputUnit.hh` | `num_idle_vcs(vnet)` |
| `NetworkInterface.cc` | injection-side gate in `calculateVC()` |
| `SwitchAllocator.cc` | ring-entry gate in `send_allowed()` |

**Two gates:**

- **Injection side** — `NetworkInterface::calculateVC()`: if the attached
  router has fewer than `BUBBLE_INJECT_MIN_IDLE_VC` idle ring VCs across both
  directions, injection is refused (returns `-1`). This is the only gate at
  `vcs_per_vnet == 1`.
- **Ring entry** — `SwitchAllocator::send_allowed()`: for `vcs_per_vnet >= 2`,
  a head flit coming from the `Local` port and heading onto a ring direction
  is blocked if that single direction has fewer than
  `BUBBLE_ENTER_MIN_IDLE_VC` idle VCs.

Forwarding between ring directions is deliberately **not** gated, since it
does not change per-direction occupancy; gating it would itself create the
deadlock it is meant to prevent.

---

## 5. Modified-file summary

| Lab / Task | Files |
|------------|-------|
| Lab1 T1 | `configs/example/garnet_synth_traffic.py` |
| Lab1 T2 | `src/mem/ruby/network/garnet/GarnetNetwork.cc`, `network_stats.txt` |
| Lab2 | *(none)* |
| Lab3 T1 | `configs/topologies/Ring.py`, `CommonTypes.hh`, `RoutingUnit.hh/.cc`, `Router.hh/.cc` |
| Lab3 T2 | `garnet_synth_traffic.py`, `GarnetNetwork.py/.hh/.cc`, `CommonTypes.hh`, `OutVcState.cc`, `VirtualChannel.hh/.cc`, `InputUnit.hh/.cc`, `OutputUnit.hh/.cc`, `SwitchAllocator.hh/.cc`, `NetworkInterface.cc` |
| Lab4 Escape VC | `garnet_synth_traffic.py`, `GarnetNetwork.py/.hh/.cc`, `CommonTypes.hh`, `Router.hh/.cc`, `VirtualChannel.hh/.cc`, `InputUnit.hh/.cc`, `OutputUnit.hh/.cc`, `SwitchAllocator.hh/.cc` |
| Lab4 Bubble | `garnet_synth_traffic.py`, `GarnetNetwork.py/.hh/.cc`, `CommonTypes.hh`, `Router.hh/.cc`, `InputUnit.hh`, `OutputUnit.hh`, `NetworkInterface.cc`, `SwitchAllocator.cc` |
