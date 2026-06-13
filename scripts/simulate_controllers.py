#!/usr/bin/env python3
"""Offline MuJoCo simulation for admittance and force-feedback tension controllers.

Runs headless against the same MJCF as the ROS stack, records time-series data,
and writes report-ready plots (PNG + PDF) plus CSV/NPZ exports.

Usage:
    python3 scripts/simulate_controllers.py
    python3 scripts/simulate_controllers.py --controller admittance --duration 20
    python3 scripts/simulate_controllers.py --output-dir software/recordings/my_run
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
MJCF = REPO_ROOT / 'software/src/description/urdf/fishing-robot_sim.xml'
DEFAULT_OUTPUT = REPO_ROOT / 'software/recordings'

sys.path.insert(0, str(REPO_ROOT / 'software/src/control'))

from control.fishing_control_core import (  # noqa: E402
    AdmittanceConfig,
    AdmittanceControllerCore,
    FishingState,
    ForceFeedbackConfig,
    ForceFeedbackControllerCore,
    get_fishing_state,
)

try:
    import mujoco
except ImportError:
    print('mujoco not installed — pip install mujoco')
    sys.exit(1)


STATE_LABELS = {
    int(FishingState.MONITOR): 'MONITOR',
    int(FishingState.HOOK_SET): 'HOOK_SET',
    int(FishingState.REGULATE): 'REGULATE',
}


def configs_from_params_yaml() -> Tuple[AdmittanceConfig, ForceFeedbackConfig]:
    """Defaults aligned with software/src/bringup/config/params.yaml."""
    adm = AdmittanceConfig(
        target_tension=3.5,
        k_v=20.0,
        k_f=8.0,
        tension_filter_alpha=0.055,
        control_rate_hz=50.0,
    )
    ffb = ForceFeedbackConfig(
        target_tension=3.5,
        tension_to_angle_gain=0.261799,
        qeq_alpha=0.04,
        max_qeq_step=0.00384,
        raise_gain=1.25,
        lower_gain=0.80,
        tension_filter_alpha=0.055,
        control_rate_hz=50.0,
    )
    return adm, ffb


def fish_pull(t: float, cfg) -> float:
    """Fish disturbance matching fish_agent + notebook regulation profile."""
    if t < cfg.bite_time + cfg.hook_duration:
        if t < cfg.bite_time:
            return 0.0
        s = (t - cfg.bite_time) / cfg.hook_duration
        s = max(0.0, min(1.0, s))
        return max(0.75 + 0.55 * math.sin(math.pi * s), 0.0)

    tau = t - cfg.bite_time - cfg.hook_duration
    return max(
        1.00
        + 0.46 * math.sin(0.95 * tau)
        + 0.22 * math.sin(2.10 * tau + 0.7)
        + 0.10 * math.sin(0.38 * tau + 1.2),
        0.0,
    )


def read_tension(model, data, tendon_id: int, stiffness: float = 220.0) -> float:
    stretch = float(
        data.ten_length[tendon_id] - model.tendon_lengthspring[tendon_id][0],
    )
    return max(stiffness * stretch, 0.0)


def regulation_mask(times: np.ndarray, cfg, settle_s: float = 1.0) -> np.ndarray:
    reg_start = cfg.bite_time + cfg.hook_duration + settle_s
    return times > reg_start


def compute_metrics(times: np.ndarray, tension: np.ndarray, cfg) -> Dict[str, float]:
    mask = regulation_mask(times, cfg)
    if not np.any(mask):
        return {
            'rms_error_N': float('nan'),
            'mae_N': float('nan'),
            'max_tension_N': float(np.max(tension)) if tension.size else float('nan'),
            'regulation_samples': 0,
        }
    err = tension[mask] - cfg.target_tension
    return {
        'rms_error_N': float(np.sqrt(np.mean(err * err))),
        'mae_N': float(np.mean(np.abs(err))),
        'max_tension_N': float(np.max(tension)),
        'regulation_samples': int(np.sum(mask)),
    }


def run_simulation(
    controller_type: str,
    cfg,
    duration: float = 18.0,
    settle_steps: int = 300,
    control_enabled: bool = True,
) -> Dict[str, np.ndarray]:
    """Run one MuJoCo trial and return logged arrays."""
    model = mujoco.MjModel.from_xml_path(str(MJCF))
    data = mujoco.MjData(model)
    dt = model.opt.timestep

    j1_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'Joint_1')
    j2_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'Joint_2')
    j1_qpos = model.jnt_qposadr[j1_id]
    j2_qpos = model.jnt_qposadr[j2_id]
    j2_qvel = model.jnt_dofadr[j2_id]
    tip_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, 'rod_tip_site')
    fish_j_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'fish_swim')
    fish_qpos = model.jnt_qposadr[fish_j_id]
    fish_act_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, 'fish_force')
    tendon_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_TENDON, 'fishing_line')

    data.qpos[j1_qpos] = cfg.joint_1_hold
    data.qpos[j2_qpos] = cfg.q_init
    data.qpos[fish_qpos] = 0.0
    mujoco.mj_forward(model, data)

    adm_core: Optional[AdmittanceControllerCore] = None
    ffb_core: Optional[ForceFeedbackControllerCore] = None
    if controller_type == 'admittance':
        adm_core = AdmittanceControllerCore(cfg, dt)
        adm_core.reset(cfg.q_init)
    elif controller_type == 'force_feedback':
        ffb_core = ForceFeedbackControllerCore(cfg)

    for _ in range(settle_steps):
        data.ctrl[0] = cfg.joint_1_hold
        data.ctrl[1] = cfg.q_init
        data.ctrl[fish_act_id] = 0.0
        mujoco.mj_step(model, data)

    data.time = 0.0
    log: Dict[str, List[float]] = {
        'time_s': [],
        'state': [],
        'tension_raw_N': [],
        'tension_filtered_N': [],
        'tension_error_N': [],
        'q_actual_rad': [],
        'q_cmd_rad': [],
        'q_dot_actual_rad_s': [],
        'fish_pull_N': [],
        'line_length_m': [],
        'theta_virtual_rad': [],
        'theta_dot_cmd_rad_s': [],
        'q_eq_rad': [],
        'q_target_rad': [],
    }

    while data.time < duration:
        t = data.time
        state = get_fishing_state(t, cfg)
        mujoco.mj_forward(model, data)

        q2 = float(data.qpos[j2_qpos])
        q2_dot = float(data.qvel[j2_qvel])
        tip = data.site_xpos[tip_id].copy()
        pull = fish_pull(t, cfg)

        tension_raw = read_tension(model, data, tendon_id)
        if controller_type == 'admittance' and adm_core is not None:
            tension = adm_core.update_tension(tension_raw)
        elif controller_type == 'force_feedback' and ffb_core is not None:
            tension = ffb_core.update_tension(tension_raw)
        else:
            alpha = cfg.tension_filter_alpha
            prev = log['tension_filtered_N'][-1] if log['tension_filtered_N'] else 0.0
            tension = (1.0 - alpha) * prev + alpha * tension_raw

        q_cmd = cfg.q_init
        theta_virtual = math.nan
        theta_dot_cmd = math.nan
        q_eq = math.nan
        q_target = math.nan

        if controller_type == 'admittance' and adm_core is not None:
            if state == FishingState.HOOK_SET:
                q_cmd = adm_core.hook_set_target(t)
                adm_core.reset(q2)
                adm_core.theta_cmd = q_cmd
            elif state == FishingState.REGULATE and control_enabled:
                q_cmd, theta_dot_cmd = adm_core.update(
                    t, state, tension, q2, q2_dot, tuple(tip), None,
                )
            elif state == FishingState.REGULATE:
                q_cmd = cfg.q_neutral
            else:
                q_cmd = cfg.q_init
            theta_virtual = adm_core.theta_cmd

        elif controller_type == 'force_feedback' and ffb_core is not None:
            q_eq, q_target = ffb_core.update(t, state, tension, control_enabled)
            q_cmd = q_eq

        else:
            if state == FishingState.HOOK_SET:
                s = (t - cfg.bite_time) / cfg.hook_duration
                s = max(0.0, min(1.0, s))
                q_cmd = cfg.q_init + (cfg.q_hook - cfg.q_init) * (
                    3.0 * s * s - 2.0 * s * s * s
                )
            elif state == FishingState.REGULATE:
                q_cmd = cfg.q_neutral
            else:
                q_cmd = cfg.q_init

        data.ctrl[0] = cfg.joint_1_hold
        data.ctrl[1] = q_cmd
        data.ctrl[fish_act_id] = pull if state != FishingState.MONITOR else 0.0
        mujoco.mj_step(model, data)

        f_desired = 0.0 if state == FishingState.MONITOR else cfg.target_tension
        log['time_s'].append(t)
        log['state'].append(int(state))
        log['tension_raw_N'].append(tension_raw)
        log['tension_filtered_N'].append(tension)
        log['tension_error_N'].append(f_desired - tension)
        log['q_actual_rad'].append(q2)
        log['q_cmd_rad'].append(q_cmd)
        log['q_dot_actual_rad_s'].append(q2_dot)
        log['fish_pull_N'].append(pull)
        log['line_length_m'].append(float(data.ten_length[tendon_id]))
        log['theta_virtual_rad'].append(theta_virtual)
        log['theta_dot_cmd_rad_s'].append(theta_dot_cmd)
        log['q_eq_rad'].append(q_eq)
        log['q_target_rad'].append(q_target)

    out: Dict[str, np.ndarray] = {}
    for key, values in log.items():
        out[key] = np.asarray(values, dtype=float if key != 'state' else int)
    out['controller_type'] = np.array([controller_type])
    out['target_tension_N'] = np.array([cfg.target_tension])
    return out


def save_recording(
    output_dir: Path,
    name: str,
    data: Dict[str, np.ndarray],
    cfg,
    metrics: Dict[str, float],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    npz_path = output_dir / f'{name}.npz'
    np.savez(npz_path, **data, config_json=json.dumps(asdict(cfg)), metrics_json=json.dumps(metrics))

    csv_path = output_dir / f'{name}.csv'
    columns = [
        'time_s', 'state', 'tension_raw_N', 'tension_filtered_N', 'tension_error_N',
        'q_actual_rad', 'q_cmd_rad', 'q_dot_actual_rad_s', 'fish_pull_N',
        'line_length_m', 'theta_virtual_rad', 'theta_dot_cmd_rad_s',
        'q_eq_rad', 'q_target_rad',
    ]
    with csv_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        n = len(data['time_s'])
        for i in range(n):
            writer.writerow([data[col][i] for col in columns])

    metrics_path = output_dir / f'{name}_metrics.json'
    with metrics_path.open('w') as f:
        json.dump(metrics, f, indent=2)

    print(f'  saved {npz_path.name}, {csv_path.name}, {metrics_path.name}')


def _state_markers(ax, cfg) -> None:
    ax.axvline(cfg.bite_time, color='gray', linestyle=':', linewidth=1.0, alpha=0.8)
    ax.axvline(
        cfg.bite_time + cfg.hook_duration,
        color='gray', linestyle='--', linewidth=1.0, alpha=0.8,
    )


def plot_results(
    output_dir: Path,
    runs: Dict[str, Dict[str, np.ndarray]],
    cfg,
    metrics: Dict[str, Dict[str, float]],
) -> None:
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as exc:
        print(f'matplotlib unavailable ({exc}); skipping plots.')
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    reg_start = cfg.bite_time + cfg.hook_duration

    # --- Comparison: tension tracking ---
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax = axes[0]
    for label, data in runs.items():
        t = data['time_s']
        ax.plot(t, data['tension_filtered_N'], linewidth=1.8, label=label)
    ax.axhline(cfg.target_tension, color='k', linestyle='--', linewidth=1.2, label='target')
    _state_markers(ax, cfg)
    ax.set_ylabel('filtered tension [N]')
    ax.set_title('Line tension — controller comparison')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    for label, data in runs.items():
        mask = data['time_s'] > reg_start
        if np.any(mask):
            ax.plot(
                data['time_s'][mask],
                data['tension_error_N'][mask],
                linewidth=1.5,
                label=label,
            )
    ax.axhline(0.0, color='k', linewidth=0.8)
    ax.set_ylabel('tension error [N]')
    ax.set_xlabel('time [s]')
    ax.set_title('Tension error during regulation phase')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    for ext in ('png', 'pdf'):
        path = output_dir / f'comparison_tension.{ext}'
        fig.savefig(path, dpi=150)
        print(f'  saved {path.name}')
    plt.close(fig)

    # --- Comparison: joint position ---
    fig, ax = plt.subplots(figsize=(10, 4))
    for label, data in runs.items():
        ax.plot(
            data['time_s'],
            np.rad2deg(data['q_actual_rad']),
            linewidth=1.8,
            label=f'{label} (actual)',
        )
    ax.axhline(np.rad2deg(cfg.q_neutral), color='k', linestyle='--', linewidth=1.0, label='q_neutral')
    _state_markers(ax, cfg)
    ax.set_ylabel('pitch angle [deg]')
    ax.set_xlabel('time [s]')
    ax.set_title('Rod pitch during simulation')
    ax.legend(loc='upper right', ncol=2, fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    for ext in ('png', 'pdf'):
        path = output_dir / f'comparison_position.{ext}'
        fig.savefig(path, dpi=150)
        print(f'  saved {path.name}')
    plt.close(fig)

    # --- Per-controller detail plots ---
    if 'admittance' in runs:
        data = runs['admittance']
        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
        ax = axes[0]
        ax.plot(data['time_s'], data['tension_filtered_N'], label='filtered', linewidth=1.8)
        ax.axhline(cfg.target_tension, linestyle='--', color='tab:red', label='target')
        _state_markers(ax, cfg)
        ax.set_ylabel('tension [N]')
        ax.set_title('Admittance controller — tension tracking')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        ax = axes[1]
        ax.plot(
            data['time_s'],
            np.rad2deg(data['theta_virtual_rad']),
            label='virtual θ_cmd',
            linewidth=1.8,
        )
        ax.plot(
            data['time_s'],
            np.rad2deg(data['q_actual_rad']),
            label='actual θ',
            linewidth=1.5,
            alpha=0.85,
        )
        ax.set_ylabel('angle [deg]')
        ax.set_title('Virtual admittance state vs measured pitch')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        ax = axes[2]
        ax.plot(
            data['time_s'],
            np.rad2deg(data['theta_dot_cmd_rad_s']),
            label='θ̇_cmd',
            linewidth=1.5,
        )
        ax.set_ylabel('rate [deg/s]')
        ax.set_xlabel('time [s]')
        ax.set_title('Virtual admittance velocity command')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        fig.tight_layout()
        for ext in ('png', 'pdf'):
            path = output_dir / f'admittance_detail.{ext}'
            fig.savefig(path, dpi=150)
            print(f'  saved {path.name}')
        plt.close(fig)

    if 'force_feedback' in runs:
        data = runs['force_feedback']
        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
        ax = axes[0]
        ax.plot(data['time_s'], data['tension_filtered_N'], label='filtered', linewidth=1.8)
        ax.axhline(cfg.target_tension, linestyle='--', color='tab:red', label='target')
        _state_markers(ax, cfg)
        ax.set_ylabel('tension [N]')
        ax.set_title('Force-feedback controller — tension tracking')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        ax = axes[1]
        ax.plot(
            data['time_s'],
            np.rad2deg(data['q_eq_rad']),
            label='q_eq (smoothed)',
            linewidth=1.8,
        )
        ax.plot(
            data['time_s'],
            np.rad2deg(data['q_target_rad']),
            label='q_target (raw)',
            linewidth=1.2,
            alpha=0.75,
        )
        ax.plot(
            data['time_s'],
            np.rad2deg(data['q_actual_rad']),
            label='actual θ',
            linewidth=1.5,
            alpha=0.85,
        )
        ax.set_ylabel('angle [deg]')
        ax.set_title('Equilibrium pitch mapping')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        ax = axes[2]
        ax.plot(data['time_s'], data['tension_error_N'], linewidth=1.5, label='error')
        ax.axhline(0.0, color='k', linewidth=0.8)
        ax.set_ylabel('error [N]')
        ax.set_xlabel('time [s]')
        ax.set_title('Tension error')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        fig.tight_layout()
        for ext in ('png', 'pdf'):
            path = output_dir / f'force_feedback_detail.{ext}'
            fig.savefig(path, dpi=150)
            print(f'  saved {path.name}')
        plt.close(fig)

    # --- Metrics summary table as figure ---
    fig, ax = plt.subplots(figsize=(8, 2.5))
    ax.axis('off')
    rows = [['controller', 'RMS error [N]', 'MAE [N]', 'max tension [N]']]
    for name, m in metrics.items():
        rows.append([
            name,
            f"{m['rms_error_N']:.3f}",
            f"{m['mae_N']:.3f}",
            f"{m['max_tension_N']:.3f}",
        ])
    table = ax.table(cellText=rows, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.6)
    ax.set_title('Regulation-phase metrics (1 s settle after hook set)', pad=12)
    fig.tight_layout()
    for ext in ('png', 'pdf'):
        path = output_dir / f'metrics_summary.{ext}'
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f'  saved {path.name}')
    plt.close(fig)

    summary_path = output_dir / 'metrics_summary.json'
    with summary_path.open('w') as f:
        json.dump(metrics, f, indent=2)
    print(f'  saved {summary_path.name}')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Simulate fishing tension controllers and export report artifacts',
    )
    parser.add_argument(
        '--controller',
        choices=['admittance', 'force_feedback', 'baseline', 'all'],
        default='all',
        help='Which controller(s) to simulate (baseline = hold q_neutral)',
    )
    parser.add_argument('--duration', type=float, default=18.0, help='Simulation length [s]')
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Output directory (default: software/recordings/sim_<timestamp>)',
    )
    parser.add_argument('--target', type=float, default=3.5, help='Target tension [N]')
    args = parser.parse_args()

    if not MJCF.exists():
        print(f'MJCF not found: {MJCF}')
        sys.exit(1)

    adm_cfg, ffb_cfg = configs_from_params_yaml()
    adm_cfg.target_tension = args.target
    ffb_cfg.target_tension = args.target

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = args.output_dir or (DEFAULT_OUTPUT / f'sim_{stamp}')
    output_dir.mkdir(parents=True, exist_ok=True)

    controllers: List[Tuple[str, object, str]] = []
    if args.controller in ('all', 'baseline'):
        controllers.append(('baseline', adm_cfg, 'baseline'))
    if args.controller in ('all', 'admittance'):
        controllers.append(('admittance', adm_cfg, 'admittance'))
    if args.controller in ('all', 'force_feedback'):
        controllers.append(('force_feedback', ffb_cfg, 'force_feedback'))

    runs: Dict[str, Dict[str, np.ndarray]] = {}
    metrics: Dict[str, Dict[str, float]] = {}

    print(f'Running simulations -> {output_dir}')
    for run_name, cfg, ctrl_type in controllers:
        print(f'  [{run_name}] ...', end=' ', flush=True)
        data = run_simulation(
            ctrl_type,
            cfg,
            duration=args.duration,
            control_enabled=(ctrl_type != 'baseline'),
        )
        if run_name == 'baseline':
            # baseline uses adm_cfg timing but holds q_neutral — relabel for clarity
            pass
        m = compute_metrics(data['time_s'], data['tension_filtered_N'], cfg)
        metrics[run_name] = m
        runs[run_name] = data
        save_recording(output_dir, run_name, data, cfg, m)
        print(f"RMS={m['rms_error_N']:.3f} N")

    print('Generating plots ...')
    plot_results(output_dir, runs, adm_cfg, metrics)

    readme = output_dir / 'README.txt'
    readme.write_text(
        'Controller simulation export\n'
        '============================\n\n'
        f'Generated: {stamp}\n'
        f'MJCF: {MJCF}\n'
        f'Duration: {args.duration} s\n'
        f'Target tension: {args.target} N\n\n'
        'Files:\n'
        '  <controller>.npz   — raw arrays + config/metrics metadata\n'
        '  <controller>.csv   — time series for spreadsheets / LaTeX pgfplots\n'
        '  <controller>_metrics.json — RMS/MAE/max tension\n'
        '  comparison_tension.{png,pdf} — overlay tension plots\n'
        '  comparison_position.{png,pdf} — pitch angle comparison\n'
        '  admittance_detail.{png,pdf} — virtual state diagnostics\n'
        '  force_feedback_detail.{png,pdf} — q_eq mapping diagnostics\n'
        '  metrics_summary.{png,pdf,json} — regulation metrics table\n',
    )
    print(f'Done. Artifacts in {output_dir}')


if __name__ == '__main__':
    main()
