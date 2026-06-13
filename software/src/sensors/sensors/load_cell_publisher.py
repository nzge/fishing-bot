#!/usr/bin/env python3
import math
from collections import deque
from typing import Optional

import rclpy
import serial
from rclpy.node import Node
from geometry_msgs.msg import WrenchStamped
from interfaces.msg import FishingTension
from tf2_ros import Buffer, TransformListener

from sensors.arduino_load_cell import ArduinoLoadCellReader


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
        # 'hardware' = HX711 via Arduino serial; 'sim_fts' = MuJoCo line-tension estimate.
        self.declare_parameter('source', 'hardware')
        self.declare_parameter('wrench_topic', '/tension_sensor_broadcaster/wrench')
        # Arduino HX711 path (project_w_t_controller.ipynb protocol).
        self.declare_parameter('arduino_port', '/dev/ttyACM0')
        self.declare_parameter('arduino_baud', 9600)
        self.declare_parameter('arduino_timeout_s', 0.05)
        self.declare_parameter('tare_on_start', True)
        self.declare_parameter('tare_samples', 20)
        self.declare_parameter('sensor_sign', 1.0)
        self.declare_parameter('sensor_line_filter_window', 2)
        # Sim stretch model (matches fishing-robot_sim.xml tendon parameters).
        self.declare_parameter('sim_line_stiffness', 220.0)
        self.declare_parameter('sim_line_springlength', 0.20)
        self.declare_parameter('sim_line_damping', 1.5)
        self.declare_parameter('sim_rod_frame', 'rod_tip_link')
        self.declare_parameter('sim_fish_frame', 'fish_link')

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
        self.arduino_port = self.get_parameter('arduino_port').value
        self.arduino_baud = int(self.get_parameter('arduino_baud').value)
        self.arduino_timeout_s = float(self.get_parameter('arduino_timeout_s').value)
        self.tare_on_start = bool(self.get_parameter('tare_on_start').value)
        self.tare_samples = int(self.get_parameter('tare_samples').value)
        self.sensor_sign = float(self.get_parameter('sensor_sign').value)
        self.sensor_line_filter_window = int(
            self.get_parameter('sensor_line_filter_window').value)
        self.sim_line_stiffness = self.get_parameter('sim_line_stiffness').value
        self.sim_line_springlength = self.get_parameter('sim_line_springlength').value
        self.sim_line_damping = self.get_parameter('sim_line_damping').value
        self.sim_rod_frame = self.get_parameter('sim_rod_frame').value
        self.sim_fish_frame = self.get_parameter('sim_fish_frame').value

        self.publisher_ = self.create_publisher(FishingTension, '/fishing_arm/tension', 10)
        self.buffer = deque(maxlen=self.window_size)

        self._latest_force = None
        self._prev_line_length = None
        self._prev_line_time = None
        self._arduino: Optional[ArduinoLoadCellReader] = None
        self._last_filtered_raw: Optional[float] = None
        self._last_tension = 0.0
        self._hardware_samples = 0

        if self.source == 'sim_fts':
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, self)
            self.wrench_sub = self.create_subscription(
                WrenchStamped, self.wrench_topic, self._wrench_cb, 10)
        elif self.source == 'hardware':
            self._init_hardware_reader()

        self.timer_period = 1.0 / self.publish_frequency
        self.timer = self.create_timer(self.timer_period, self.timer_callback)
        self.time_counter = 0.0

        self.get_logger().info(
            f'Load Cell Publisher initialized at {self.publish_frequency:.1f} Hz '
            f'(source: {self.source}, frame: {self.frame_id}).')

    def _init_hardware_reader(self) -> None:
        reader = ArduinoLoadCellReader(
            port=self.arduino_port,
            baud=self.arduino_baud,
            timeout_s=self.arduino_timeout_s,
            filter_window=self.sensor_line_filter_window,
            tare_samples=self.tare_samples,
        )
        try:
            reader.open()
        except serial.SerialException as exc:
            raise RuntimeError(
                f'Failed to open Arduino load cell on {self.arduino_port}: {exc}',
            ) from exc

        zero_offset = self.calibration_offset
        if self.tare_on_start:
            self.get_logger().info(
                'Taring load cell — keep the line unloaded for a moment...')
            zero_offset = reader.tare()
            self.get_logger().info(f'Tare complete. zero_offset={zero_offset:.1f}')
        else:
            reader.zero_offset = zero_offset
            self.get_logger().info(
                f'Using fixed calibration_offset={zero_offset:.1f} (tare_on_start=false)',
            )

        self._arduino = reader
        self.calibration_offset = zero_offset
        self.get_logger().info(
            f'Arduino HX711 reader active on {self.arduino_port} @ {self.arduino_baud} baud, '
            f'scale={self.calibration_scale:.6g} N/count.',
        )

    def destroy_node(self) -> bool:
        if self._arduino is not None:
            self._arduino.close()
            self._arduino = None
        return super().destroy_node()

    def _wrench_cb(self, msg):
        f = msg.wrench.force
        self._latest_force = (f.x, f.y, f.z)

    def _line_length_from_tf(self) -> Optional[float]:
        try:
            tf = self._tf_buffer.lookup_transform(
                self.sim_rod_frame,
                self.sim_fish_frame,
                rclpy.time.Time(),
            )
        except Exception:
            return None
        t = tf.transform.translation
        return math.sqrt(t.x * t.x + t.y * t.y + t.z * t.z)

    def _sim_stretch_tension(self) -> Optional[float]:
        """Hooke's-law line model: k*(L-L0) + c*dL/dt (matches MJCF tendon)."""
        length = self._line_length_from_tf()
        if length is None:
            return None

        stretch = max(length - self.sim_line_springlength, 0.0)
        tension = self.sim_line_stiffness * stretch

        now = self.get_clock().now()
        if self._prev_line_length is not None and self._prev_line_time is not None:
            dt = (now - self._prev_line_time).nanoseconds / 1e9
            if dt > 1e-6:
                rate = (length - self._prev_line_length) / dt
                if rate > 0.0:
                    tension += self.sim_line_damping * rate

        self._prev_line_length = length
        self._prev_line_time = now
        return max(tension, 0.0)

    def _raw_to_newtons(self, filtered_raw: float) -> float:
        return (
            self.sensor_sign
            * self.calibration_scale
            * (filtered_raw - self.calibration_offset)
        )

    def read_hardware_tension_newtons(self) -> Optional[float]:
        """Read one Arduino sample; return None if no new line this cycle."""
        if self._arduino is None:
            return None
        filtered_raw = self._arduino.read_filtered_raw()
        if filtered_raw is None:
            return None
        self._last_filtered_raw = filtered_raw
        self._hardware_samples += 1
        return self._raw_to_newtons(filtered_raw)

    def read_tension_newtons(self) -> float:
        if self.source == 'sim_fts':
            stretch_tension = self._sim_stretch_tension()
            if stretch_tension is not None:
                return stretch_tension
            if self._latest_force is None:
                return 0.0
            fx, fy, fz = self._latest_force
            return math.sqrt(fx * fx + fy * fy + fz * fz)

        tension = self.read_hardware_tension_newtons()
        if tension is not None:
            self._last_tension = tension
            return tension
        # Hold last reading until the next serial line arrives.
        return self._last_tension

    def timer_callback(self):
        tension = self.read_tension_newtons()

        if abs(tension) < self.noise_floor:
            tension = 0.0

        if self.use_moving_average:
            self.buffer.append(tension)
            tension = sum(self.buffer) / len(self.buffer)

        msg = FishingTension()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.tension_newtons = float(tension)
        msg.target_tension_newtons = 0.0
        self.publisher_.publish(msg)

        if tension > self.tension_max_threshold:
            self.get_logger().warn(
                f'Line tension {tension:.2f} N exceeds threshold '
                f'{self.tension_max_threshold:.2f} N.')

        if int(self.time_counter * self.publish_frequency) % int(self.publish_frequency) == 0:
            detail = ''
            if self.source == 'hardware' and self._last_filtered_raw is not None:
                detail = f' (raw={self._last_filtered_raw:.0f})'
            self.get_logger().info(f'Publishing line tension: {tension:.2f} N{detail}')

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
