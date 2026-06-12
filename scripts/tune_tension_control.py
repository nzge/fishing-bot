#!/usr/bin/env python3
"""Offline parameter sweep for fishing tension controllers against the ROS MJCF.

Runs headless MuJoCo with the same scene as mujoco_ros2_control and evaluates
RMS tension error during the regulation phase for both controller types.

Usage:
    python3 scripts/tune_tension_control.py
    python3 scripts/tune_tension_control.py --controller force_feedback --target 3.5
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
MJCF = REPO_ROOT / 'software/src/description/urdf/fishing-robot_sim.xml'
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


def fish_pull(t: float, cfg) -> float:
    """Simplified fish disturbance matching fish_agent mean + sinusoid."""
    if t < cfg.bite_time + cfg.hook_duration:
        return 0.0
    tau = t - cfg.bite_time - cfg.hook_duration
    return max(
        3.5
        + 1.2 * math.sin(2.0 * math.pi * 0.5 * tau)
        + 0.3 * math.sin(2.0 * math.pi * 1.1 * tau + 0.5),
        0.0,
    )


def read_tension(model, data, tendon_id, stiffness=220.0):
    """Stretch-based tension matching load_cell sim_fts path."""
    stretch = float(data.ten_length[tendon_id] - model.tendon_lengthspring[tendon_id][0])
    return max(stiffness * stretch, 0.0)


def run_trial(
    controller_type: str,
    cfg,
    duration: float = 18.0,
    settle_steps: int = 300,
) -> dict:
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

    if controller_type == 'admittance':
        core = AdmittanceControllerCore(cfg, dt)
        core.reset(cfg.q_init)
    else:
        core = ForceFeedbackControllerCore(cfg)

    for _ in range(settle_steps):
        data.ctrl[0] = cfg.joint_1_hold
        data.ctrl[1] = cfg.q_init
        data.ctrl[fish_act_id] = 0.0
        mujoco.mj_step(model, data)

    data.time = 0.0
    times, tensions, cmds = [], [], []

    while data.time < duration:
        t = data.time
        state = get_fishing_state(t, cfg)
        mujoco.mj_forward(model, data)

        q2 = data.qpos[j2_qpos]
        q2_dot = data.qvel[j2_qvel]
        tip = data.site_xpos[tip_id].copy()

        pull = fish_pull(t, cfg)

        tension_raw = read_tension(model, data, tendon_id)
        tension = core.update_tension(tension_raw)

        if controller_type == 'admittance':
            if state == FishingState.HOOK_SET:
                q_cmd = core.hook_set_target(t)
                core.reset(q2)
                core.theta_cmd = q_cmd
            elif state == FishingState.REGULATE:
                q_cmd, _ = core.update(
                    t, state, tension, q2, q2_dot, tuple(tip), None,
                )
            else:
                q_cmd = cfg.q_init
        else:
            q_cmd, _ = core.update(t, state, tension)

        data.ctrl[0] = cfg.joint_1_hold
        data.ctrl[1] = q_cmd
        data.ctrl[fish_act_id] = pull if state != FishingState.MONITOR else 0.0
        mujoco.mj_step(model, data)

        times.append(t)
        tensions.append(tension)
        cmds.append(q_cmd)

    reg_start = cfg.bite_time + cfg.hook_duration + 1.0
    mask = np.array(times) > reg_start
    err = np.array(tensions)[mask] - cfg.target_tension
    rms = float(np.sqrt(np.mean(err * err))) if err.size else float('nan')

    return {
        'rms_error': rms,
        'times': np.array(times),
        'tensions': np.array(tensions),
        'cmds': np.array(cmds),
    }


def sweep_force_feedback(target: float) -> None:
    """Grid search Chaoyi gains for minimum RMS tension error."""
    best_rms = float('inf')
    best = None

    for gain_deg in (30.0, 38.0, 42.0, 48.0):
        for alpha in (0.04, 0.055, 0.07):
            cfg = ForceFeedbackConfig(target_tension=target)
            cfg.tension_to_angle_gain = math.radians(gain_deg)
            cfg.qeq_alpha = alpha
            result = run_trial('force_feedback', cfg)
            print(
                f'  gain={gain_deg:4.0f} deg/N  alpha={alpha:.3f}  '
                f'RMS={result["rms_error"]:.3f} N',
            )
            if result['rms_error'] < best_rms:
                best_rms = result['rms_error']
                best = (gain_deg, alpha)

    print(f'\nBest force_feedback: gain={best[0]} deg/N, alpha={best[1]:.3f}, '
          f'RMS={best_rms:.3f} N')


def sweep_admittance(target: float) -> None:
    best_rms = float('inf')
    best = None

    for k_f in (3.0, 5.0, 7.0):
        for k_v in (12.0, 16.0, 20.0):
            cfg = AdmittanceConfig(target_tension=target)
            cfg.k_f = k_f
            cfg.k_v = k_v
            result = run_trial('admittance', cfg)
            print(f'  k_f={k_f:.1f}  k_v={k_v:.1f}  RMS={result["rms_error"]:.3f} N')
            if result['rms_error'] < best_rms:
                best_rms = result['rms_error']
                best = (k_f, k_v)

    print(f'\nBest admittance: k_f={best[0]}, k_v={best[1]}, RMS={best_rms:.3f} N')


def main() -> None:
    parser = argparse.ArgumentParser(description='Tune fishing tension controllers')
    parser.add_argument(
        '--controller', choices=['admittance', 'force_feedback', 'both'],
        default='both',
    )
    parser.add_argument('--target', type=float, default=3.5)
    parser.add_argument('--sweep', action='store_true', help='Run parameter grid search')
    args = parser.parse_args()

    if not MJCF.exists():
        print(f'MJCF not found: {MJCF}')
        sys.exit(1)

    if args.sweep:
        if args.controller in ('force_feedback', 'both'):
            print('=== Force-feedback sweep ===')
            sweep_force_feedback(args.target)
        if args.controller in ('admittance', 'both'):
            print('\n=== Admittance sweep ===')
            sweep_admittance(args.target)
        return

    for ctrl in ('force_feedback', 'admittance'):
        if args.controller != 'both' and args.controller != ctrl:
            continue
        if ctrl == 'force_feedback':
            cfg = ForceFeedbackConfig(target_tension=args.target)
        else:
            cfg = AdmittanceConfig(target_tension=args.target)
        result = run_trial(ctrl, cfg)
        print(f'{ctrl}: RMS tension error = {result["rms_error"]:.3f} N '
              f'(target {args.target} N)')


if __name__ == '__main__':
    main()
