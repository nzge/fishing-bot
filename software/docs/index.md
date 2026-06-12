# Fishing Robot — ROS 2 Workspace

```{warning}
Course project for **MAE 263C**. A force-controlled robotic fishing arm built on
**ROS 2 Jazzy**, with a MuJoCo simulation backend and a Dynamixel hardware path.
```

Welcome to the developer documentation for the `fishing-bot` software stack. The
workspace is a standard colcon workspace under `software/`, organised into seven
packages spanning bring-up, control, sensing, planning, robot description and
diagnostics.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} {octicon}`rocket` Getting started
:link: getting_started
:link-type: doc

Build the workspace, source it, and launch the simulator or hardware stack.
:::

:::{grid-item-card} {octicon}`stack` Architecture overview
:link: overview
:link-type: doc

Sim/real switch, control loop, package map, and navigation hub.
:::

:::{grid-item-card} {octicon}`package` Package guide
:link: packages/index
:link-type: doc

In-depth narrative for every package: nodes, algorithms, interactions.
:::

:::{grid-item-card} {octicon}`git-branch` ROS 2 graphs
:link: ros2/index
:link-type: doc

Separate simulation vs hardware node/topic diagrams with explanations.
:::

:::{grid-item-card} {octicon}`file` Package reference (auto)
:link: _generated/reference/index
:link-type: doc

Machine-generated launch args, parameters, messages — always in sync.
:::

:::{grid-item-card} {octicon}`code` Python API (auto)
:link: _generated/reference/api
:link-type: doc

Module / class / function reference via static analysis.
:::
::::

## Documentation map

```{mermaid}
flowchart TB
    GS["getting_started"] --> OV["overview"]
    OV --> PKG["packages/"]
    OV --> ROS["ros2/"]
    PKG --> REF["_generated/reference/"]
    PKG --> API["_generated/autoapi/"]
    ROS --> DIA["diagrams/*.mmd"]
    DP["doc_pipeline"] -.-> REF
    DP -.-> ROS
```

## Building the documentation

Run `./docs/build.sh` when you want the site refreshed from the current source.
See {doc}`doc_pipeline` for details.

```{toctree}
:hidden:
:caption: Guides

getting_started
overview
doc_pipeline
```

```{toctree}
:hidden:
:caption: Architecture

packages/index
ros2/index
```

```{toctree}
:hidden:
:caption: Reference (auto-generated)

_generated/reference/index
_generated/reference/api
_generated/ros_graph/topic_index
```
