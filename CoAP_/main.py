import select
import socket
import sys
import threading

import general_use as gu
from message import Message
from sintatic_analizer import sintatic_analizer


# py main.py --r_port=65415 --s_port=65416 --s_ip=192.168.0.103


def main_th_fct():
    # to do sync mechans for queues
    counter = 0
    while running:
        # todo de intrebat rol
        # Apelam la functia sistem IO -select- pentru a verifca daca socket-ul are date in bufferul de receptie
        # Stabilim un timeout de 1 secunda
        r, _, _ = select.select([soc], [], [], 1)
        if not r:
            counter = counter + 1
            # todo de intrebat rol
        else:
            data_rcv, address = soc.recvfrom(gu.max_up_size)
            new_request = Message(gu.MsgType.Request)
            new_request.set_raw_data(data_rcv)
            gu.req_q1.append(new_request)

            print(sintatic_analizer(new_request))
            # todo awake serv_th1
            print("\nDATA ===>\n", new_request, " \n<=== FROM: ", address)
            # # print("cnt= ", counter)


if __name__ == '__main__':

    # todo awake and sleep mecans for threads
    # todo colectie care contine toate thread urile petru join sau alte necesitati
    # todo logging
    # todo exceptions handling

    if len(sys.argv) != 4:
        print("Help : ")
        print("  --r_port=receive port number ")
        print("  --s_port=send port number ")
        print("  --s_ip=send ip ")
        sys.exit()

    # todo de intrebat primit data request de oriunde, orice ip sau primit prin parametri
    for arg in sys.argv:
        if arg.startswith("--r_port"):
            temp, r_port = arg.split("=")
        elif arg.startswith("--s_port"):
            temp, s_port = arg.split("=")
        elif arg.startswith("--s_ip"):
            temp, s_ip = arg.split("=")

    # Creare socket UDP
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    soc.bind(('0.0.0.0', int(r_port)))

    running = True

    try:
        # todo pornit celelalte threaduri
        main_thread = threading.Thread(target=main_th_fct, name="Main Thread")
        main_thread.start()
    except:
        print("Eroare la pornirea main thread‐ului")
        sys.exit()

    while True:
        # todo control comands for basic terminal
        try:
            useless = input("Send(enter):\n")
            response = Message(gu.MsgType.Response)
            # set response data
            soc.sendto(response.get_raw_data(), (s_ip, int(s_port)))
        except KeyboardInterrupt:
            running = False
            print("Waiting for the thread to close...")
            main_thread.join()
            try:
                gu.msg_id_file.close()
                gu.token_file.close()
            except:
                pass
            break
