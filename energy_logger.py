import csv
import random
import time
import os
import minimalmodbus

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Config
DS_FILENAME = "energy_data.csv"
DS_HEADER = ["Timestamp", "Voltage (V)", "Current (A)", "Energy (kW)", "Reactive Power (kVA)"]

MODBUS_PORT = "/dev/ttyUSB0"
MODBUS_SLAVE_ID = 1
BAUDRATE = 9600
PARITY = minimalmodbus.serial.PARITY_NONE

INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = "energy-logger"
INFLUXDB_BUCKET = "energy-logger"

#instrument = minimalmodbus.Instrument(MODBUS_PORT, MODBUS_SLAVE_ID)
#instrument.serial.baudrate = BAUDRATE
#instrument.serial.parity = PARITY
#instrument.serial.bytesize = 8
#instrument.serial.stopbits = 1
#instrument.serial.timeout = 1

# Initialize plots directory if it doesn't exist
os.makedirs("plots", exist_ok=True)

# Initialize CSV file (overwrite every time the script runs)
with open(DS_FILENAME, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(DS_HEADER)

# Functions
def meter_reading_mock():
    """
    Simulate meter readings with mock values.
    """
    voltage = round(random.uniform(215, 240), 2)
    current = round(random.uniform(1.5, 15.0), 2)
    energy = round(random.uniform(0.2, 2.5), 3)
    reactive_power = round(random.uniform(0.1, 1.2), 3)

    return voltage, current, energy, reactive_power

#def meter_reading_modbus():
    """
    Poll electrical data from the power meter.
    Register value formats are FLOAT32 ABCD.
    """
    try:
        # Total measurements
        voltage_total = instrument.read_float(0x5000, functioncode=4, number_of_registers=2)
        current_total = instrument.read_float(0x500A, functioncode=4, number_of_registers=2)
        active_power_total = instrument.read_float(0x5012, functioncode=4, number_of_registers=2)
        reactive_power_total = instrument.read_float(0x501A, functioncode=4, number_of_registers=2)

        # Per-phase voltages
        voltage_L1 = instrument.read_float(0x5002, functioncode=4, number_of_registers=2)
        voltage_L2 = instrument.read_float(0x5004, functioncode=4, number_of_registers=2)
        voltage_L3 = instrument.read_float(0x5006, functioncode=4, number_of_registers=2)

        # Per-phase currents
        current_L1 = instrument.read_float(0x500C, functioncode=4, number_of_registers=2)
        current_L2 = instrument.read_float(0x500E, functioncode=4, number_of_registers=2)
        current_L3 = instrument.read_float(0x5010, functioncode=4, number_of_registers=2)
        
        return {
            "voltage_total": round(voltage_total, 2),
            "current_total": round(current_total, 2),
            "active_power_total": round(active_power_total, 3),
            "reactive_power_total": round(reactive_power_total, 3),
            "voltage_L1": round(voltage_L1, 2),
            "voltage_L2": round(voltage_L2, 2),
            "voltage_L3": round(voltage_L3, 2),
            "current_L1": round(current_L1, 2),
            "current_L2": round(current_L2, 2),
            "current_L3": round(current_L3, 2),
        }

    except Exception as e:
        print(f"[MODBUS ERROR] {e}")
        return None

def calculate_statistics():
    """
    Calculate statistics based on the logged data.
    """
    try:
        df = pd.read_csv(DS_FILENAME)
        stats = {}
        for column in df.columns[1:]:  # Skip timestamp column
            stats[column] = {
                'min': df[column].min(),
                'max': df[column].max(),
                'mean': df[column].mean(),
                'median': df[column].median(),
                'std': df[column].std()
            }

        # Print statistics
        print("\n===== Power Meter Statistics =====")
        for column, values in stats.items():
            print(f"\n{column}:")
            for stat_name, stat_value in values.items():
                print(f"  {stat_name}: {stat_value:.2f}")

        return df
    except Exception as e:
        print(f"Error calculating statistics: {e}")
        return None

def visualize_data(df):
    """
    Visualize the logged data with enhanced time series charts.
    """
    if df is None or len(df) < 2:
        print("Not enough data for visualization.")
        return
        
    try:
        # Convert timestamp to datetime for better plotting
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        
        # Create figure with shared x-axis for better time comparison
        fig, axs = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
        
        # Format the date/time display on x-axis
        from matplotlib.dates import DateFormatter
        date_format = DateFormatter('%H:%M:%S')
        
        # Plot voltage with markers and grid
        axs[0, 0].plot(df['Timestamp'], df['Voltage (V)'], 'b-', linewidth=1.5, marker='o', markersize=3)
        axs[0, 0].set_title('Voltage Over Time')
        axs[0, 0].set_ylabel('Voltage (V)')
        axs[0, 0].grid(True, linestyle='--', alpha=0.7)
        
        # Plot current
        axs[0, 1].plot(df['Timestamp'], df['Current (A)'], 'r-', linewidth=1.5, marker='o', markersize=3)
        axs[0, 1].set_title('Current Over Time')
        axs[0, 1].set_ylabel('Current (A)')
        axs[0, 1].grid(True, linestyle='--', alpha=0.7)
        
        # Plot energy
        axs[1, 0].plot(df['Timestamp'], df['Energy (kW)'], 'g-', linewidth=1.5, marker='o', markersize=3)
        axs[1, 0].set_title('Energy Over Time')
        axs[1, 0].set_ylabel('Energy (kW)')
        axs[1, 0].set_xlabel('Time')
        axs[1, 0].grid(True, linestyle='--', alpha=0.7)
        
        # Plot reactive power
        axs[1, 1].plot(df['Timestamp'], df['Reactive Power (kVA)'], 'm-', linewidth=1.5, marker='o', markersize=3)
        axs[1, 1].set_title('Reactive Power Over Time')
        axs[1, 1].set_ylabel('Reactive Power (kVA)')
        axs[1, 1].set_xlabel('Time')
        axs[1, 1].grid(True, linestyle='--', alpha=0.7)
        
        # Apply the formatter to all x-axes
        for ax in axs.flat:
            ax.xaxis.set_major_formatter(date_format)
        
        # Add rolling averages if enough data points
        if len(df) > 5:
            window = min(5, len(df) // 2)  # Use sensible window size
            axs[0, 0].plot(df['Timestamp'], df['Voltage (V)'].rolling(window=window).mean(), 
                'k--', alpha=0.7, linewidth=1, label='Trend (Rolling Avg)')
            axs[0, 1].plot(df['Timestamp'], df['Current (A)'].rolling(window=window).mean(), 
                'k--', alpha=0.7, linewidth=1, label='Trend (Rolling Avg)')
            axs[1, 0].plot(df['Timestamp'], df['Energy (kW)'].rolling(window=window).mean(), 
                'k--', alpha=0.7, linewidth=1, label='Trend (Rolling Avg)')
            axs[1, 1].plot(df['Timestamp'], df['Reactive Power (kVA)'].rolling(window=window).mean(), 
                'k--', alpha=0.7, linewidth=1, label='Trend (Rolling Avg)')
            
            # Add legends
            for ax in axs.flat:
                ax.legend()
        
        # Rotate x-axis labels
        plt.setp(axs[1, 0].get_xticklabels(), rotation=45, ha='right')
        plt.setp(axs[1, 1].get_xticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Add a combined normalized time series plot
        plt.figure(figsize=(14, 6))
        
        # Normalize each series to 0-1 range for comparison
        for column in df.columns[1:]:
            series = df[column]
            normalized = (series - series.min()) / (series.max() - series.min())
            plt.plot(df['Timestamp'], normalized, marker='.', markersize=4, label=column)
        
        plt.title('Normalized Values Comparison')
        plt.xlabel('Time')
        plt.ylabel('Normalized Value (0-1)')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save both figures with absolute paths
        os.makedirs("plots", exist_ok=True)
        fig.savefig("plots/energy_data_visualization.png")
        plt.savefig("plots/energy_data_normalized.png")

        print("\nVisualizations saved as:")
        print("- plots/energy_data_visualization.png")
        print("- plots/energy_data_normalized.png")
    except Exception as e:
        print(f"Error generating visualizations: {e}")

def log():
    """
    Log energy data to both CSV and InfluxDB simultaneously.
    """
    try:
        # Initialize InfluxDB client
        try:
            client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
            write_api = client.write_api(write_options=SYNCHRONOUS)
            influxdb_enabled = True
            print("InfluxDB connection established successfully.")
        except Exception as e:
            print(f"InfluxDB connection error: {e}")
            print("Continuing with CSV logging only.")
            influxdb_enabled = False
        
        print("Energy Data Logger started. Press Ctrl+C to stop logging.")
        
        while True:
            # Get meter readings
            voltage, current, energy, reactive_power = meter_reading_mock()
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # 1. Log to CSV file
            try:
                with open(DS_FILENAME, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([timestamp_str, voltage, current, energy, reactive_power])
                csv_status = "✓"
            except Exception as e:
                print(f"CSV write error: {e}")
                csv_status = "✗"
            
            # 2. Log to InfluxDB if enabled
            influx_status = "-"
            if influxdb_enabled:
                try:
                    # Create point with all measurements
                    point = (Point("power_measurements")
                            .tag("source", "energy_logger")
                            .tag("location", "main_panel")
                            .field("voltage", voltage)
                            .field("current", current)
                            .field("energy", energy)
                            .field("reactive_power", reactive_power)
                            .time(datetime.now(tz=timezone.utc), WritePrecision.S))

                    # Write to InfluxDB
                    write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                    influx_status = "✓"
                except Exception as e:
                    print(f"InfluxDB write error: {e}")
                    influx_status = "✗"

            # Print status with both logging systems
            print(f"[{timestamp_str}] CSV: {csv_status} InfluxDB: {influx_status} | V = {voltage}V | I = {current}A | E = {energy}kW | RP = {reactive_power}kVA")

            time.sleep(3)

    except KeyboardInterrupt:
        print("\nLogging stopped by user. Processing data...")
        
        # Close the client connection
        client.close()
        print("InfluxDB connection closed.")

        # Calculate statistics and visualize data
        df = calculate_statistics()
        visualize_data(df)

    except Exception as e:
        print(f"\nError during logging: {e}")
        if 'client' in locals() and influxdb_enabled:
            client.close()

if __name__ == "__main__":
    log()
    print("Energy data logging completed.")