#!/usr/bin/env python3
import math
from collections import deque

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import WrenchStamped
from interfaces.msg import FishingTension


class LoadCellPublisher(Node):
    def __init__(self):
        # Node name matches the key in sensor_params.yaml so params load correctly.
        super().__init__('load_cell_node')

        # Defensive Coding: Parameterization (No Magic Numbers).
        self.declare_parameter('calibration_offset', 0.0)
        self.declare_parameter('calibration_scale', 1.0)
        self.declare_parameter('use_moving_average', True)
        self.declare_parameter('window_size', 10)
        self.declare_parameter('publish_frequency', 80.0)
        self.declare_parameter('tension_max_threshold', 20.0)
        self.declare_parameter('noise_floor', 0.1)
        self.declare_parameter('frame_id', 'rod_tip_link')
        # 'hardware' = read the HX711 load cell; 'sim_fts' = derive tension from the
        # MuJoCo force/torque sensor published by force_torque_sensor_broadcaster.
        self.declare_parameter('source', 'hardware')
        self.declare_parameter('wrench_topic', '/tension_sensor_broadcaster/wrench')

        self.calibration_offset = self.get_parameter('calibration_offset').value
        self.calibration_scale = self.get_parameter('calibration_scale').value
        self.use_moving_average = self.get_parameter('use_moving_average').value
        self.window_size = int(self.get_parameter('window_size').value)
        self.publish_frequency = self.get_parameter('publish_frequency').value
        self.tension_max_threshold = self.get_parameter('tension_max_threshold').value
        self.noise_floor = self.get_parameter('noise_floor').value
        self.frame_id = self.get_parameter('frame_id').value
        self.source = self.get_parameter('source').value
        self.wrench_topic = self.get_parameter('wrench_topic').value

        self.publisher_ = self.create_publisher(FishingTension, '/fishing_arm/tension', 10)
        self.buffer = deque(maxlen=self.window_size)

        # Latest force vector from the simulated FTS (None until first message).
        self._latest_force = None
        if self.source == 'sim_fts':
            self.wrench_sub = self.create_subscription(
                WrenchStamped, self.wrench_topic, self._wrench_cb, 10)

        self.timer_period = 1.0 / self.publish_frequency
        self.timer = self.create_timer(self.timer_period, self.timer_callback)
        self.time_counter = 0.0

        self.get_logger().info(
            f'Load Cell Publisher initialized at {self.publish_frequency:.1f} Hz '
            f'(source: {self.source}, frame: {self.frame_id}).')

    def _wrench_cb(self, msg):
        f = msg.wrench.force
        self._latest_force = (f.x, f.y, f.z)

    def read_raw_adc(self):
        # --- PLACEHOLDER FOR HARDWARE READ (HX711 SPI/Serial) ---
        # Until the real driver is wired in, mimic a raw ADC count: a tension
        # bias plus a small wave fluctuation, expressed in raw counts.
        base_tension = 10.0
        wave_disturbance = 2.0 * math.sin(2.0 * math.pi * 1.0 * self.time_counter)
        simulated_newtons = base_tension + wave_disturbance
        return self.calibration_offset + simulated_newtons / self.calibration_scale

    def read_tension_newtons(self):
        # In sim, the load cell IS the MuJoCo force sensor: tension is the
        # magnitude of the force transmitted through the rod-tip site.
        if self.source == 'sim_fts':
            if self._latest_force is None:
                return 0.0
            fx, fy, fz = self._latest_force
            return math.sqrt(fx * fx + fy * fy + fz * fz)
        # On hardware, convert raw ADC counts into Newtons via calibration.
        raw = self.read_raw_adc()
        return (raw - self.calibration_offset) * self.calibration_scale

    def timer_callback(self):
        tension = self.read_tension_newtons()

        # Reject sub-threshold readings as sensor noise.
        if abs(tension) < self.noise_floor:
            tension = 0.0

        # Optional moving-average smoothing.
        if self.use_moving_average:
            self.buffer.append(tension)
            tension = sum(self.buffer) / len(self.buffer)

        msg = FishingTension()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.tension_newtons = float(tension)
        # The sensor only MEASURES tension; the desired setpoint is owned by the
        # controller (admittance_controller's 'target_tension' parameter).
        msg.target_tension_newtons = 0.0
        self.publisher_.publish(msg)

        if tension > self.tension_max_threshold:
            self.get_logger().warn(
                f'Line tension {tension:.2f} N exceeds threshold '
                f'{self.tension_max_threshold:.2f} N.')

        # Throttle console logging so it does not flood the terminal.
        if int(self.time_counter * self.publish_frequency) % int(self.publish_frequency) == 0:
            self.get_logger().info(f'Publishing line tension: {tension:.2f} N')

        self.time_counter += self.timer_period


def main(args=None):
    rclpy.init(args=args)
    node = LoadCellPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
