#!/usr/bin/env python3
"""Hardware bring-up self-test (open-loop, no closed-loop control).

Verifies that the ROS 2 pipeline talks to the physical layer:

  * MOTOR  - command each joint a small, slow, absolute move via the trajectory
             controller and confirm /joint_states reports it reaching the target.
  * SENSOR - sample /fishing_arm/tension and confirm it is publishing finite
             values within a sane range.

It deliberately does NOT run the admittance controller (the bringup launch
disables it when hardware_check:=true), so these are pure function checks, not
control behaviour. The exact same test runs in simulation, so you can validate
it with use_sim:=true before trusting it on real hardware.

Prints a PASS/FAIL summary and exits 0 (all passed) or 1 (something failed).
"""
import math
import sys
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from interfaces.msg import FishingTension


class HardwareCheck(Node):
    def __init__(self):
        super().__init__('hardware_check')

        self.declare_parameter('joints', ['Joint_1', 'Joint_2'])
        self.declare_parameter('move_delta', 0.2)            # rad, small & safe
        self.declare_parameter('move_time', 2.0)             # s, slow command
        self.declare_parameter('settle_time', 1.0)           # s, extra to arrive
        self.declare_parameter('position_tolerance', 0.08)   # rad
        self.declare_parameter('startup_timeout', 15.0)      # s, wait for states
        self.declare_parameter('tension_check_duration', 3.0)
        self.declare_parameter('tension_min', -50.0)
        self.declare_parameter('tension_max', 50.0)
        self.declare_parameter('require_tension_variation', False)
        self.declare_parameter('traj_topic', '/position_trajectory_controller/joint_trajectory')

        self.joints = list(self.get_parameter('joints').value)
        self.move_delta = self.get_parameter('move_delta').value
        self.move_time = self.get_parameter('move_time').value
        self.settle_time = self.get_parameter('settle_time').value
        self.position_tolerance = self.get_parameter('position_tolerance').value
        self.startup_timeout = self.get_parameter('startup_timeout').value
        self.tension_check_duration = self.get_parameter('tension_check_duration').value
        self.tension_min = self.get_parameter('tension_min').value
        self.tension_max = self.get_parameter('tension_max').value
        self.require_tension_variation = bool(
            self.get_parameter('require_tension_variation').value)
        self.traj_topic = self.get_parameter('traj_topic').value

        self.joint_pos = {}
        self.tension = []
        self._collect_tension = False

        self.create_subscription(JointState, '/joint_states', self._js_cb, 50)
        self.create_subscription(FishingTension, '/fishing_arm/tension', self._ten_cb, 50)
        self.pub = self.create_publisher(JointTrajectory, self.traj_topic, 10)

    def _js_cb(self, msg):
        for name, pos in zip(msg.name, msg.position):
            self.joint_pos[name] = pos

    def _ten_cb(self, msg):
        if self._collect_tension:
            self.tension.append(msg.tension_newtons)

    def _send(self, positions):
        msg = JointTrajectory()
        msg.joint_names = list(positions.keys())
        point = JointTrajectoryPoint()
        point.positions = [float(positions[j]) for j in msg.joint_names]
        point.time_from_start.sec = int(self.move_time)
        point.time_from_start.nanosec = int((self.move_time % 1.0) * 1e9)
        msg.points.append(point)
        self.pub.publish(msg)

    def _wait_for(self, condition, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return True
            time.sleep(0.05)
        return False

    def run_checks(self):
        results = []

        if not self._wait_for(lambda: all(j in self.joint_pos for j in self.joints),
                              self.startup_timeout):
            missing = [j for j in self.joints if j not in self.joint_pos]
            print(f'[hw-check] FAIL: no /joint_states for {missing} within '
                  f'{self.startup_timeout:.0f}s. Are the controllers + hardware up?')
            return False

        # Wait for the trajectory controller to actually subscribe, otherwise the
        # first command is published into the void (pub/sub discovery race) and the
        # first joint never moves.
        if not self._wait_for(lambda: self.pub.get_subscription_count() > 0,
                              self.startup_timeout):
            print(f'[hw-check] FAIL: no subscriber on {self.traj_topic} - is '
                  f'position_trajectory_controller active?')
            return False
        time.sleep(0.5)

        start = {j: self.joint_pos[j] for j in self.joints}
        print(f'[hw-check] Initial positions: '
              f'{ {j: round(start[j], 3) for j in self.joints} }')

        # ---- MOTOR checks: move each joint, confirm it tracks, then return ----
        for j in self.joints:
            target = dict(start)
            target[j] = start[j] + self.move_delta
            print(f'[hw-check] Commanding {j} {self.move_delta:+.3f} rad '
                  f'-> {target[j]:.3f} ...')
            self._send(target)
            time.sleep(self.move_time + self.settle_time)
            err = abs(self.joint_pos[j] - target[j])
            ok = err < self.position_tolerance
            results.append((f'motor:{j}', ok,
                            f'reached err={err:.3f} rad (tol {self.position_tolerance})'))
            self._send(start)
            time.sleep(self.move_time + self.settle_time)

        # ---- SENSOR check: confirm tension publishes finite, in-range values ----
        print(f'[hw-check] Sampling /fishing_arm/tension for '
              f'{self.tension_check_duration:.1f}s ...')
        self.tension = []
        self._collect_tension = True
        time.sleep(self.tension_check_duration)
        self._collect_tension = False

        n = len(self.tension)
        finite = all(math.isfinite(x) for x in self.tension)
        lo = min(self.tension) if n else float('nan')
        hi = max(self.tension) if n else float('nan')
        in_range = n > 0 and lo >= self.tension_min and hi <= self.tension_max
        varied = (hi - lo) > 1e-6 if n else False
        sensor_ok = (n > 0 and finite and in_range
                     and (varied or not self.require_tension_variation))
        detail = f'{n} samples'
        if n:
            detail += f', range [{lo:.2f}, {hi:.2f}] N'
        if not finite:
            detail += ', NON-FINITE values'
        results.append(('sensor:tension', sensor_ok, detail))

        # ---- Summary ----
        print('\n===== HARDWARE CHECK SUMMARY =====')
        all_ok = True
        for name, ok, detail in results:
            all_ok = all_ok and ok
            print(f'  [{"PASS" if ok else "FAIL"}] {name:18s} {detail}')
        print('===== ' + ('ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED')
              + ' =====\n')
        return all_ok


def main(args=None):
    rclpy.init(args=args)
    node = HardwareCheck()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    passed = False
    try:
        passed = node.run_checks()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
