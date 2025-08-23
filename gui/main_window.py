import logging
import os
import platform
import subprocess
import numpy as np
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (QMainWindow, QTextEdit,
                             QWidget, QVBoxLayout,
                             QHBoxLayout, QColorDialog,
                             QHBoxLayout, QLabel,
                             QGridLayout, QVBoxLayout,
                             QFrame, QTextBrowser, QDialogButtonBox,
                             QSizePolicy, QGroupBox, QMessageBox,
                             QInputDialog, QDialog)
from gui.time_series_plot import TimeSeriesPlot
from datetime import datetime, timedelta
from serial.tools import list_ports
from PyQt6.QtGui import QIcon, QPixmap, QColor, QFont
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

        # Debug variables - to be removed
        self.current_status_index = 1
        self.status_cycle_timer = QTimer()
        self.status_cycling_active = False

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
        self.setFont(QFont("Helvetica Neue"))
        self.resize(1800, 900)
        self.showMaximized()
        self.declare_layout()
        self.declare_left_side_widgets()
        self.declare_right_side_widgets()
        self.declare_menus()

    def declare_layout(self):
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.main_layout = QGridLayout()
        self.central.setLayout(self.main_layout)

    def declare_menus(self):
        self.menu = self.menuBar()
        self.menu.setStyleSheet("""
        QMenu {
            background-color: #1e1e1e;
            color: white;
            border: 1px solid #444;
        }

        QMenu::item {
            padding: 5px 25px 5px 25px;
        }

        QMenu::item:selected {
            background-color: #555;
        }

        QMenu::indicator {
            width: 14px;
            height: 14px;
            border-radius: 7px;
            border: 1px solid #888;
            background-color: #2e2e2e;
        }

        QMenu::indicator:checked {
            background-color: #4caf50;
            border: 1px solid #4caf50;
            box-shadow: 0px 0px 2px black;
        }
        """)
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

        self.status_bar_action = self.view_menu.addAction("Status Bar")
        self.status_bar_action.setCheckable(True)
        self.status_bar_action.setChecked(True)
        self.status_bar_action.triggered.connect(self.toggle_status_bar)

        self.heartbeat_action = self.view_menu.addAction("Heartbeat")
        self.heartbeat_action.setCheckable(True)
        self.heartbeat_action.setChecked(True)
        self.heartbeat_action.triggered.connect(self.toggle_heartbeat)

        self.view_menu.addSeparator()

        self.crosshair_action = self.view_menu.addAction("Crosshair")
        self.crosshair_action.setCheckable(True)
        self.crosshair_action.setChecked(False)
        self.crosshair_action.triggered.connect(self.toggle_crosshairs)

        self.auto_zoom_action = self.view_menu.addAction("Auto-Zoom")
        self.auto_zoom_action.setCheckable(True)
        self.auto_zoom_action.setChecked(True)
        self.auto_zoom_action.triggered.connect(self.toggle_auto_zoom)

        self.data_markers_action = self.view_menu.addAction("Data Markers")
        self.data_markers_action.setCheckable(True)
        self.data_markers_action.setChecked(True)
        self.data_markers_action.triggered.connect(self.toggle_data_markers)

        self.grid_action = self.view_menu.addAction("Grid")
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(True)
        self.grid_action.triggered.connect(self.toggle_plot_grid)

        self.color_action = self.view_menu.addAction("Plot color")
        self.color_action.triggered.connect(self.change_line_colors)

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
        self.plot_speed_menu = self.test_menu.addMenu("Plot Simulation Speed")
        self.test_menu.addSeparator()
        self.test_menu.addAction("Start Status Image Cycling", self.start_status_cycling)
        self.test_menu.addAction("Stop Status Image Cycling", self.stop_status_cycling)

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


        self.plot_speed_actions = {}

        speeds = {
            "Fast (250 ms)": 250,
            "Normal (500 ms)": 500,
            "Slow (1000 ms)": 1000,
            "Very Slow (2000 ms)": 2000,
        }

        for label, interval in speeds.items():
            action = self.plot_speed_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, i=interval: self.set_plot_sim_speed(i))
            self.plot_speed_actions[label] = action

        self.plot_speed_actions["Normal (500 ms)"].setChecked(True)
        self.plot_sim_interval = 500


    def declare_left_side_widgets(self):
        self.left_layout = QVBoxLayout()
        self.main_layout.addLayout(self.left_layout, 0, 0, 1, 1)

        global_status_label = QLabel("Status: <span style='color: orange;'>not connected</span>")

        status_font =  QFont()
        status_font.setPointSize(30)
        status_font.setFamily("Helvetica Neue")
        status_font.setBold(True)
        global_status_label.setFont(status_font)

        status_wrapper = QHBoxLayout()
        status_wrapper.addStretch()
        status_wrapper.addWidget(global_status_label)
        status_wrapper.addStretch()

        self.left_layout.addLayout(status_wrapper)

        self.rocket_trajectory_label = QLabel()
        self.rocket_trajectory_label.setScaledContents(True)
        self.left_layout.addWidget(self.rocket_trajectory_label)

        pixmap = QPixmap(r"gui/resources/status_images/status-1.png")
        scaled_pixmap = pixmap.scaled(500, 650, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        self.rocket_trajectory_label.setPixmap(scaled_pixmap)
        # rocket_trajectory_label.setSizePolicy(
        #     QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.terminal_output = QTextBrowser()
        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: System ready...")
        self.terminal_output.setStyleSheet(
            "font-size: 14px;")
        self.left_layout.addWidget(self.terminal_output)

    from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QGroupBox
    from PyQt6.QtGui import QFont
    from PyQt6.QtCore import Qt

    def declare_right_side_widgets(self):
        self.right_layout = QVBoxLayout()
        self.main_layout.addLayout(self.right_layout, 0, 2, 1, 1)

        # ------------------ Recovery Bay Temperature ------------------
        self.temp_group = QGroupBox("Recovery Bay Temperature (0 °C)")
        temp_layout = QVBoxLayout()

        self.temp_plot = TimeSeriesPlot(self.default_timespan, line_color='#e74c3c')
        self.temp_plot.set_x_label("Time [s]")
        self.temp_plot.set_y_label("Temp [°C]")
        temp_layout.addWidget(self.temp_plot, stretch=1)

        self.temp_group.setLayout(temp_layout)
        self.right_layout.addWidget(self.temp_group)

        # ------------------ Recovery Bay Pressure ------------------
        self.press_group = QGroupBox("Recovery Bay Pressure (0 hPa)")
        press_layout = QVBoxLayout()

        self.press_plot = TimeSeriesPlot(self.default_timespan, line_color='#27ae60')
        self.press_plot.set_x_label("Time [s]")
        self.press_plot.set_y_label("Pressure [hPa]")
        press_layout.addWidget(self.press_plot, stretch=1)

        self.press_group.setLayout(press_layout)
        self.right_layout.addWidget(self.press_group)

        # ------------------ LoRa SNR ------------------
        self.lora_group = QGroupBox("LoRa SNR Status (0 dB)")
        lora_layout = QVBoxLayout()

        self.lora_snr_plot = TimeSeriesPlot(self.default_timespan, line_color='#2980b9')
        self.lora_snr_plot.set_x_label("Time [s]")
        self.lora_snr_plot.set_y_label("SNR [dB]")
        lora_layout.addWidget(self.lora_snr_plot, stretch=1)

        self.lora_group.setLayout(lora_layout)
        self.right_layout.addWidget(self.lora_group)

        # ------------------ Styling ------------------
        groupbox_style = """
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
            }
        """
        self.temp_group.setStyleSheet(groupbox_style)
        self.press_group.setStyleSheet(groupbox_style)
        self.lora_group.setStyleSheet(groupbox_style)

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
        state = self.heartbeat_action.isChecked()
        if state:
            self.heartbeat_timer.start(500)
            self.heartbeat_active = True
        else:
            self.heartbeat_timer.stop()
            self.heartbeat_placeholder.setStyleSheet("color: transparent; font-size: 14px;")
            self.heartbeat_active = False

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Heartbeat turned {status}</span>")
        self.logger.info(f"Heartbeat toggled to {status}")

    def toggle_crosshairs(self):
        state = self.crosshair_action.isChecked()
        for plot in [self.temp_plot, self.press_plot, self.lora_snr_plot]:
            plot.toggle_crosshair(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Crosshair turned {status}</span>")
        self.logger.info(f"Crosshair toggled to {status}")

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
        state = self.status_bar_action.isChecked()
        if state:
            self.statusBar().show()
        else:
            self.statusBar().hide()
        self.status_bar_visible = state

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Status bar turned {status}</span>")
        self.logger.info(f"Status bar toggled to {status}")

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

    def set_plot_sim_speed(self, interval):
        self.plot_sim_interval = interval
        if hasattr(self, 'plot_sim_timer') and self.plot_sim_timer.isActive():
            self.plot_sim_timer.start(self.plot_sim_interval)
        for label, action in self.plot_speed_actions.items():
            action.setChecked(action.text().startswith(f"{interval // 1000 if interval >= 1000 else interval}"))
        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: <span style='color: yellow;'>Plot simulation speed set to {self.plot_sim_interval}ms</span>")


    def generate_plot_data(self):
        current_time = datetime.now()

        temp_value = np.random.normal(50, 5)
        self.temp_plot.add_point(current_time, temp_value)
        self.temp_group.setTitle(f"Recovery Bay Temperature ({temp_value:.1f} °C)")


        snr_value = np.random.normal(5, 1.5)
        self.press_plot.add_point(current_time, snr_value)
        self.press_group.setTitle(f"Recovery Bay Pressure ({snr_value:.1f} hPa)")

        lora_snr_value = np.random.normal(25, 3)
        self.lora_snr_plot.add_point(current_time, lora_snr_value)
        self.lora_group.setTitle(f"LoRa SNR Status ({lora_snr_value:.1f} dB)")


    def clear_plots(self):
        self.temp_plot.clear_data()
        self.press_plot.clear_data()
        self.lora_snr_plot.clear_data()

        self.temp_group.setTitle(f"Recovery Bay Temperature ({0} °C)")
        self.press_group.setTitle(f"Recovery Bay Pressure ({0} hPa)")
        self.lora_group.setTitle(f"LoRa SNR Status ({0} dB)")

        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: All plots cleared")
        self.logger.info("Plots cleared")

    def clear_all(self):
        self.clear_plots()
        self.clear_terminal()

    def change_plot_timespans(self, timespan):
        self.temp_plot.update_timespan(timespan)
        self.press_plot.update_timespan(timespan)
        self.lora_snr_plot.update_timespan(timespan)

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
                "temperature": self.temp_plot,
                "pressure": self.press_plot,
                "lora": self.lora_snr_plot
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
        state = self.data_markers_action.isChecked()
        for plot in [self.temp_plot, self.press_plot, self.lora_snr_plot]:
            plot.toggle_data_markers(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Data markers turned {status}</span>")
        self.logger.info(f"Data markers toggled to {status}")

    def change_line_colors(self):
        plots = {
            "Temperature": self.temp_plot,
            "Pressure": self.press_plot,
            "LoRa SNR": self.lora_snr_plot
        }

        plot_name, ok = QInputDialog.getItem(
            self, "Select Plot", "Choose plot to change color:", list(plots.keys()), 0, False
        )

        if not ok:
            return

        current_color = plots[plot_name].line_color
        current_qcolor = QColor(current_color)

        color = QColorDialog.getColor(current_qcolor, self, "Select Line Color")

        if color.isValid():
            plots[plot_name].set_line_color(color)

            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: {color.name()};'>Plot '{plot_name}' line color changed</span>"
            )
            self.logger.info(f"Plot '{plot_name}' line color changed to {color.name()}")

    def toggle_plot_grid(self):
        state = self.grid_action.isChecked()
        for plot in [self.temp_plot, self.press_plot, self.lora_snr_plot]:
            plot.toggle_grid(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Plot grid turned {status}</span>")
        self.logger.info(f"Plot grid toggled to {status}")

    # def toggle_plot_legends(self):
    #     state = self.color_action.isChecked()
    #     for plot in [self.temp_plot, self.press_plot, self.lora_snr_plot]:
    #         plot.toggle_legend(state)

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

    def toggle_auto_zoom(self):
        state = self.auto_zoom_action.isChecked()
        for plot in [self.temp_plot, self.press_plot, self.lora_snr_plot]:
            plot.toggle_auto_zoom(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.terminal_output.append(
            f">{current_time}: <span style='color: lightblue;'>Auto-zoom turned {status}</span>")
        self.logger.info(f"Auto-zoom toggled to {status}")

    def calculate_statistics(self):
        """Calculate and display statistics for plot data"""
        try:
            stats = []

            # Calculate for each plot
            plots = {
                "Temperature": self.temp_plot,
                "Pressure": self.press_plot,
                "LoRa SNR": self.lora_snr_plot
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

    def start_status_cycling(self):
        self.status_cycle_timer.timeout.connect(self.cycle_status_image)
        self.status_cycling_active = True
        self.status_cycle_timer.start(2000)

        current_time = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.append(
            f">{current_time}: <span style='color: yellow;'>Started status image cycling (2s interval)</span>")
        self.logger.info("Started status image cycling")

    def stop_status_cycling(self):
        """Stop cycling through status images"""
        if hasattr(self, 'status_cycle_timer') and self.status_cycle_timer.isActive():
            self.status_cycle_timer.stop()
            self.status_cycling_active = False

            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: yellow;'>Stopped status image cycling</span>")
            self.logger.info("Stopped status image cycling")

    def cycle_status_image(self):
        """Cycle to the next status image"""
        self.current_status_index = (self.current_status_index % 6) + 1

        try:
            pixmap = QPixmap(f"gui/resources/status_images/status-{self.current_status_index}.png")
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(500, 650, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                # Assuming rocket_trajectory_label is accessible - you might need to make it a class variable
                self.rocket_trajectory_label.setPixmap(scaled_pixmap)

                current_time = datetime.now().strftime("%H:%M:%S")
                self.terminal_output.append(
                    f">{current_time}: <span style='color: cyan;'>Status image changed to status-{self.current_status_index}.png</span>")
            else:
                self.logger.warning(f"Could not load status-{self.current_status_index}.png")
        except Exception as e:
            self.logger.error(f"Error loading status image: {str(e)}")

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