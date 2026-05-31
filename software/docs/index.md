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

How the sim/real switch, controller manager, and application nodes fit together.
:::

:::{grid-item-card} {octicon}`package` Package reference
:link: _generated/reference/index
:link-type: doc

Auto-generated docs for every package: nodes, launch args, parameters, messages.
:::

:::{grid-item-card} {octicon}`code` Python API
:link: _generated/reference/api
:link-type: doc

Full module / class / function reference, generated statically from the source.
:::
::::

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
:caption: Reference

_generated/reference/index
_generated/reference/api
```
