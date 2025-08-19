import socket
import json

HOST = "0.0.0.0"  # nasłuch na wszystkich interfejsach
PORT = 65432

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"Serwer nasłuchuje na {HOST}:{PORT}")

    conn, addr = s.accept()
    with conn:
        print(f"Połączono z {addr}")
        while True:
            try:
                raw_data = conn.recv(1024)
                if not raw_data:
                    break  # rozłączenie klienta

                # dekodowanie bajtów na string
                text_data = raw_data.decode('utf-8')

                # zamiana JSON na słownik
                try:
                    data = json.loads(text_data)
                except json.JSONDecodeError as e:
                    print("Błąd dekodowania JSON:", e)
                    continue

                # wypisanie wszystkich pól dynamicznie
                print("Otrzymane dane telemetryczne:")
                for key, value in data.items():
                    print(f"  {key}: {value}")

            except ConnectionResetError:
                print("Klient rozłączył się.")
                break
