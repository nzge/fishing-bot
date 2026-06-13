"""Pure-Python fishing tension controllers ported from the MuJoCo notebooks.

Julie notebook  -> AdmittanceController (virtual mass-spring-damper + PD inner loop)
Chaoyi notebook -> ForceFeedbackController (asymmetric tension-to-angle mapping)

The notebooks model a single pitch DOF. In ROS2, control_dof=1 maps all q_* setpoints
to pitch_joint (Joint_2) while base_joint (Joint_1) is held fixed at joint_1_hold.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Tuple


class FishingState(IntEnum):
    MONITOR = 0
    HOOK_SET = 1
    REGULATE = 2


def smoothstep(s: float) -> float:
    s = max(0.0, min(1.0, s))
    return 3.0 * s * s - 2.0 * s * s * s


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class FishingControllerConfig:
    """Shared configuration for both controller types."""

    target_tension: float = 3.5
    safety_tension_limit: float = 20.0

    # 1 = notebook-equivalent pitch-only (Joint_2); 2 = both arm joints (future).
    control_dof: int = 1
    pitch_joint: str = 'Joint_2'
    base_joint: str = 'Joint_1'
    # Base yaw locked at this angle in 1DOF mode (matches MJCF starting_pose).
    joint_1_hold: float = 1.57

    # Pitch limits and setpoints (radians) — maps to pitch_joint in 1DOF mode.
    q_init: float = 1.745
    q_hook: float = 1.40
    q_neutral: float = 1.605
    q_min: float = 0.10
    q_max: float = 2.20

    # When false, skip MONITOR/HOOK_SET and regulate from t=0 (hardware bring-up).
    fsm_enabled: bool = True

    # State-machine timing (seconds from controller start).
    bite_time: float = 2.4
    hook_duration: float = 1.2

    # Tension signal conditioning (matches notebook FILTER_ALPHA).
    tension_filter_alpha: float = 0.055

    control_rate_hz: float = 50.0


@dataclass
class AdmittanceConfig(FishingControllerConfig):
    """Julie admittance controller parameters."""

    m_v: float = 0.6
    b_v: float = 5.5
    k_v: float = 16.0
    k_f: float = 5.0
    kp_track: float = 140.0
    kd_track: float = 20.0
    ki_track: float = 0.0
    k_g: float = 9.95
    rod_length: float = 0.185
    j_alpha: float = 0.05
    pos_int_limit: float = 0.15
    max_torque: float = 20.0


@dataclass
class ForceFeedbackConfig(FishingControllerConfig):
    """Chaoyi proportional force-feedback controller parameters."""

    tension_to_angle_gain: float = math.radians(42.0)
    qeq_alpha: float = 0.055
    max_qeq_step: float = math.radians(0.22)
    raise_gain: float = 1.25
    lower_gain: float = 0.80


@dataclass
class ControllerSnapshot:
    state: FishingState = FishingState.MONITOR
    tension_raw: float = 0.0
    tension_filtered: float = 0.0
    q_cmd: float = 0.0
    q_dot_cmd: float = 0.0


def get_fishing_state(t: float, cfg: FishingControllerConfig) -> FishingState:
    if not cfg.fsm_enabled:
        return FishingState.REGULATE
    if t < cfg.bite_time:
        return FishingState.MONITOR
    if t < cfg.bite_time + cfg.hook_duration:
        return FishingState.HOOK_SET
    return FishingState.REGULATE


def filter_tension(
    raw: float, prev_filtered: float, alpha: float,
) -> float:
    return (1.0 - alpha) * prev_filtered + alpha * raw


class AdmittanceControllerCore:
    """Virtual admittance outer loop from mojocowithJulieController.ipynb."""

    def __init__(self, cfg: AdmittanceConfig, dt: float):
        self.cfg = cfg
        self.dt = dt
        self.theta_cmd = cfg.q_init
        self.theta_dot_cmd = 0.0
        self.pos_int = 0.0
        self.j_filtered = 0.0
        self._tension_filtered = 0.0

    @property
    def tension_filtered(self) -> float:
        return self._tension_filtered

    def reset(self, q_actual: float) -> None:
        self.theta_cmd = q_actual
        self.theta_dot_cmd = 0.0
        self.pos_int = 0.0
        self.j_filtered = 0.0
        self._tension_filtered = 0.0

    def get_jacobian(
        self,
        theta: float,
        tip_pos: Optional[Tuple[float, float, float]] = None,
        fish_pos: Optional[Tuple[float, float, float]] = None,
    ) -> float:
        """Map pitch rate to line-length rate (notebook get_jacobian)."""
        if tip_pos is not None and fish_pos is not None:
            line_vec = (
                fish_pos[0] - tip_pos[0],
                fish_pos[1] - tip_pos[1],
                fish_pos[2] - tip_pos[2],
            )
            distance = math.sqrt(sum(v * v for v in line_vec))
            if distance < 1e-6:
                return 0.0
            u = tuple(v / distance for v in line_vec)
            l_arm = self.cfg.rod_length
            dx_dtheta = l_arm * math.cos(theta)
            dz_dtheta = -l_arm * math.sin(theta)
            return dx_dtheta * u[0] + dz_dtheta * u[2]

        # Hardware fallback: approximate scalar Jacobian.
        return self.cfg.rod_length * max(abs(math.cos(theta)), 0.05)

    def update_tension(self, tension_raw: float) -> float:
        self._tension_filtered = filter_tension(
            tension_raw, self._tension_filtered, self.cfg.tension_filter_alpha,
        )
        return self._tension_filtered

    def hook_set_target(self, t: float) -> float:
        s = smoothstep((t - self.cfg.bite_time) / self.cfg.hook_duration)
        return self.cfg.q_init + (self.cfg.q_hook - self.cfg.q_init) * s

    def update(
        self,
        t: float,
        state: FishingState,
        f_measured: float,
        theta: float,
        theta_dot: float,
        tip_pos: Optional[Tuple[float, float, float]] = None,
        fish_pos: Optional[Tuple[float, float, float]] = None,
        control_enabled: bool = True,
    ) -> Tuple[float, float]:
        """Return (position_cmd, velocity_cmd) for Joint_2."""
        cfg = self.cfg

        if state == FishingState.MONITOR or not control_enabled:
            f_desired = 0.0
        else:
            f_desired = cfg.target_tension

        force_error = f_desired - f_measured

        j_val = self.get_jacobian(theta, tip_pos, fish_pos)
        self.j_filtered += cfg.j_alpha * (j_val - self.j_filtered)

        tau_force = -(self.j_filtered * force_error) * cfg.k_f
        tau_spring = cfg.k_v * (cfg.q_neutral - self.theta_cmd)

        theta_ddot_cmd = (
            tau_force + tau_spring - cfg.b_v * self.theta_dot_cmd
        ) / cfg.m_v

        self.theta_dot_cmd += theta_ddot_cmd * self.dt
        self.theta_cmd += self.theta_dot_cmd * self.dt
        self.theta_cmd = clip(self.theta_cmd, cfg.q_min, cfg.q_max)

        # Inner PD loop (notebook); on ROS the position_trajectory_controller
        # tracks theta_cmd, but we keep theta_dot_cmd for diagnostics.
        e_pos = self.theta_cmd - theta
        e_vel = self.theta_dot_cmd - theta_dot
        self.pos_int += e_pos * self.dt
        self.pos_int = clip(self.pos_int, -cfg.pos_int_limit, cfg.pos_int_limit)

        _torque = (
            cfg.kp_track * e_pos
            + cfg.kd_track * e_vel
            + cfg.ki_track * self.pos_int
            - cfg.k_g * math.sin(theta)
        )
        _torque = clip(_torque, -cfg.max_torque, cfg.max_torque)

        return self.theta_cmd, self.theta_dot_cmd


class ForceFeedbackControllerCore:
    """Asymmetric tension-to-angle controller from mojocowithchaoyi'scontroller.ipynb."""

    def __init__(self, cfg: ForceFeedbackConfig):
        self.cfg = cfg
        self.q_eq = cfg.q_init
        self._tension_filtered = 0.0

    @property
    def tension_filtered(self) -> float:
        return self._tension_filtered

    def reset(self) -> None:
        self.q_eq = self.cfg.q_init
        self._tension_filtered = 0.0

    def update_tension(self, tension_raw: float) -> float:
        self._tension_filtered = filter_tension(
            tension_raw, self._tension_filtered, self.cfg.tension_filter_alpha,
        )
        return self._tension_filtered

    def update(
        self,
        t: float,
        state: FishingState,
        tension_filtered: float,
        control_enabled: bool = True,
    ) -> Tuple[float, float]:
        """Return (q_eq, q_target) equilibrium pitch angles."""
        cfg = self.cfg

        if state == FishingState.MONITOR:
            q_target = cfg.q_init
        elif state == FishingState.HOOK_SET:
            s = smoothstep((t - cfg.bite_time) / cfg.hook_duration)
            q_target = cfg.q_init + (cfg.q_hook - cfg.q_init) * s
        elif control_enabled:
            tension_error = tension_filtered - cfg.target_tension
            if tension_error < 0.0:
                q_target = (
                    cfg.q_neutral
                    + cfg.raise_gain * cfg.tension_to_angle_gain * tension_error
                )
            else:
                q_target = (
                    cfg.q_neutral
                    + cfg.lower_gain * cfg.tension_to_angle_gain * tension_error
                )
        else:
            q_target = cfg.q_neutral

        q_target = clip(q_target, cfg.q_min, cfg.q_max)

        q_smooth = (1.0 - cfg.qeq_alpha) * self.q_eq + cfg.qeq_alpha * q_target
        q_eq = clip(
            q_smooth,
            self.q_eq - cfg.max_qeq_step,
            self.q_eq + cfg.max_qeq_step,
        )
        q_eq = clip(q_eq, cfg.q_min, cfg.q_max)
        self.q_eq = q_eq
        return q_eq, q_target
