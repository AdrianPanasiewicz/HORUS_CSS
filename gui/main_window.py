import logging
import os

import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QMainWindow, QTextEdit,
                             QWidget, QVBoxLayout,
                             QHBoxLayout, QColorDialog,
                             QHBoxLayout, QLabel,
                             QPushButton, QGridLayout,
                             QGridLayout, QVBoxLayout,
                             QFrame, QTextBrowser, QDialogButtonBox,
                             QSizePolicy, QGroupBox, QMessageBox,
                             QInputDialog, QDialog)
from gui.time_series_plot import TimeSeriesPlot
from datetime import datetime, timedelta
from serial.tools import list_ports
from PyQt6.QtGui import QIcon, QPixmap, QColor
from core.serial_reader import SerialReader
from core.process_data import ProcessData
from core.csv_handler import CsvHandler

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.connect_gui_to_backend(config)
        self.declare_variables()
        self.initalizeUI()
        self.define_separators()
        self.setup_status_bar()

        # for plot in [self.time_pres_plot, self.lora_snr_plot, self.gps_snr_plot]:
        #     timestamps, values = self.generate_sample_data()
        #     plot.set_data(timestamps, values)
        # self.clear_plots()

        self.serial.start_reading()

    def connect_gui_to_backend(self, config):
        self.logger = logging.getLogger('HORUS_CSS.main_window')
        self.logger.info("Inicjalizacja głównego okna")

        self.csv_handler = CsvHandler()
        self.logger.info(
            f"CSV handler zainicjalizowany w sesji: {self.csv_handler.session_dir}")

        self.serial = SerialReader(config['port'], config['baudrate'])
        self.logger.info(f"SerialReader zainicjalizowany na porcie {config['port']} z baudrate {config['baudrate']}")
        self.processor = ProcessData()
        self.logger.info(
            f"Singleton ProcessData zainicjalizowany")

        self.default_timespan = 30

        if config['lora_config']:
            self.serial.LoraSet(config['lora_config'], config['is_config_selected'])
            self.logger.info(f"Konfiguracja LoRa ustawiona: {config['lora_config']}")

        self.serial.telemetry_received.connect(self.processor.handle_telemetry)
        self.serial.transmission_info_received.connect(self.processor.handle_transmission_info)
        self.processor.processed_data_ready.connect(self.handle_processed_data)

    def declare_variables(self):
        self.start_detection = False
        self.calib_detection = False
        self.apogee_detection = False
        self.recovery_detection = False
        self.landing_detection = False
        self.engine_detection = False

        self.current_data = {
            'velocity': 0.0,
            'altitude': 0.0,
            'pitch': 0.0,
            'roll': 0.0,
            'status': 0,
            'latitude': 52.2549,
            'longitude': 20.9004,
            'len': 0,
            'rssi': 0,
            'snr': 0
        }

    def initalizeUI(self):
        self.setWindowTitle("HORUS-CSS")
        self.setWindowIcon(QIcon(r'gui/resources/black_icon.png'))
        self.setStyleSheet(open(r'gui/resources/themes/dark_blue.qss').read())
        self.resize(1800, 900)
        self.declare_layout()
        self.declare_left_side_widgets()
        self.declare_right_side_widgets()
        self.declare_menu()

    def declare_layout(self):
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.main_layout = QGridLayout()
        self.central.setLayout(self.main_layout)

    def declare_menu(self):
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        self.view_menu = self.menu.addMenu("View")
        self.theme_menu = self.view_menu.addMenu("Themes")
        self.timespan_menu = self.view_menu.addMenu("Timespan")
        self.tools_menu = self.menu.addMenu("Tools")
        self.test_menu = self.menu.addMenu("Test")
        self.help_menu = self.menu.addMenu("Help")

        self.file_menu.addAction("Exit", self.close)
        self.file_menu.addAction("Open Session Directory", self.open_session_directory)
        self.file_menu.addAction("Show Session Path", self.show_session_directory_path)
        self.file_menu.addSeparator()
        self.file_menu.addAction("Save Terminal Log", self.save_terminal_log)
        self.file_menu.addAction("Export Plots as PNG", lambda: self.export_plots("png"))
        self.file_menu.addAction("Export Plots as SVG", lambda: self.export_plots("svg"))

        self.view_menu.addAction("Toggle Fullscreen", self.toggle_fullscreen)
        self.view_menu.addAction("Toggle Status Bar", self.toggle_status_bar)
        self.view_menu.addAction("Toggle Heartbeat", self.toggle_heartbeat)
        self.view_menu.addSeparator()
        self.view_menu.addAction("Toggle Crosshair", self.toggle_crosshairs)
        self.view_menu.addAction("Toggle Data Point Markers", self.toggle_data_markers)
        self.view_menu.addAction("Change Line Colors", self.change_line_colors)
        self.view_menu.addAction("Toggle Grid", self.toggle_plot_grid)
        # self.view_menu.addAction("Toggle Legends", self.toggle_plot_legends)
        self.view_menu.addSeparator()
        self.view_menu.addAction("Clear Terminal", self.clear_terminal)
        self.view_menu.addAction("Clear Plots", self.clear_plots)
        self.view_menu.addAction("Clear All", self.clear_all)

        self.help_menu.addAction("About application", self.show_about_app_dialog)
        self.help_menu.addAction("About KNS LiK", self.show_about_kns_dialog)

        self.test_menu.addAction("Start Terminal Simulation", self.start_terminal_simulation)
        self.test_menu.addAction("Stop Terminal Simulation", self.stop_terminal_simulation)
        self.test_menu.addSeparator()
        self.test_menu.addAction("Start Plot Simulation", self.start_plot_simulation)
        self.test_menu.addAction("Stop Plot Simulation", self.stop_plot_simulation)

        self.themes = {
            "Dark Blue": "dark_blue.qss",
            "Gray": "gray.qss",
            "Marble": "marble.qss",
            "Slick Dark": "slick_dark.qss",
            "Uniform Dark": "unform_dark.qss"
        }

        self.theme_actions = {}
        for theme_name, theme_file in self.themes.items():
            action = self.theme_menu.addAction(theme_name)
            action.triggered.connect(lambda _, t=theme_file: self.apply_theme(t))
            self.theme_actions[theme_name] = action

        self.timespan_menu.addAction("30 seconds", lambda: self.change_plot_timespans(30))
        self.timespan_menu.addAction("60 seconds", lambda: self.change_plot_timespans(60))
        self.timespan_menu.addAction("90 seconds", lambda: self.change_plot_timespans(90))
        self.timespan_menu.addAction("120 seconds", lambda: self.change_plot_timespans(120))

        serial_menu = self.tools_menu.addMenu("Serial Configuration")
        serial_menu.addAction("Scan Ports", self.scan_serial_ports)
        serial_menu.addAction("Change Baud Rate", self.change_baud_rate)
        serial_menu.addAction("Reconnect Serial", self.reconnect_serial)
        self.tools_menu.addAction("Configure Filters", self.configure_filters)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction("Calculate Statistics", self.calculate_statistics)


    def declare_left_side_widgets(self):
        self.left_layout = QVBoxLayout()
        self.main_layout.addLayout(self.left_layout, 0, 0)

        global_status_label = QLabel("Status: not connected")
        global_status_label.setStyleSheet("font-size: 30px;")
        self.left_layout.addWidget(global_status_label)

        rocket_trajectory_label = QLabel()
        rocket_trajectory_label.setScaledContents(True)
        self.left_layout.addWidget(rocket_trajectory_label)

        rocket_trajectory_background = QPixmap(r"gui/resources/Professional_graphic.png")
        rocket_trajectory_label.setPixmap(rocket_trajectory_background)
        rocket_trajectory_label.setMinimumSize(200, 160)
        rocket_trajectory_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.terminal_output = QTextBrowser()
        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: System ready...")
        self.terminal_output.setStyleSheet(
            "font-size: 14px;")
        self.left_layout.addWidget(self.terminal_output)


    def declare_right_side_widgets(self):

        #------------------------
        self.right_layout = QVBoxLayout()
        self.main_layout.addLayout(self.right_layout, 0, 2)

        self.rec_bay_layout = QHBoxLayout()
        self.rec_bay_group = QGroupBox("Recovery bay status")

        self.time_pres_plot = TimeSeriesPlot(self.default_timespan)
        self.time_pres_plot.set_x_label("Time [s]")
        self.time_pres_plot.set_y_label("Temp [°C]")

        # base_time = datetime.now()
        # timestamps = [base_time + timedelta(minutes=i) for i
        #               in range(60)]
        # values = np.random.normal(50, 10, 60).tolist()

        # self.time_pres_plot.set_data(timestamps, values)

        self.rec_bay_hbox = QHBoxLayout()
        self.rec_bay_hbox.addWidget(self.time_pres_plot,4)
        self.rec_bay_vbox = QVBoxLayout()
        self.rec_bay_hbox.addLayout(self.rec_bay_vbox,1)
        self.rec_bay_layout.addLayout(self.rec_bay_hbox)

        self.rec_bay_temp_label = QLabel(f"Temperature: 0°C")
        self.rec_bay_press_label = QLabel(f"Pressure: 0 hPa")
        self.rec_bay_vbox.addWidget(self.rec_bay_temp_label)
        self.rec_bay_vbox.addWidget(self.rec_bay_press_label)

        self.rec_bay_group.setLayout(self.rec_bay_layout)
        self.right_layout.addWidget(self.rec_bay_group)
        #-------------------------

        self.lora_layout = QHBoxLayout()
        self.lora_group = QGroupBox("LoRa signal status")

        self.lora_snr_plot = TimeSeriesPlot(self.default_timespan)
        self.lora_snr_plot.set_x_label("Time [s]")
        self.lora_snr_plot.set_y_label("SNR [dB]")

        # base_time = datetime.now()
        # timestamps = [base_time + timedelta(minutes=i) for i
        #               in range(120)]
        # values = np.random.normal(2, 0.01, 120).tolist()
        # self.lora_snr_plot.set_data(timestamps, values)

        self.lora_hbox = QHBoxLayout()
        self.lora_hbox.addWidget(self.lora_snr_plot,4)

        self.lora_vbox = QVBoxLayout()
        self.lora_snr_label = QLabel("SNR: 0 dB")
        self.lora_freq_label = QLabel("RSSI: 0 dBm")
        self.lora_vbox.addWidget(self.lora_snr_label)
        self.lora_vbox.addWidget(self.lora_freq_label)

        self.lora_hbox.addLayout(self.lora_vbox,1)
        self.lora_layout.addLayout(self.lora_hbox)

        self.lora_group.setLayout(self.lora_layout)
        self.right_layout.addWidget(self.lora_group)
        # ------------------------

        self.gps_layout = QHBoxLayout()
        self.gps_group = QGroupBox("GPS signal status")

        self.gps_snr_plot = TimeSeriesPlot(self.default_timespan)
        self.gps_snr_plot.set_x_label("Time [s]")
        self.gps_snr_plot.set_y_label("SNR [dB]")

        self.gps_hbox = QHBoxLayout()
        self.gps_hbox.addWidget(self.gps_snr_plot,4)

        self.gps_vbox = QVBoxLayout()
        self.gps_snr_label = QLabel("SNR: 0 dB")
        self.gps_sat_label = QLabel("RSSI: 0 dBm")
        self.gps_vbox.addWidget(self.gps_snr_label)
        self.gps_vbox.addWidget(self.gps_sat_label)

        self.gps_hbox.addLayout(self.gps_vbox,1)
        self.gps_layout.addLayout(self.gps_hbox)

        self.gps_group.setLayout(self.gps_layout)
        self.right_layout.addWidget(self.gps_group)

    def generate_sample_data(self):
        base_time = datetime.now()
        timestamps = [base_time + timedelta(minutes=i) for i
                      in range(200)]
        values = np.random.normal(10, 5, 200).tolist()
        return timestamps, values


    def define_separators(self):

        vert_separator = QFrame()
        vert_separator.setFrameShape(QFrame.Shape.VLine)
        vert_separator.setFrameShadow(
            QFrame.Shadow.Sunken)
        vert_separator.setStyleSheet(
            "color: white;")
        self.main_layout.addWidget(vert_separator, 0, 1, 3, 1)

    def apply_theme(self, theme_file):
        try:
            theme_path = os.path.join("gui", "resources", "themes", theme_file)
            with open(theme_path, "r") as file:
                self.setStyleSheet(file.read())
            self.logger.info(f"Theme changed to: {theme_file}")
        except Exception as e:
            self.logger.error(f"Error loading theme {theme_file}: {str(e)}")

    def show_about_app_dialog(self):
        about_text = """
        <div style="text-align: justify;">
            <h2>HOURS Communication & System Status Station</h2>
            <p><b>Version:</b> 0.1.0</p>
            <p><b>Description:</b> The ground station is responsible for controlling the AGS and displaying data regarding 
            the quality of the wireless connection and the status of the rocket's systems. It is a subcomponent of a
            HOURS project, which is also as a part of a larger LOTUS ONE project Scientific Association of Aviation and
            Astronautics Students of MUT.</p>
            <p><b>Authors:</b> Adrian Panasiewicz, Filip Sudak</p>
            <p><b>Copyright:</b> © 2025 KNS LiK </p>
            <p>Built with PyQt6</p>
        </div>
        """

        QMessageBox.about(self, "About HORUS-CSS", about_text)

    def show_about_kns_dialog(self):
        about_text = """
        <div style="text-align: justify;">
            <h2>Scientific Association of Aviation and Astronautics Students of MUT</h2>
            <p><b>Description:</b> The Scientific Circle of Aviation and Astronautics (KNS) brings together the best 
            civilian and military students studying Aviation and Astronautics, as well as students from other fields 
            present at the Faculty of Mechatronics, Armament, and Aviation, who deepen their knowledge in collaboration 
            with university staff.</p>
            <p>The main objectives of the Scientific Circle of Aviation and Astronautics Students are:</p>
            <ul>
                <li>Developing engineering skills in designing and building UAVs and other flying structures;</li>
                <li>Fostering students' interests in building and developing UAVs, model rockets, and topics related to 
                aviation technologies;</li>
                <li>Enhancing skills in using market-available software related to engineering work;</li>
                <li>Developing soft skills in project management, teamwork, and team communication.</li>
            </ul>
            The Circle plans to develop the existing skills of its members, improve their soft and technical 
            competencies, and, above all, undertake projects characterized by a higher level of complexity and 
            advanced technical and technological sophistication.
        </div>
        """
        QMessageBox.about(self, "About KNS LiK", about_text)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def open_session_directory(self):
        import os
        import platform
        import subprocess
        from PyQt6.QtWidgets import QMessageBox

        session_path = self.csv_handler.session_dir

        if not os.path.exists(session_path):
            QMessageBox.warning(
                self,
                "Directory Not Found",
                f"Session directory not found:\n{session_path}"
            )
            return

        try:
            if platform.system() == "Windows":
                os.startfile(session_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", session_path])
            else:
                subprocess.Popen(["xdg-open", session_path])
        except Exception as e:
            self.logger.error(f"Error opening session directory: {str(e)}")
            QMessageBox.critical(
                self,
                "Error Opening Directory",
                f"Could not open session directory:\n{str(e)}"
            )

    def show_session_directory_path(self):
        session_path = self.csv_handler.session_dir
        QMessageBox.information(
            self,
            "Session Directory Path",
            f"Current session files are stored at:\n{session_path}"
        )

    def toggle_heartbeat(self):
        if hasattr(self, 'heartbeat_active') and self.heartbeat_active:
            self.heartbeat_timer.stop()
            self.heartbeat_placeholder.setStyleSheet("color: transparent; font-size: 14px;")
            self.heartbeat_active = False
        else:
            self.heartbeat_timer.start(500)
            self.heartbeat_active = True
            self.blink_heartbeat()

    def setup_heartbeat(self):
        if not hasattr(self, 'heartbeat_timer'):
            self.heartbeat_timer = QTimer()
            self.heartbeat_timer.timeout.connect(self.blink_heartbeat)
            self.heartbeat_state = True

        self.heartbeat_active = True
        self.heartbeat_timer.start(500)

    def setup_status_bar(self):
        self.status_bar_visible = True
        self.status_logo = QLabel()
        self.status_logo.setFixedSize(24, 24)
        self.status_logo.setScaledContents(True)
        logo_pixmap = QPixmap(r"gui/resources/black_icon_without_background.png").scaled(30, 30)
        self.status_logo.setPixmap(logo_pixmap)
        self.statusBar().addWidget(self.status_logo)

        current_time = datetime.now().strftime("%H:%M:%S")
        self.status_packet_label = QLabel(f"Last received packet: {current_time} s")
        self.status_packet_label.setStyleSheet("font-size: 14px;")
        self.statusBar().addWidget(self.status_packet_label)

        self.statusBar().addWidget(QLabel(), 1)

        self.status_title_label = QLabel("HORUS Communication & System Status Station  \t\t\t")
        self.status_title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.statusBar().addWidget(self.status_title_label)

        self.statusBar().addWidget(QLabel(), 1)

        self.heartbeat_placeholder = QLabel("●")
        self.heartbeat_placeholder.setStyleSheet("color: transparent; font-size: 14px;")
        self.statusBar().addPermanentWidget(self.heartbeat_placeholder)

        self.setup_heartbeat()

    def toggle_status_bar(self):
        if self.status_bar_visible:
            self.statusBar().hide()
            self.status_bar_visible = False
        else:
            self.statusBar().show()
            self.status_bar_visible = True

    def update_status_packet_time(self):
        if hasattr(self, 'status_packet_label'):
            current_time = datetime.now().strftime("%H:%M:%S")
            self.status_packet_label.setText(f"Last received packet: {current_time}s")

    def blink_heartbeat(self):
        if hasattr(self, 'heartbeat_active') and self.heartbeat_active:
            self.heartbeat_state = not self.heartbeat_state
            color = "red" if self.heartbeat_state else "transparent"
            self.heartbeat_placeholder.setStyleSheet(f"color: {color}; font-size: 14px;")

    def start_terminal_simulation(self):
        if not hasattr(self, 'simulation_timer'):
            self.simulation_timer = QTimer()
            self.simulation_timer.timeout.connect(self.generate_terminal_output)

        self.simulation_interval = max(500, int(np.random.normal(1000, 200)))
        self.simulation_timer.start(self.simulation_interval)
        self.logger.info("Started terminal simulation")

        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: <span style='color: yellow;'>Started terminal simulation (interval: "
            f"{self.simulation_interval}ms)</span>")

    def stop_terminal_simulation(self):
        if hasattr(self, 'simulation_timer') and self.simulation_timer.isActive():
            self.simulation_timer.stop()
            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: yellow;'>Stopped terminal simulation</span>")
            self.logger.info("Stopped terminal simulation")

    def generate_terminal_output(self):
        current_time = datetime.now().strftime("%H:%M:%S")
        messages = [
            f"<span style='color: yellow;'>SIM</span>: Telemetry packet received - velocity: "
            f"{np.random.normal(50, 10):.2f} m/s",
            f"<span style='color: yellow;'>SIM</span>: GPS coordinates - lat: {np.random.normal(52.25, 0.01):.6f}, lon: {np.random.normal(20.90, 0.01):.6f}",
            f"<span style='color: yellow;'>SIM</span>: System status OK - CPU: {np.random.randint(10, 30)}%, "
            f"MEM: {np.random.randint(200, 400)}MB",
            f"<span style='color: yellow;'>SIM</span>: LoRa signal - RSSI: {np.random.normal(-90, 5):.1f} dBm, SNR: {np.random.normal(5, 2):.1f} dB",
            f"<span style='color: yellow;'>SIM</span>: Altitude: {np.random.normal(1500, 200):.1f} m, Pressure: "
            f"{np.random.normal(800, 50):.1f} hPa",
            f"<span style='color: yellow;'>SIM</span>: Rocket orientation - pitch: {np.random.normal(0, 5):.1f}°, roll: {np.random.normal(0, 5):.1f}°"
        ]

        message = np.random.choice(messages)
        self.terminal_output.append(f">{current_time}: {message}")

        self.simulation_interval = max(500, int(np.random.normal(1000, 200)))
        self.simulation_timer.setInterval(self.simulation_interval)
    def clear_terminal(self):
        self.terminal_output.clear()
        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: Terminal cleared")
        self.logger.info("Terminal cleared")

    def start_plot_simulation(self):
        if not hasattr(self, 'plot_sim_timer'):
            self.plot_sim_timer = QTimer()
            self.plot_sim_timer.timeout.connect(self.generate_plot_data)

        self.plot_sim_interval = max(500, int(np.random.normal(1000, 200)))
        self.plot_sim_timer.start(self.plot_sim_interval)
        self.logger.info("Started plot simulation")

        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: <span style='color: yellow;'>Started plot simulation (interval: {self.plot_sim_interval}ms)</span>")

    def stop_plot_simulation(self):
        if hasattr(self, 'plot_sim_timer') and self.plot_sim_timer.isActive():
            self.plot_sim_timer.stop()
            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: yellow;'>Stopped plot simulation</span>")
            self.logger.info("Stopped plot simulation")

    def generate_plot_data(self):
        current_time = datetime.now()

        temp_value = np.random.normal(50, 5)
        self.time_pres_plot.add_point(current_time, temp_value)
        self.rec_bay_temp_label.setText(f"Temperature: {temp_value:.1f}°C")

        if np.random.random() < 0.2:
            pressure_value = np.random.normal(800, 30)
            self.rec_bay_press_label.setText(f"Pressure: {pressure_value:.1f} hPa")

        snr_value = np.random.normal(5, 1.5)
        self.lora_snr_plot.add_point(current_time, snr_value)
        self.lora_snr_label.setText(f"SNR: {snr_value:.1f} dB")

        if np.random.random() < 0.3:  # 30% chance to update RSSI
            rssi_value = np.random.normal(-90, 3)
            self.lora_freq_label.setText(f"RSSI: {rssi_value:.1f} dBm")

        gps_snr_value = np.random.normal(25, 3)
        self.gps_snr_plot.add_point(current_time, gps_snr_value)
        self.gps_snr_label.setText(f"SNR: {gps_snr_value:.1f} dB")

        if np.random.random() < 0.4:
            sat_value = np.random.normal(-100, 5)
            self.gps_sat_label.setText(f"RSSI: {sat_value:.1f} dBm")

    def clear_plots(self):
        self.time_pres_plot.clear_data()
        self.lora_snr_plot.clear_data()
        self.gps_snr_plot.clear_data()

        self.rec_bay_temp_label.setText("Temperature: 0°C")
        self.rec_bay_press_label.setText("Pressure: 0 hPa")
        self.lora_snr_label.setText("SNR: 0 dB")
        self.lora_freq_label.setText("RSSI: 0 dBm")
        self.gps_snr_label.setText("SNR: 0 dB")
        self.gps_sat_label.setText("RSSI: 0 dBm")

        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: All plots cleared")
        self.logger.info("Plots cleared")

    def clear_all(self):
        self.clear_plots()
        self.clear_terminal()

    def change_plot_timespans(self, timespan):
        self.time_pres_plot.update_timespan(timespan)
        self.lora_snr_plot.update_timespan(timespan)
        self.gps_snr_plot.update_timespan(timespan)

    def toggle_crosshairs(self):
        current_state = self.time_pres_plot.crosshair_visible

        for plot in [self.time_pres_plot, self.lora_snr_plot, self.gps_snr_plot]:
            plot.toggle_crosshair(not current_state)

    def save_terminal_log(self):
        path = os.path.join(self.csv_handler.session_dir, "terminal_log.txt")
        try:
            with open(path, 'w') as f:
                f.write(self.terminal_output.toPlainText())
            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(f">{current_time}: Log saved to {path}")
            self.logger.info(f"Terminal log saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save log: {str(e)}")

    def export_plots(self, format):
        try:
            session_dir = self.csv_handler.session_dir
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            plots = {
                "pressure": self.time_pres_plot,
                "lora": self.lora_snr_plot,
                "gps": self.gps_snr_plot
            }

            for name, plot in plots.items():
                filename = os.path.join(session_dir, f"{name}_plot_{timestamp}.{format}")
                if format == "png":
                    plot.export_to_png(filename)
                elif format == "svg":
                    plot.export_to_svg(filename)

            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: lightgreen;'>Exported plots as {format.upper()} files</span>")
            self.logger.info(f"Exported plots as {format.upper()} files")
        except Exception as e:
            self.logger.error(f"Error exporting plots: {str(e)}")
            QMessageBox.critical(self, "Export Error", f"Failed to export plots: {str(e)}")

    def toggle_data_markers(self):
        state = not self.time_pres_plot.data_markers_visible

        for plot in [self.time_pres_plot, self.lora_snr_plot, self.gps_snr_plot]:
            plot.toggle_data_markers(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Data markers turned {status}</span>")
        self.logger.info(f"Data markers toggled to {status}")

    def change_line_colors(self):
        current_color = self.time_pres_plot.line_color

        current_qcolor = QColor(current_color)
        color = QColorDialog.getColor(current_qcolor, self, "Select Line Color")
        if color.isValid():
            for plot in [self.time_pres_plot, self.lora_snr_plot, self.gps_snr_plot]:
                plot.set_line_color(color)

            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: {color.name()};'>Plot line color changed</span>")
            self.logger.info(f"Plot line color changed to {color.name()}")

    # def change_line_styles(self):
    #     styles = ["Solid", "Dashed", "Dotted", "Dash-Dot"]
    #     current_style = self.time_pres_plot.line_style
    #
    #     choice, ok = QInputDialog.getItem(
    #         self, "Select Line Style", "Choose a line style:",
    #         styles, styles.index(current_style), False
    #     )
    #
    #     if ok and choice:
    #         for plot in [self.time_pres_plot, self.lora_snr_plot, self.gps_snr_plot]:
    #             plot.set_line_style(choice)
    #
    #         current_time = datetime.now().strftime("%H:%M:%S")
    #         self.terminal_output.append(
    #             f">{current_time}: <span style='color: lightblue;'>Line style changed to {choice}</span>")
    #         self.logger.info(f"Line style changed to {choice}")

    def toggle_plot_grid(self):
        state = not self.time_pres_plot.grid_visible

        for plot in [self.time_pres_plot, self.lora_snr_plot, self.gps_snr_plot]:
            plot.toggle_grid(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Plot grid turned {status}</span>")
        self.logger.info(f"Plot grid toggled to {status}")

    def toggle_plot_legends(self):
        state = not self.time_pres_plot.legend_visible

        for plot in [self.time_pres_plot, self.lora_snr_plot, self.gps_snr_plot]:
            plot.toggle_legend(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Plot legends turned {status}</span>")
        self.logger.info(f"Plot legends toggled to {status}")

    def scan_serial_ports(self):
        try:
            ports = [port.device for port in list_ports.comports()]
            current_time = datetime.now().strftime("%H:%M:%S")

            if not ports:
                self.terminal_output.append(
                    f">{current_time}: <span style='color: orange;'>No serial ports found</span>")
                return

            message = "<span style='color: lightgreen;'>Available ports:</span><br>"
            message += "<br>".join([f"&nbsp;&nbsp;• {port}" for port in ports])

            self.terminal_output.append(f">{current_time}: {message}")
            self.logger.info(f"Scanned serial ports: {ports}")
        except Exception as e:
            self.logger.error(f"Error scanning serial ports: {str(e)}")
            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: red;'>Error scanning ports: {str(e)}</span>")

    def change_baud_rate(self):

        current_baud = self.serial.baudrate
        baud_rates = ["9600", "19200", "38400", "57600", "115200"]

        choice, ok = QInputDialog.getItem(
            self, "Select Baud Rate", "Choose a baud rate:",
            baud_rates, baud_rates.index(str(current_baud)), False
        )

        if ok and choice:
            try:
                new_baud = int(choice)
                self.serial.set_baudrate(new_baud)

                current_time = datetime.now().strftime("%H:%M:%S")
                self.terminal_output.append(
                    f">{current_time}: <span style='color: lightgreen;'>Baud rate changed to {new_baud}</span>")
                self.logger.info(f"Baud rate changed to {new_baud}")
            except Exception as e:
                self.logger.error(f"Error changing baud rate: {str(e)}")
                current_time = datetime.now().strftime("%H:%M:%S")
                self.terminal_output.append(
                    f">{current_time}: <span style='color: red;'>Error changing baud rate: {str(e)}</span>")

    def reconnect_serial(self):
        try:
            self.serial.reconnect()
            current_time = datetime.now().strftime("%H:%M:%S")

            if self.serial.is_connected():
                self.terminal_output.append(
                    f">{current_time}: <span style='color: lightgreen;'>Serial reconnected successfully</span>")
                self.logger.info("Serial reconnected successfully")
            else:
                self.terminal_output.append(
                    f">{current_time}: <span style='color: orange;'>Serial reconnection failed</span>")
                self.logger.warning("Serial reconnection failed")
        except Exception as e:
            self.logger.error(f"Error reconnecting serial: {str(e)}")
            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: red;'>Error reconnecting serial: {str(e)}</span>")

    def configure_filters(self):
        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: <span style='color: yellow;'>Filter configuration opened</span>")

        # Placeholder for actual implementation
        QMessageBox.information(
            self,
            "Configure Filters",
            "This feature is under development. It will allow you to configure "
            "data filtering algorithms for noise reduction."
        )

    def calculate_statistics(self):
        """Calculate and display statistics for plot data"""
        try:
            stats = []

            # Calculate for each plot
            plots = {
                "Pressure/Temperature": self.time_pres_plot,
                "LoRa SNR": self.lora_snr_plot,
                "GPS SNR": self.gps_snr_plot
            }

            for name, plot in plots.items():
                if plot.values.any():
                    values = np.array(plot.values)
                    stats.append(f"<b>{name}:</b>")
                    stats.append(f"  Min: {np.min(values):.2f}")
                    stats.append(f"  Max: {np.max(values):.2f}")
                    stats.append(f"  Mean: {np.mean(values):.2f}")
                    stats.append(f"  Std Dev: {np.std(values):.2f}")
                    stats.append("")

            if not stats:
                raise ValueError("No data available for statistics")

            stats_html = "<br>".join(stats)

            # Show in dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Data Statistics")
            dialog.resize(200, 400)
            layout = QVBoxLayout()

            text_browser = QTextBrowser()
            text_browser.setHtml(stats_html)
            layout.addWidget(text_browser)

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)

            dialog.setLayout(layout)
            dialog.exec()

            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: lightgreen;'>Calculated data statistics</span>")
            self.logger.info("Calculated data statistics")

        except Exception as e:
            self.logger.error(f"Error calculating statistics: {str(e)}")
            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: red;'>Error calculating statistics: {str(e)}</span>")

    def handle_processed_data(self, data):
        pass
        # self.logger.debug(
        #     f"Odebrano dane przetworzone: {data}")
        # self.current_data = data
        # try:
        #     self.update_data()
        #     self.csv_handler.write_row(data)
        #
        #     if data['latitude'] != 0.0 and data[
        #         'longitude'] != 0.0:
        #         self.current_lat = data['latitude']
        #         self.current_lng = data['longitude']
        #         self.initialize_map()
        #         self.update_map_view()
        #
        # except Exception as e:
        #     self.logger.exception(
        #         f"Błąd w update_data(): {e}")

    def update_data(self):
        pass
        # """Aktualizacja danych na interfejsie"""
        # # Aktualizacja wykresów
        # self.alt_plot.update_plot(
        #     self.current_data['altitude'])
        # self.velocity_plot.update_plot(
        #     self.current_data['velocity'])
        # self.pitch_plot.update_plot(
        #     self.current_data['pitch'])
        # self.roll_plot.update_plot(
        #     self.current_data['roll'])
        #
        # self.label_info.setText(
        #     f"Pitch: {self.current_data['pitch']:.2f}°, Roll: {self.current_data['roll']:.2f}°\n"
        #     f"V: {self.current_data['velocity']:.2f} m/s, H: {self.current_data['altitude']:.2f} m"
        # )
        # self.label_pos.setText(
        #     f"LON:\t{self.current_data['longitude']:.6f}° N \nLAT:\t{self.current_data['latitude']:.6f}° E"
        # )
        #
        # self.now_str = datetime.now().strftime("%H:%M:%S")
        # msg = (
        #     f"{self.current_data['velocity']};{self.current_data['altitude']};"
        #     f"{self.current_data['pitch']};{self.current_data['roll']};"
        #     f"{self.current_data['status']};{self.current_data['latitude']};"
        #     f"{self.current_data['longitude']}"
        # )
        # self.console.append(
        #     f"{self.now_str} | LEN: {self.current_data['len']} bajtów | "
        #     f"RSSI: {self.current_data['rssi']} dBm | "
        #     f"SNR: {self.current_data['snr']} dB | msg: {msg}"
        # )
        # self.logger.debug(f"Odebrano dane: {msg}")
        #
        # status = self.current_data['status']
        #
        # # Calibration
        # if status & (1 << 0):
        #     if not self.calib_detection:
        #         self.calib_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: green; padding: 5px;}"
        #         )
        #         self.calib_button.setText("Calibration: On")
        #         self.console.append(f"{self.now_str} | CALIB ON")
        #         self.logger.info("Detekcja kalibracji")
        #         self.calib_detection = True
        # else:
        #     if self.calib_detection:
        #         self.calib_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: red; padding: 5px;}"
        #         )
        #         self.calib_button.setText("Calibration: Off")
        #         self.calib_detection = False
        #
        # # Start
        # if status & (1 << 1):
        #     if not self.start_detection:
        #         self.start_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: green; padding: 5px;}"
        #         )
        #         self.logger.info("Detekcja startu")
        #         self.console.append(f"{self.now_str} | START DETECTION")
        #         print("Detekcja startu")
        #         self.start_detection = True
        # else:
        #     if self.start_detection:
        #         self.start_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: red; padding: 5px;}"
        #         )
        #         self.start_detection = False
        #
        # # Engine
        # if status & (1 << 2):
        #     if not self.engine_detection:
        #         self.engine_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: green; padding: 5px;}"
        #         )
        #         self.engine_buttonn.setText("Engine: On")
        #         self.console.append(f"{self.now_str} | ENGINE ON")
        #         self.logger.info("Detekcja uruchomienia silników")
        #         self.engine_detection = True
        # else:
        #     if self.engine_detection:
        #         self.engine_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: red; padding: 5px;}"
        #         )
        #         self.engine_buttonn.setText("Engine: Off")
        #         self.console.append(f"{self.now_str} | ENGINE OF")
        #         self.engine_detection = False
        #
        # # Apogee
        # if status & (1 << 3):
        #     if not self.apogee_detection:
        #         self.apogee_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: green; padding: 5px;}"
        #         )
        #         self.console.append(f"{self.now_str} | APOGEE DETECTION")
        #         self.logger.info("Detekcja apogeum")
        #         self.apogee_detection = True
        # else:
        #     if self.apogee_detection:
        #         self.apogee_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: red; padding: 5px;}"
        #         )
        #         self.apogee_detection = False
        #
        # # Recovery
        # if status & (1 << 4):
        #     if not self.recovery_detection:
        #         self.recovery_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: green; padding: 5px;}"
        #         )
        #         self.recovery_button.setText("Recovery: On")
        #         self.console.append(f"{self.now_str} | RECOVERY DETECTION")
        #         self.logger.info("Detekcja odzysku")
        #         print("Detekcja odzysku")
        #         self.recovery_detection = True
        # else:
        #     if self.recovery_detection:
        #         self.recovery_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: red; padding: 5px;}"
        #         )
        #         self.recovery_button.setText("Recovery: Off")
        #         self.recovery_detection = False
        #
        # # Landing
        # if status & (1 << 5):
        #     if not self.landing_detection:
        #         self.landing_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: green; padding: 5px;}"
        #         )
        #         self.console.append(f"{self.now_str} | DESCENT DETECTION")
        #         self.logger.info("Detekcja lądowania")
        #         print("Detekcja lądowania")
        #         self.landing_detection = True
        # else:
        #     if self.landing_detection:
        #         self.landing_button.setStyleSheet(
        #             "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: red; padding: 5px;}"
        #         )
        #         self.landing_detection = False
        #
        # snr_threshold = 5.0
        # rssi_threshold = -80.0
        # snr = self.current_data['snr']
        # rssi = self.current_data['rssi']
        #
        # if snr >= snr_threshold and rssi >= rssi_threshold:
        #     self.signal_quality = "Good"
        #     self.signal_button.setStyleSheet(
        #         "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: green; padding: 5px;}")
        # elif snr < snr_threshold and rssi < rssi_threshold:
        #     self.signal_quality = "Weak"
        #     self.signal_button.setStyleSheet(
        #         "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: red; padding: 5px;}")
        # else:
        #     self.signal_quality = "Average"
        #     self.signal_button.setStyleSheet(
        #         "QPushButton {border: 2px solid white; border-radius: 5px; background-color: black; color: yellow; padding: 5px;}")
        #
        # self.signal_button.setText(
        #     f"Signal: {self.signal_quality}")
        # self.logger.debug(
        #     f"Jakość sygnału: {self.signal_quality} (SNR: {snr}, RSSI: {rssi})")

    def closeEvent(self, event):
        if hasattr(self, "heartbeat_timer") and self.heartbeat_timer.isActive():
            self.heartbeat_timer.stop()
        if hasattr(self, "serial") and self.serial:
            self.serial.stop_reading()
        if hasattr(self, "csv_handler") and self.csv_handler:
            self.csv_handler.close_file()
        super().closeEvent(event)