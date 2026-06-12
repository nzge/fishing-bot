"""Shared ROS2 node base for fishing tension controllers."""
from __future__ import annotations

from typing import Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from interfaces.msg import FishingTension

from control.fishing_control_core import (
    AdmittanceConfig,
    AdmittanceControllerCore,
    ControllerSnapshot,
    FishingControllerConfig,
    FishingState,
    ForceFeedbackConfig,
    ForceFeedbackControllerCore,
    get_fishing_state,
)


def _load_fishing_config(node: Node, defaults: FishingControllerConfig) -> FishingControllerConfig:
    """Load parameters from the node's namespace (params.yaml keyed by node name)."""
    cfg = FishingControllerConfig()
    for name in defaults.__dataclass_fields__:
        default = getattr(defaults, name)
        node.declare_parameter(name, default)
        setattr(cfg, name, node.get_parameter(name).value)
    return cfg


def load_admittance_config(node: Node) -> AdmittanceConfig:
    base = _load_fishing_config(node, FishingControllerConfig())
    cfg = AdmittanceConfig(**base.__dict__)
    for name in (
        'm_v', 'b_v', 'k_v', 'k_f', 'kp_track', 'kd_track', 'ki_track',
        'k_g', 'rod_length', 'j_alpha', 'pos_int_limit', 'max_torque',
    ):
        default = getattr(cfg, name)
        node.declare_parameter(name, default)
        setattr(cfg, name, node.get_parameter(name).value)
    return cfg


def load_force_feedback_config(node: Node) -> ForceFeedbackConfig:
    base = _load_fishing_config(node, FishingControllerConfig())
    cfg = ForceFeedbackConfig(**base.__dict__)
    for name in (
        'tension_to_angle_gain', 'qeq_alpha', 'max_qeq_step',
        'raise_gain', 'lower_gain',
    ):
        default = getattr(cfg, name)
        node.declare_parameter(name, default)
        setattr(cfg, name, node.get_parameter(name).value)
    return cfg


class FishingControllerBase(Node):
    """Common subscriptions, safety checks, and trajectory publishing."""

    def __init__(self, node_name: str, cfg: FishingControllerConfig):
        super().__init__(node_name)
        self.cfg = cfg
        self._start_time = self.get_clock().now()
        self._base_pos = cfg.joint_1_hold
        self._pitch_pos = cfg.q_init
        self._pitch_vel = 0.0
        self._tension_raw = 0.0
        self._tension_received = False
        self._estop = False
        self._fish_pos: Optional[Tuple[float, float, float]] = None
        self._tip_pos: Optional[Tuple[float, float, float]] = None
        self.snapshot = ControllerSnapshot(q_cmd=cfg.q_init)

        self._traj_pub = self.create_publisher(
            JointTrajectory,
            '/position_trajectory_controller/joint_trajectory',
            10,
        )
        self.create_subscription(
            FishingTension, '/fishing_arm/tension', self._tension_cb, 10,
        )
        self.create_subscription(JointState, '/joint_states', self._joint_state_cb, 10)

        period = 1.0 / cfg.control_rate_hz
        self.create_timer(period, self._control_timer)

        if cfg.control_dof == 1:
            self.get_logger().info(
                f'{node_name} ready — 1DOF pitch on {cfg.pitch_joint} '
                f'({cfg.base_joint} locked at {cfg.joint_1_hold:.3f} rad), '
                f'target={cfg.target_tension:.2f} N.',
            )
        elif cfg.control_dof == 2:
            self.get_logger().warn(
                f'{node_name}: control_dof=2 is not implemented yet; '
                f'behaving as 1DOF on {cfg.pitch_joint}.',
            )
        else:
            self.get_logger().error(
                f'{node_name}: unsupported control_dof={cfg.control_dof}.',
            )

    def _elapsed(self) -> float:
        return (self.get_clock().now() - self._start_time).nanoseconds / 1e9

    def _tension_cb(self, msg: FishingTension) -> None:
        self._tension_raw = msg.tension_newtons
        self._tension_received = True

    def _joint_state_cb(self, msg: JointState) -> None:
        names = list(msg.name)
        cfg = self.cfg
        if cfg.base_joint in names:
            self._base_pos = msg.position[names.index(cfg.base_joint)]
        if cfg.pitch_joint in names:
            idx = names.index(cfg.pitch_joint)
            self._pitch_pos = msg.position[idx]
            if idx < len(msg.velocity):
                self._pitch_vel = msg.velocity[idx]

    def _check_safety(self) -> bool:
        if not self._tension_received:
            return False
        if abs(self._tension_raw) > self.cfg.safety_tension_limit:
            if not self._estop:
                self.get_logger().warn(
                    f'Tension {self._tension_raw:.2f} N exceeds safety limit '
                    f'{self.cfg.safety_tension_limit:.2f} N. Holding position.',
                )
                self._estop = True
            return False
        self._estop = False
        return True

    def _publish_position(self, pitch_cmd: float) -> None:
        """Publish trajectory commands for the active control DOF."""
        cfg = self.cfg
        traj = JointTrajectory()
        point = JointTrajectoryPoint()

        if cfg.control_dof == 1:
            # 1DOF: notebook logic drives pitch only; base joint stays fixed.
            traj.joint_names = [cfg.base_joint, cfg.pitch_joint]
            point.positions = [cfg.joint_1_hold, pitch_cmd]
        else:
            # Reserved for future 2DOF — pitch_cmd reused as pitch setpoint only.
            traj.joint_names = [cfg.pitch_joint]
            point.positions = [pitch_cmd]

        point.time_from_start = Duration(seconds=0.1).to_msg()
        traj.points.append(point)
        self._traj_pub.publish(traj)
        self.snapshot.q_cmd = pitch_cmd

    def _control_timer(self) -> None:
        raise NotImplementedError


class AdmittanceControllerNode(FishingControllerBase):
    """ROS2 wrapper for Julie's admittance controller."""

    def __init__(self):
        cfg = load_admittance_config(self)
        super().__init__('admittance_controller', cfg)
        dt = 1.0 / cfg.control_rate_hz
        self._core = AdmittanceControllerCore(cfg, dt)
        self._core.reset(self._pitch_pos)
        self.get_logger().info('Admittance (Julie) controller active.')

    def _control_timer(self) -> None:
        if not self._check_safety():
            return

        t = self._elapsed()
        state = get_fishing_state(t, self.cfg)
        tension = self._core.update_tension(self._tension_raw)

        self.snapshot.state = state
        self.snapshot.tension_raw = self._tension_raw
        self.snapshot.tension_filtered = tension

        if state == FishingState.HOOK_SET:
            q_cmd = self._core.hook_set_target(t)
            self._core.reset(self._pitch_pos)
            self._core.theta_cmd = q_cmd
        elif state == FishingState.REGULATE:
            q_cmd, q_dot = self._core.update(
                t=t,
                state=state,
                f_measured=tension,
                theta=self._pitch_pos,
                theta_dot=self._pitch_vel,
                tip_pos=self._tip_pos,
                fish_pos=self._fish_pos,
                control_enabled=True,
            )
            self.snapshot.q_dot_cmd = q_dot
        else:
            q_cmd = self.cfg.q_init

        self._publish_position(q_cmd)


class ForceFeedbackControllerNode(FishingControllerBase):
    """ROS2 wrapper for Chaoyi's proportional force-feedback controller."""

    def __init__(self):
        cfg = load_force_feedback_config(self)
        super().__init__('force_feedback_controller', cfg)
        self._core = ForceFeedbackControllerCore(cfg)
        self.get_logger().info('Force-feedback (Chaoyi) controller active.')

    def _control_timer(self) -> None:
        if not self._check_safety():
            return

        t = self._elapsed()
        state = get_fishing_state(t, self.cfg)
        tension = self._core.update_tension(self._tension_raw)

        self.snapshot.state = state
        self.snapshot.tension_raw = self._tension_raw
        self.snapshot.tension_filtered = tension

        q_cmd, _ = self._core.update(
            t=t,
            state=state,
            tension_filtered=tension,
            control_enabled=True,
        )
        self._publish_position(q_cmd)
