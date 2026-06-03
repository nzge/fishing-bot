import serial
import time
import csv
import re
from datetime import datetime

# =====================================================
# Serial Settings
# =====================================================

PORT = "COM3"
BAUD_RATE = 9600

# =====================================================
# Calibration Parameters
# =====================================================
# Placeholder values
# Replace after calibration:
#
# tension_N = K * raw_value + B
#
# Example:
# K = 0.00012
# B = -0.15
#
# determined using known weights
# =====================================================

K = 1.0
B = 0.0

# =====================================================
# Output File
# =====================================================

OUTPUT_CSV = "load_cell_readings.csv"

# =====================================================
# Arduino Output Format:
# raw: 1788 | avg5: 1793 | avg20: 1786
# =====================================================

pattern = re.compile(
    r"raw:\s*(-?\d+)\s*\|\s*avg5:\s*(-?\d+)\s*\|\s*avg20:\s*(-?\d+)"
)

# =====================================================
# Calibration Function
# =====================================================

def raw_to_tension(raw_value):
    """
    Convert HX711 reading to tension force.

    Placeholder linear model:
        tension_N = K * raw + B

    Replace K and B after calibration.
    """
    return K * raw_value + B


# =====================================================
# Main
# =====================================================

def main():

    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        time.sleep(2)

        print(f"Connected to Arduino on {PORT}")
        print("Reading sensor data...")
        print("Press Ctrl+C to stop.\n")

    except serial.SerialException as e:
        print("Could not open serial port.")
        print(e)
        return

    with open(OUTPUT_CSV, "w", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            "timestamp",
            "raw",
            "avg5",
            "avg20",
            "tension_N"
        ])

        try:

            while True:

                line = ser.readline().decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if not line:
                    continue

                match = pattern.search(line)

                if match:

                    timestamp = datetime.now().isoformat(
                        timespec="seconds"
                    )

                    raw = int(match.group(1))
                    avg5 = int(match.group(2))
                    avg20 = int(match.group(3))

                    # Use avg20 as filtered signal
                    tension = raw_to_tension(avg20)

                    print(
                        f"{timestamp} | "
                        f"raw={raw} "
                        f"avg5={avg5} "
                        f"avg20={avg20} "
                        f"tension={tension:.3f} N"
                    )

                    writer.writerow([
                        timestamp,
                        raw,
                        avg5,
                        avg20,
                        tension
                    ])

                    file.flush()

        except KeyboardInterrupt:

            print("\nStopped by user.")

        finally:

            ser.close()

            print("\nSerial port closed.")
            print(f"Data saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()