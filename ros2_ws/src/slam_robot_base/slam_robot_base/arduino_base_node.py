import math
import threading
import time
from dataclasses import dataclass
from typing import Optional

import rclpy
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

try:
    import serial
except ImportError:  # pragma: no cover - reported cleanly at runtime
    serial = None


@dataclass
class ArduinoStatus:
    arduino_millis: int
    left_count: int
    right_count: int
    left_tps: int
    right_tps: int
    left_pwm: int
    right_pwm: int
    raw: str


@dataclass
class ArduinoBatteryStatus:
    arduino_millis: int
    source: int
    adc_raw: int
    supply_mv: int
    raw: str


class ArduinoBaseNode(Node):
    """Bridge /cmd_vel to the Arduino Nano line protocol and publish odometry.

    The Arduino firmware accepts target wheel speeds in encoder ticks/second:

        V <left_ticks_per_sec> <right_ticks_per_sec>\n
    and emits periodic status:

        E <millis> <left_position> <right_position> <left_tps> <right_tps> <left_pwm> <right_pwm>\n

    Battery/supply status is polled on demand:

        B\n
    and reported as:

        B <millis> <source> <adc_raw> <v_supply_mV>\n
        source: 0=unknown, 1=battery, 2=dc_external

    The firmware reports signed positions (positive for forward, negative for
    backward) with direction inferred from the target velocity sign. The ROS
    node applies static left_encoder_sign / right_encoder_sign for calibration.
    This node deliberately defaults to motors_enabled=False. In that mode it
    still opens the serial port and publishes Arduino status, but it sends safe
    stop/zero commands regardless of /cmd_vel. Set motors_enabled:=true only
    when the robot is lifted or otherwise safe to move.
    """

    def __init__(self) -> None:
        super().__init__('arduino_base_node')

        self.declare_parameter('port', '/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0')
        self.declare_parameter('baud', 115200)
        self.declare_parameter('base_frame_id', 'base_link')
        self.declare_parameter('odom_frame_id', 'odom')
        self.declare_parameter('track_width_m', 0.155)
        self.declare_parameter('wheel_radius_m', 0.029)
        self.declare_parameter('ticks_per_rev', 360.0)
        self.declare_parameter('ticks_per_meter', 0.0)
        self.declare_parameter('left_ticks_per_rev', 0.0)
        self.declare_parameter('right_ticks_per_rev', 0.0)
        self.declare_parameter('left_ticks_per_meter', 0.0)
        self.declare_parameter('right_ticks_per_meter', 0.0)
        self.declare_parameter('left_encoder_sign', 1.0)
        self.declare_parameter('right_encoder_sign', 1.0)
        # Direction is inferred from the motor's commanded direction in the
        # firmware (single-channel tachometer workaround). These command-sign
        # parameters map /cmd_vel linear/angular to Arduino target tps and
        # also determine the odometry sign via the firmware's direction logic.
        # The encoder-sign parameters below are fine-calibration only.
        self.declare_parameter('left_command_sign', 1.0)
        self.declare_parameter('right_command_sign', 1.0)
        self.declare_parameter('max_linear_mps', 0.20)
        self.declare_parameter('max_angular_rps', 1.0)
        self.declare_parameter('max_target_tps', 250.0)
        self.declare_parameter('cmd_vel_timeout_s', 0.5)
        self.declare_parameter('command_rate_hz', 20.0)
        self.declare_parameter('serial_read_rate_hz', 100.0)
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('motors_enabled', False)
        self.declare_parameter('send_zero_when_disabled', True)

        # Odometry covariance placeholders (m^2 and (rad/s)^2).
        # These are the uncertainty the filter should assume about the raw
        # encoder pose/twist. They are NOT sensor noise — they encode how much
        # you trust wheel odom vs the EKF/SLAM. For a tracked base, yaw is the
        # weakest channel (track slip), so pose yaw covariance should be much
        # larger than x/y. Tune with scripts/calibrate_odom_cov.py.
        self.declare_parameter('odom_pose_x_cov', 0.05)
        self.declare_parameter('odom_pose_y_cov', 0.05)
        self.declare_parameter('odom_pose_yaw_cov', 0.20)
        self.declare_parameter('odom_twist_vx_cov', 0.10)
        self.declare_parameter('odom_twist_vyaw_cov', 0.05)

        # Battery/supply sensing (polled from Arduino via 'B' command).
        self.declare_parameter('battery_poll_period_s', 5.0)
        self.declare_parameter('battery_frame_id', 'base_link')
        self.declare_parameter('battery_location', 'base')
        self.declare_parameter('battery_voltage_scale', 0.9346)
        self.declare_parameter('battery_source_dc_min_v', 8.7)
        self.declare_parameter('battery_voltage_min_v', 6.0)
        self.declare_parameter('battery_voltage_max_v', 9.5)
        self.declare_parameter('battery_full_voltage', 8.4)
        self.declare_parameter('battery_empty_voltage', 6.6)

        self.port = self.get_parameter('port').value
        self.baud = int(self.get_parameter('baud').value)
        self.base_frame_id = self.get_parameter('base_frame_id').value
        self.odom_frame_id = self.get_parameter('odom_frame_id').value
        self.track_width_m = float(self.get_parameter('track_width_m').value)
        self.wheel_radius_m = float(self.get_parameter('wheel_radius_m').value)
        self.ticks_per_rev = float(self.get_parameter('ticks_per_rev').value)
        configured_tpm = float(self.get_parameter('ticks_per_meter').value)
        if configured_tpm > 0.0:
            default_ticks_per_meter = configured_tpm
        else:
            default_ticks_per_meter = self.ticks_per_rev / (2.0 * math.pi * self.wheel_radius_m)

        left_tpr = float(self.get_parameter('left_ticks_per_rev').value)
        right_tpr = float(self.get_parameter('right_ticks_per_rev').value)
        configured_left_tpm = float(self.get_parameter('left_ticks_per_meter').value)
        configured_right_tpm = float(self.get_parameter('right_ticks_per_meter').value)

        self.left_ticks_per_meter = self.resolve_ticks_per_meter(
            configured_left_tpm, left_tpr, self.wheel_radius_m, default_ticks_per_meter
        )
        self.right_ticks_per_meter = self.resolve_ticks_per_meter(
            configured_right_tpm, right_tpr, self.wheel_radius_m, default_ticks_per_meter
        )
        self.left_encoder_sign = float(self.get_parameter('left_encoder_sign').value)
        self.right_encoder_sign = float(self.get_parameter('right_encoder_sign').value)
        self.left_command_sign = float(self.get_parameter('left_command_sign').value)
        self.right_command_sign = float(self.get_parameter('right_command_sign').value)
        self.max_linear_mps = abs(float(self.get_parameter('max_linear_mps').value))
        self.max_angular_rps = abs(float(self.get_parameter('max_angular_rps').value))
        self.max_target_tps = abs(float(self.get_parameter('max_target_tps').value))
        self.cmd_vel_timeout_s = float(self.get_parameter('cmd_vel_timeout_s').value)
        command_rate_hz = float(self.get_parameter('command_rate_hz').value)
        serial_read_rate_hz = float(self.get_parameter('serial_read_rate_hz').value)
        self.publish_tf = bool(self.get_parameter('publish_tf').value)
        self.motors_enabled = bool(self.get_parameter('motors_enabled').value)
        self.send_zero_when_disabled = bool(self.get_parameter('send_zero_when_disabled').value)

        # Params read from config/arduino_base.yaml (set via declare_parameter in __init__)
        self.odom_pose_x_cov = float(self.get_parameter('odom_pose_x_cov').value)
        self.odom_pose_y_cov = float(self.get_parameter('odom_pose_y_cov').value)
        self.odom_pose_yaw_cov = float(self.get_parameter('odom_pose_yaw_cov').value)
        self.odom_twist_vx_cov = float(self.get_parameter('odom_twist_vx_cov').value)
        self.odom_twist_vyaw_cov = float(self.get_parameter('odom_twist_vyaw_cov').value)

        self.battery_poll_period_s = float(self.get_parameter('battery_poll_period_s').value)
        self.battery_frame_id = self.get_parameter('battery_frame_id').value
        self.battery_location = self.get_parameter('battery_location').value
        self.battery_voltage_scale = float(self.get_parameter('battery_voltage_scale').value)
        self.battery_source_dc_min_v = float(self.get_parameter('battery_source_dc_min_v').value)
        self.battery_voltage_min_v = float(self.get_parameter('battery_voltage_min_v').value)
        self.battery_voltage_max_v = float(self.get_parameter('battery_voltage_max_v').value)
        self.battery_full_voltage = float(self.get_parameter('battery_full_voltage').value)
        self.battery_empty_voltage = float(self.get_parameter('battery_empty_voltage').value)

        if self.left_ticks_per_meter <= 0.0 or self.right_ticks_per_meter <= 0.0:
            raise ValueError('left_ticks_per_meter and right_ticks_per_meter must be positive')
        if command_rate_hz <= 0.0:
            raise ValueError('command_rate_hz must be positive')
        if serial_read_rate_hz <= 0.0:
            raise ValueError('serial_read_rate_hz must be positive')

        self.status_pub = self.create_publisher(String, '~/status_raw', 10)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.battery_pub = self.create_publisher(BatteryState, '~/battery_state', 10)
        self.cmd_sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.tf_broadcaster = TransformBroadcaster(self) if self.publish_tf else None

        self.serial_lock = threading.Lock()
        self.ser = self.open_serial()

        self.last_cmd_vel_time = 0.0
        self.last_safe_stop_time = 0.0
        self.target_linear_mps = 0.0
        self.target_angular_rps = 0.0

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.last_left_count: Optional[int] = None
        self.last_right_count: Optional[int] = None
        self.last_odom_time = self.get_clock().now()
        self.last_status: Optional[ArduinoStatus] = None
        self.last_battery_source: Optional[int] = None

        self.create_timer(1.0 / serial_read_rate_hz, self.read_serial_once)
        self.create_timer(1.0 / command_rate_hz, self.command_timer)
        if self.battery_poll_period_s > 0.0:
            self.create_timer(self.battery_poll_period_s, self.request_battery_status)

        self.get_logger().info(
            'Arduino base node started: '
            f'port={self.port} baud={self.baud} motors_enabled={self.motors_enabled} '
            f'track_width_m={self.track_width_m:.3f} '
            f'left_ticks_per_meter={self.left_ticks_per_meter:.1f} '
            f'right_ticks_per_meter={self.right_ticks_per_meter:.1f}'
        )
        if not self.motors_enabled:
            self.get_logger().warn(
                'motors_enabled is false: /cmd_vel will be ignored and safe stop commands will be sent. '
                'Set motors_enabled:=true only when safe to move.'
            )

    def open_serial(self):
        if serial is None:
            raise RuntimeError('python3-serial is not available; install python3-serial')
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.01, write_timeout=0.2)
        except serial.SerialException as exc:
            raise RuntimeError(f'failed to open serial port {self.port}: {exc}') from exc
        # Opening a Nano serial port usually resets it. Give firmware a moment.
        time.sleep(2.0)
        ser.reset_input_buffer()
        return ser

    def cmd_vel_callback(self, msg: Twist) -> None:
        self.target_linear_mps = max(-self.max_linear_mps, min(self.max_linear_mps, msg.linear.x))
        self.target_angular_rps = max(-self.max_angular_rps, min(self.max_angular_rps, msg.angular.z))
        self.last_cmd_vel_time = time.monotonic()

    def command_timer(self) -> None:
        now = time.monotonic()
        cmd_fresh = (now - self.last_cmd_vel_time) <= self.cmd_vel_timeout_s

        if not self.motors_enabled:
            # Keep the Arduino safely stopped without flooding the line with OK
            # responses, which can interleave with status output on a small MCU.
            if now - self.last_safe_stop_time >= 1.0:
                if self.send_zero_when_disabled:
                    self.send_velocity_command(0, 0)
                else:
                    self.send_stop_command()
                self.last_safe_stop_time = now
            return

        if not cmd_fresh:
            self.send_velocity_command(0, 0)
            return

        left_mps = self.target_linear_mps - self.target_angular_rps * self.track_width_m / 2.0
        right_mps = self.target_linear_mps + self.target_angular_rps * self.track_width_m / 2.0

        left_tps = self.left_command_sign * left_mps * self.left_ticks_per_meter
        right_tps = self.right_command_sign * right_mps * self.right_ticks_per_meter

        left_i = int(round(max(-self.max_target_tps, min(self.max_target_tps, left_tps))))
        right_i = int(round(max(-self.max_target_tps, min(self.max_target_tps, right_tps))))
        self.send_velocity_command(left_i, right_i)

    def send_velocity_command(self, left_tps: int, right_tps: int) -> None:
        self.write_line(f'V {left_tps} {right_tps}')

    def send_stop_command(self) -> None:
        self.write_line('S')

    def request_battery_status(self) -> None:
        self.write_line('B')

    def write_line(self, line: str) -> None:
        data = (line + '\n').encode('ascii')
        try:
            with self.serial_lock:
                self.ser.write(data)
        except serial.SerialException as exc:
            self.get_logger().error(f'serial write failed: {exc}')

    def read_serial_once(self) -> None:
        while True:
            try:
                with self.serial_lock:
                    raw = self.ser.readline()
            except serial.SerialException as exc:
                self.get_logger().error(f'serial read failed: {exc}')
                return
            if not raw:
                return
            line = raw.decode('ascii', errors='replace').strip()
            if line:
                self.handle_serial_line(line)

    def handle_serial_line(self, line: str) -> None:
        msg = String()
        msg.data = line
        self.status_pub.publish(msg)

        if line.startswith('BOOT'):
            self.get_logger().info(f'Arduino boot message: {line}')
            return
        if line.startswith('OK'):
            self.get_logger().debug(f'Arduino ack: {line}')
            return
        if line.startswith('ERR') or line.startswith('F'):
            self.get_logger().warn(f'Arduino reported: {line}')
            return
        if line.startswith('E '):
            status = self.parse_status(line)
            if status is None:
                return
            self.update_odometry(status)
            self.last_status = status
            return
        if line.startswith('B '):
            battery = self.parse_battery_status(line)
            if battery is None:
                return
            self.publish_battery_state(battery)
            return
        self.get_logger().debug(f'Ignoring serial line: {line}')

    def parse_status(self, line: str) -> Optional[ArduinoStatus]:
        parts = line.split()
        if len(parts) != 8:
            self.get_logger().warn(f'Bad E line field count: {line}')
            return None
        try:
            return ArduinoStatus(
                arduino_millis=int(parts[1]),
                left_count=int(parts[2]),
                right_count=int(parts[3]),
                left_tps=int(parts[4]),
                right_tps=int(parts[5]),
                left_pwm=int(parts[6]),
                right_pwm=int(parts[7]),
                raw=line,
            )
        except ValueError:
            self.get_logger().warn(f'Bad E line values: {line}')
            return None

    def parse_battery_status(self, line: str) -> Optional[ArduinoBatteryStatus]:
        parts = line.split()
        if len(parts) != 5:
            self.get_logger().warn(f'Bad B line field count: {line}')
            return None
        try:
            return ArduinoBatteryStatus(
                arduino_millis=int(parts[1]),
                source=int(parts[2]),
                adc_raw=int(parts[3]),
                supply_mv=int(parts[4]),
                raw=line,
            )
        except ValueError:
            self.get_logger().warn(f'Bad B line values: {line}')
            return None

    def publish_battery_state(self, status: ArduinoBatteryStatus) -> None:
        voltage = (status.supply_mv / 1000.0) * self.battery_voltage_scale
        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.battery_frame_id
        msg.voltage = float(voltage)
        msg.current = float('nan')
        msg.charge = float('nan')
        msg.capacity = float('nan')
        msg.design_capacity = float('nan')
        msg.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_UNKNOWN
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_UNKNOWN
        msg.present = False
        msg.location = self.battery_location
        msg.serial_number = ''

        is_dc = voltage >= self.battery_source_dc_min_v or status.source == 2
        is_battery = (
            self.battery_voltage_min_v <= voltage <= self.battery_source_dc_min_v
            or status.source == 1
        )
        if is_dc:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
            msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_UNKNOWN
            msg.present = True
        elif is_battery and self.battery_voltage_min_v <= voltage <= self.battery_voltage_max_v:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
            msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
            msg.present = True
        else:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
            msg.present = False

        # Estimate SoC from the sample 2S Li-ion OCV lookup (clamped to [0, 1]).
        # Note: this is an approximation; voltage sag under load and cell variation affect accuracy.
        msg.percentage = float(self.voltage_to_percentage(voltage))

        if self.last_battery_source != status.source:
            source_names = {0: 'unknown', 1: 'battery', 2: 'dc_external'}
            self.get_logger().info(
                f"Battery source: {source_names.get(status.source, 'invalid')} "
                f'voltage={voltage:.2f}V adc_raw={status.adc_raw}'
            )
            self.last_battery_source = status.source

        self.battery_pub.publish(msg)

    def update_odometry(self, status: ArduinoStatus) -> None:
        now = self.get_clock().now()
        if self.last_left_count is None or self.last_right_count is None:
            self.last_left_count = status.left_count
            self.last_right_count = status.right_count
            self.last_odom_time = now
            self.publish_odometry(now, 0.0, 0.0)
            return

        dt = (now - self.last_odom_time).nanoseconds / 1e9
        if dt <= 0.0:
            return

        left_delta_ticks = self.left_encoder_sign * (status.left_count - self.last_left_count)
        right_delta_ticks = self.right_encoder_sign * (status.right_count - self.last_right_count)
        self.last_left_count = status.left_count
        self.last_right_count = status.right_count
        self.last_odom_time = now

        left_distance = left_delta_ticks / self.left_ticks_per_meter
        right_distance = right_delta_ticks / self.right_ticks_per_meter
        distance = (left_distance + right_distance) / 2.0
        delta_yaw = (right_distance - left_distance) / self.track_width_m

        mid_yaw = self.yaw + delta_yaw / 2.0
        self.x += distance * math.cos(mid_yaw)
        self.y += distance * math.sin(mid_yaw)
        self.yaw = self.normalize_angle(self.yaw + delta_yaw)

        linear_velocity = distance / dt
        angular_velocity = delta_yaw / dt
        self.publish_odometry(now, linear_velocity, angular_velocity)

    def publish_odometry(self, stamp, linear_velocity: float, angular_velocity: float) -> None:
        qz = math.sin(self.yaw / 2.0)
        qw = math.cos(self.yaw / 2.0)

        odom = Odometry()
        odom.header.stamp = stamp.to_msg()
        odom.header.frame_id = self.odom_frame_id
        odom.child_frame_id = self.base_frame_id
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = linear_velocity
        odom.twist.twist.angular.z = angular_velocity

        # Odometry covariances from params so they can be tuned without code edits.
        odom.pose.covariance[0] = self.odom_pose_x_cov
        odom.pose.covariance[7] = self.odom_pose_y_cov
        odom.pose.covariance[35] = self.odom_pose_yaw_cov
        odom.twist.covariance[0] = self.odom_twist_vx_cov
        odom.twist.covariance[35] = self.odom_twist_vyaw_cov
        self.odom_pub.publish(odom)

        if self.tf_broadcaster is not None:
            transform = TransformStamped()
            transform.header.stamp = odom.header.stamp
            transform.header.frame_id = self.odom_frame_id
            transform.child_frame_id = self.base_frame_id
            transform.transform.translation.x = self.x
            transform.transform.translation.y = self.y
            transform.transform.translation.z = 0.0
            transform.transform.rotation.z = qz
            transform.transform.rotation.w = qw
            self.tf_broadcaster.sendTransform(transform)

    @staticmethod
    def resolve_ticks_per_meter(
        configured_tpm: float,
        ticks_per_rev: float,
        wheel_radius_m: float,
        default_tpm: float,
    ) -> float:
        if configured_tpm > 0.0:
            return configured_tpm
        if ticks_per_rev > 0.0:
            return ticks_per_rev / (2.0 * math.pi * wheel_radius_m)
        return default_tpm

    # Sample 2S Li-ion OCV (resting/open-circuit) curve: (pack_voltage_v, soc_fraction).
    # Approximate for typical LiCoO2/NMC cells; tune for your specific pack.
    BATTERY_OCV_TABLE = (
        (8.40, 1.00),
        (8.30, 0.95),
        (8.22, 0.90),
        (8.16, 0.85),
        (8.04, 0.80),
        (7.96, 0.75),
        (7.90, 0.70),
        (7.82, 0.65),
        (7.74, 0.60),
        (7.70, 0.55),
        (7.68, 0.50),
        (7.64, 0.45),
        (7.60, 0.40),
        (7.58, 0.35),
        (7.54, 0.30),
        (7.50, 0.25),
        (7.46, 0.20),
        (7.42, 0.15),
        (7.38, 0.10),
        (7.22, 0.05),
        (6.60, 0.00),
    )

    @classmethod
    def voltage_to_percentage(cls, voltage: float) -> float:
        """Estimate battery state-of-charge fraction from resting pack voltage."""
        table = cls.BATTERY_OCV_TABLE
        if voltage >= table[0][0]:
            return 1.0
        if voltage <= table[-1][0]:
            return 0.0
        for i in range(len(table) - 1):
            v_high, soc_high = table[i]
            v_low, soc_low = table[i + 1]
            if v_low <= voltage <= v_high:
                if v_high == v_low:
                    return soc_high
                fraction = (voltage - v_low) / (v_high - v_low)
                return soc_low + fraction * (soc_high - soc_low)
        return 0.0

    @staticmethod
    def normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def destroy_node(self) -> bool:
        try:
            self.send_stop_command()
            with self.serial_lock:
                self.ser.close()
        except Exception:
            pass
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ArduinoBaseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
