#!/usr/bin/env python3
"""Recorder: logs the run, plots it, and triggers the MuJoCo animation render.

Toggled by record:=true in the bringup launch. It subscribes to the joint
states and the line-tension sensor, buffers the time series, and on shutdown:

  1. Writes a PNG with joint positions, motor effort (torque) and the measured
     vs target line tension (so you can see if tension is held constant).
  2. Saves the raw time series + the joint trajectory to an .npz file.
  3. Auto-spawns the offscreen animation renderer (render_animation.py) under
     the .venv python, because MuJoCo lives there, not in the ROS python env.

Everything here uses only rclpy + numpy + matplotlib (all available to the ROS
python), keeping the node light; the heavy MuJoCo rendering is a separate
process fed the .npz.
"""
import datetime
import os
import subprocess

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from interfaces.msg import FishingTension


class Recorder(Node):
    def __init__(self):
        super().__init__('recorder')

        # Where artifacts are written. Empty -> a timestamped dir under ~.
        self.declare_parameter('output_dir', '')
        # MJCF + render script. Empty -> resolved from the package shares.
        self.declare_parameter('mjcf_path', '')
        self.declare_parameter('render_script', '')
        # The python that can import mujoco (the project virtualenv).
        self.declare_parameter('venv_python', os.path.expanduser('~/fishing-bot/.venv/bin/python'))
        self.declare_parameter('auto_render', True)
        self.declare_parameter('video_format', 'mp4')   # 'mp4' or 'gif'
        self.declare_parameter('video_fps', 30)
        # MJCF qpos order (used to rebuild the trajectory for the renderer).
        self.declare_parameter('qpos_joints', ['Joint_1', 'Joint_2', 'fish_swim'])
        # Joints whose effort/torque we plot.
        self.declare_parameter('arm_joints', ['Joint_1', 'Joint_2'])

        self.output_dir = self.get_parameter('output_dir').value
        self.mjcf_path = self.get_parameter('mjcf_path').value
        self.render_script = self.get_parameter('render_script').value
        self.venv_python = self.get_parameter('venv_python').value
        self.auto_render = bool(self.get_parameter('auto_render').value)
        self.video_format = self.get_parameter('video_format').value
        self.video_fps = int(self.get_parameter('video_fps').value)
        self.qpos_joints = list(self.get_parameter('qpos_joints').value)
        self.arm_joints = list(self.get_parameter('arm_joints').value)

        self._resolve_paths()

        # Buffers.
        self.js_t = []
        self.qpos_rows = []                       # one row per JointState msg
        self.eff = {j: [] for j in self.arm_joints}
        self.eff_t = []
        self.ten_t = []
        self.ten = []
        self.ten_target = []

        self.create_subscription(JointState, '/joint_states', self._js_cb, 50)
        self.create_subscription(FishingTension, '/fishing_arm/tension', self._ten_cb, 50)

        self.get_logger().info(
            f'Recorder active. Artifacts -> {self.output_dir} '
            f'(auto_render={self.auto_render}, format={self.video_format}).')

    def _resolve_paths(self):
        from ament_index_python.packages import get_package_share_directory
        # output_dir is a BASE directory; every run gets its own timestamped
        # subfolder so recordings never overwrite each other.
        base = self.output_dir or os.path.expanduser('~/fishing_recordings')
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = os.path.join(base, stamp)
        os.makedirs(self.output_dir, exist_ok=True)
        if not self.mjcf_path:
            self.mjcf_path = os.path.join(
                get_package_share_directory('description'), 'urdf', 'fishing-robot_sim.xml')
        if not self.render_script:
            self.render_script = os.path.join(
                get_package_share_directory('diagnostics'), 'scripts', 'render_animation.py')

    def _now(self):
        # Stamp every sample with the recorder's own clock so all topics share
        # one time base, regardless of each publisher's use_sim_time setting.
        return self.get_clock().now().nanoseconds * 1e-9

    def _js_cb(self, msg):
        name_to_pos = dict(zip(msg.name, msg.position))
        if not all(j in name_to_pos for j in self.qpos_joints):
            return
        now = self._now()
        self.js_t.append(now)
        self.qpos_rows.append([name_to_pos[j] for j in self.qpos_joints])
        if msg.effort and len(msg.effort) == len(msg.name):
            name_to_eff = dict(zip(msg.name, msg.effort))
            self.eff_t.append(now)
            for j in self.arm_joints:
                self.eff[j].append(name_to_eff.get(j, float('nan')))

    def _ten_cb(self, msg):
        self.ten_t.append(self._now())
        self.ten.append(msg.tension_newtons)
        self.ten_target.append(msg.target_tension_newtons)

    def save_and_render(self):
        if not self.js_t and not self.ten_t:
            print('[recorder] No data captured; nothing to save.')
            return

        # Normalize all clocks to start at t=0 for readability.
        t0 = min([t for t in (self.js_t[:1] + self.ten_t[:1])] or [0.0])
        js_t = np.array(self.js_t) - t0
        qpos = np.array(self.qpos_rows) if self.qpos_rows else np.empty((0, len(self.qpos_joints)))
        eff_t = np.array(self.eff_t) - t0 if self.eff_t else np.array([])
        ten_t = np.array(self.ten_t) - t0 if self.ten_t else np.array([])
        ten = np.array(self.ten)
        ten_target = np.array(self.ten_target)

        npz_path = os.path.join(self.output_dir, 'recording.npz')
        np.savez(
            npz_path,
            times=js_t, qpos=qpos, qpos_joints=np.array(self.qpos_joints),
            eff_t=eff_t, eff=np.array([self.eff[j] for j in self.arm_joints]),
            arm_joints=np.array(self.arm_joints),
            ten_t=ten_t, tension=ten, tension_target=ten_target,
            mjcf_path=self.mjcf_path)
        print(f'[recorder] Saved data -> {npz_path}')

        self._plot(js_t, qpos, eff_t, ten_t, ten, ten_target)
        self._spawn_render(npz_path)

    def _plot(self, js_t, qpos, eff_t, ten_t, ten, ten_target):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError as exc:
            print(f'[recorder] matplotlib unavailable ({exc}); skipping plots.')
            return

        fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

        ax = axes[0]
        for i, j in enumerate(self.qpos_joints):
            if qpos.size:
                ax.plot(js_t, qpos[:, i], label=j)
        ax.set_ylabel('position [rad / m]')
        ax.set_title('Joint positions')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        ax = axes[1]
        for i, j in enumerate(self.arm_joints):
            if eff_t.size and len(self.eff[j]) == len(eff_t):
                ax.plot(eff_t, self.eff[j], label=j)
        ax.set_ylabel('effort [N·m]')
        ax.set_title('Motor effort (torque)')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        ax = axes[2]
        if ten_t.size:
            ax.plot(ten_t, ten, label='measured', color='tab:blue')
            if np.any(np.asarray(ten_target) != 0.0):
                ax.plot(ten_t, ten_target, label='target', color='tab:red', linestyle='--')
        ax.set_ylabel('tension [N]')
        ax.set_xlabel('time [s]')
        ax.set_title('Line tension (constant-tension tracking)')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        fig.tight_layout()
        png_path = os.path.join(self.output_dir, 'diagnostics.png')
        fig.savefig(png_path, dpi=120)
        plt.close(fig)
        print(f'[recorder] Saved plots -> {png_path}')

    def _spawn_render(self, npz_path):
        video_path = os.path.join(self.output_dir, f'animation.{self.video_format}')
        if not self.auto_render:
            print('[recorder] auto_render disabled. Render manually with:')
            print(f'  {self.venv_python} {self.render_script} {npz_path} '
                  f'--output {video_path} --fps {self.video_fps}')
            return
        if not os.path.exists(self.venv_python):
            print(f'[recorder] venv python not found at {self.venv_python}; '
                  f'cannot auto-render. Run manually:')
            print(f'  <python-with-mujoco> {self.render_script} {npz_path} '
                  f'--output {video_path} --fps {self.video_fps}')
            return
        cmd = [self.venv_python, self.render_script, npz_path,
               '--output', video_path, '--fps', str(self.video_fps)]
        # Detach into its own session so the launch teardown (process-group
        # SIGINT/SIGKILL) does not kill the render before it finishes.
        subprocess.Popen(cmd, start_new_session=True)
        print(f'[recorder] Rendering animation in background -> {video_path}')


def main(args=None):
    rclpy.init(args=args)
    node = Recorder()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.save_and_render()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
