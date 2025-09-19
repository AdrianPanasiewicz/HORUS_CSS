import socket
import json
import logging
import threading
from time import sleep

class NetworkReader:

	def __init__(self, host = "192.168.236.1", port = 65432):
		self.HOST = host
		self.PORT = port
		self.conn = None
		self.stop_requested = False
		self.logger = logging.getLogger(
			'HORUS_CSS.network_reader')
		self.on_connection_subscibers = []
		self.on_disconnection_subscibers = []
		self.on_data_received_subscibers = []

	def connect_to_server(self):
		server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		server_socket.bind((self.HOST, self.PORT))
		server_socket.listen()
		server_socket.settimeout(1.0)

		self.logger.info(f"Server listening on {self.HOST}:{self.PORT}")

		while not self.stop_requested:
			try:
				self.conn, self.addr = server_socket.accept()
				self.logger.info(f"Connected with {self.addr}")

				for callback in self.on_connection_subscibers:
					callback()

				threading.Thread(target=self.heartbeat_check, daemon=True).start()
				self.read_data()

			except socket.timeout:
				continue
			except OSError as e:
				if not self.stop_requested:
					self.logger.error("Socket error in accept(): %s", e)
				sleep(1)

		server_socket.close()
		self.logger.info("NetworkReader stopped")

	def read_data(self):
		try:
			while True:
				raw_data = self.conn.recv(1024)
				if not raw_data:
					return
				# dekodowanie bajtów na string
				text_data = raw_data.decode('utf-8')

				# zamiana JSON na słownik
				try:
					data = json.loads(text_data)
				except json.JSONDecodeError as e:
					self.logger.error("Błąd dekodowania JSON:", e)
					return

				for on_data_received in self.on_data_received_subscibers:
					on_data_received(data)

		except ConnectionResetError:
			self.logger.error("Klient rozłączył się.")
			for on_disconnection in self.on_disconnection_subscibers:
				on_disconnection()
			return

		finally:
			self.conn.close()

	def send(self, data: dict):
		if not self.conn:
			self.logger.error("No active connection to send data.")
			return
		try:
			message = json.dumps(data).encode('utf-8')
			self.conn.sendall(message)
			self.logger.debug(f"Sent: {data}")
		except (BrokenPipeError, ConnectionResetError, OSError) as e:
			self.logger.error(f"Error sending data: {e}")
			self.conn = None

	def heartbeat_check(self):
		while self.conn and not self.stop_requested:
			try:
				self.conn.send(b'')
				sleep(0.5)
			except (BrokenPipeError, ConnectionResetError, OSError):
				self.logger.warning("Connection lost during heartbeat check.")
				self.conn.close()
				self.conn = None
				for on_disconnection in self.on_disconnection_subscibers:
					on_disconnection()
				break
		self.connect_to_server()

	def subcribe_on_connection(self, callback):
		self.on_connection_subscibers.append(callback)
		self.logger.info(f"Added {callback} as a subscriber to on_connection_subscibers.")

	def subcribe_on_disconnect(self, callback):
		self.on_disconnection_subscibers.append(callback)
		self.logger.info(f"Added {callback} as a subscriber to on_disconnection_subscibers.")

	def subcribe_on_data_received(self, callback):
		self.on_data_received_subscibers.append(callback)
		self.logger.info(f"Added {callback} as a subscriber to on_data_received_subscibers.")

	def stop(self):
		self.logger.info("Stop requested for NetworkReader")
		self.stop_requested = True
		if self.conn:
			self.conn.close()
			self.conn = None
