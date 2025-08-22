import socket
import json
import logging
import threading

class NetworkReader:

	def __init__(self, host = "192.168.236.1", port = 65432):
		self.HOST = host # nasłuch na wszystkich interfejsach — trzeba zobaczyć, jaki jest przydzielony ip network adaptera
		self.PORT = port
		self.logger = logging.getLogger(
			'HORUS_CSS.network_reader')
		self.connect_to_server()

	def connect_to_server(self):
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

			s.bind((self.HOST, self.PORT))
			s.listen()
			self.logger.debug(f"Serwer nasłuchuje na {self.HOST}:{self.PORT}")

			self.conn, self.addr = s.accept()
			self.logger.debug(f"Połączono z {self.addr}")

			threading.Thread(target=self.read_data).start()

	def read_data(self):
		try:
			while True:
				print(self.conn)
				raw_data = self.conn.recv(1024)
				if not raw_data:
					return
				# dekodowanie bajtów na string
				text_data = raw_data.decode('utf-8')

				# zamiana JSON na słownik
				try:
					data = json.loads(text_data)
				except json.JSONDecodeError as e:
					print("Błąd dekodowania JSON:", e)
					return

				# wypisanie wszystkich pól dynamicznie
				print("Otrzymane dane telemetryczne:")
				for key, value in data.items():
					print(f"  {key}: {value}")

		except ConnectionResetError:
			print("Klient rozłączył się.")
			return

		finally:
			self.conn.close()
