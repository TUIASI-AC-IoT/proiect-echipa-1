import socket
import sys
import select
import threading

#py main.py --r_port=65416 --s_port=65415 --s_ip=192.168.0.103
from bitarray import bitarray


def receive_fct():
    global running
    counter = 0
    while running:
        # Apelam la functia sistem IO -select- pentru a verifca daca socket-ul are date in bufferul de receptie
        # Stabilim un timeout de 1 secunda
        r, _, _ = select.select([s], [], [], 1)
        if not r:
            counter = counter + 1
        else:
            data, address = s.recvfrom(1024)
            print("RECEIVED ===> ", data, " <=== FROM: ", address)
            print("cnt=", counter)


# Citire nr port din linia de comanda
if len(sys.argv) != 4:
    print("help : ")
    print("  --r_port=receive port ")
    print("  --s_port=send port ")
    print("  --s_ip=sen ip")
    sys.exit()

for arg in sys.argv:
    if arg.startswith("--r_port"):
        temp, r_port = arg.split("=")
    elif arg.startswith("--s_port"):
        temp, s_port = arg.split("=")
    elif arg.startswith("--s_ip"):
        temp, s_ip = arg.split("=")

# Creare socket UDP
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

s.bind(('0.0.0.0', int(r_port)))

running = True

try:
    receive_thread = threading.Thread(target=receive_fct)
    receive_thread.start()
except:
    print("Eroare la pornirea thread‐ului")
    sys.exit()

while True:
    try:
        useless = input("Send: ")
        test_data = bitarray('00 11 0001 111 00000 1111111111111111 11111111 0001 0010 01000001 01000010  0010 0010 01000011 01000100 1111 1111 000 1111111111111111 0000000000000000')
        s.sendto(test_data.tobytes(), (s_ip, int(s_port)))
    except KeyboardInterrupt:
        running = False
        print("Waiting for the thread to close...")
        receive_thread.join()
        break
