import re
import logging
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal


class ProcessData(QObject):
    processed_data_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(
            'HORUS_CSS.data_processor')
        self.current_telemetry = None
        self.current_transmission = None
        self.past = None

        self.current_data = {
            'timestamp': 0.0,
            'velocity': 0.0,
            'altitude': 0.0,
            'pitch': 0.0,
            'roll': 0.0,
            'status': 0,
            'latitude': 52.2549,
            'longitude': 20.9004,
            'rssi': 0.0,
            'snr': 0.0,
            'bay_pressure': 0.0,
            'bay_temperature': 0.0,
            'progress': 0
        }

    def handle_telemetry(self, telemetry):
        self.current_telemetry = telemetry
        self.process_and_emit()

    def handle_transmission_info(self, transmission):
        self.current_transmission = transmission
        self.process_and_emit()

    def on_ethernet_data_received(self, data):
        self.current_data['timestamp'] = data['timestamp']
        for key in data['telemetry'].keys():
            if key in self.current_data:
                self.current_data[key] = data['telemetry'][key]
        for key in data['transmission'].keys():
            if key in self.current_data:
                self.current_data[key] = data['transmission'][key]

        self.logger.debug("Data packet processed")

        self.process_status()

        try:
            self.logger.debug(
                f"Połączone dane do wysłania: {self.current_data}")
            self.processed_data_ready.emit(self.current_data)
        except Exception as e:
            self.logger.exception(
                f"Błąd podczas łączenia danych telemetrycznych i transmisyjnych: {e}")

    def count_leading_ones(self, status, bit_length=6):
        mask = (1 << bit_length) - 1
        status &= mask
        found_zero = False
        count = 0
        for i in range(bit_length - 1, -1, -1):
            if status & (1 << i):
                if found_zero:
                    return -1
                count += 1
            else:
                found_zero = True
        return count

    def process_status(self):
        status = self.current_data['status']
        ones_count = self.count_leading_ones(status)
        if ones_count != -1:
            self.current_data['progress'] = ones_count*16
        else:
            self.current_data['progress'] = -1

    def process_and_emit(self):
        if self.current_telemetry and self.current_transmission:
            try:
                combined_data = {**self.current_telemetry,
                                 **self.current_transmission}
                self.logger.debug(
                    f"Połączone dane do wysłania: {combined_data}")
                self.processed_data_ready.emit(
                    combined_data)
            except Exception as e:
                self.logger.exception(
                    f"Błąd podczas łączenia danych telemetrycznych i transmisyjnych: {e}")