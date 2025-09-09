import sys
import logging
import platform
import threading
from functools import partial
from PyQt6.QtWidgets import QApplication, QDialog
from gui.main_window import MainWindow
from core.serial_config import SerialConfigDialog
from core.network_reader import NetworkReader
from core.utils import Utils
from core.config import Config
from core.gpio_reader import GpioReader
import os

def main():

    session_dir = Utils.create_session_directory()
    log_file = os.path.join(session_dir, 'app_events.log')

    logging.basicConfig(
        filename=log_file,
        filemode='a',
        level=logging.INFO,
        format='%(asctime)s %(levelname)-8s %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('HORUS_CSS_logger')
    logger.info(f"Log file location: {log_file}")
    logger.info("Uruchamianie aplikacji")

    app = QApplication(sys.argv)

    config_dialog = SerialConfigDialog()
    if config_dialog.exec() == QDialog.DialogCode.Accepted:
        config = config_dialog.get_settings()
        logger.info(f"Konfiguracja portu załadowana: {config}")
    else:
        config = {'port': "", 'baudrate': Config.DEFAULT_BAUD_RATE, 'lora_config': None, 'is_config_selected': True,
        "network": {'ip_address': Config.DEFAULT_IP_ADDRESS, "port": Config.DEFAULT_IP_PORT}}
        logger.info("Użytkownik zrezygnował z portu – używam domyślnych ustawień")

    network_config = config['network']
    network_reader = NetworkReader(host=network_config['ip_address'], port=int(network_config['port']))

    gpio_reader = GpioReader(Config.DEFAULT_GPIO_PIN)
    gpio_reader.subscribe_when_held(partial(network_reader.send, {"event": "mission_abort_pressed"}))

    window = MainWindow(config, network_reader, gpio_reader)
    network_thread = threading.Thread(target=network_reader.connect_to_server, daemon=True)
    network_thread.start()

    window.show()

    exit_code = app.exec()
    logger.info(f"Aplikacja zakończona z kodem {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    operational_system = platform.system()
    if operational_system == 'Windows':
        os.environ["QT_QPA_PLATFORM"] = "windows"
    elif operational_system == 'Linux':
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    elif operational_system == 'Darwin':
        os.environ["QT_QPA_PLATFORM"] = "cocoa"
    try:
        main()
    except Exception as e:
        logger = logging.getLogger('HORUS_CSS_logger')
        logger.error(f"An exception has occurred: {e}")
        print("An exception has occurred: ", e)
