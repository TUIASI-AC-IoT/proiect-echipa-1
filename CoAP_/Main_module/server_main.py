import sys

import cmd_interpreter as ci
import general_use as gu
import threads as th
from message import Message


# for terminal start use
# python dummy_client_main.py --r_port=65415 --s_port=65416 --s_ip=127.0.0.1
# python dummy_client_main.py --r_port=65414 --s_port=65413 --s_ip=127.0.0.1

# filtru pentru wireshark
# udp and ip.addr==192.168.0.102 and ip.addr==192.168.0.104


def receive_request():
    data_rcv, address = gu.socket_.recvfrom(gu.max_up_size)
    new_request = Message(gu.MsgType.Request)
    new_request.set_raw_data(data_rcv)
    gu.req_q1.append(new_request)
    if gu.printdata_flag:
        print("RECEIVED:\n", new_request, "\nFROM: ", address)
    if gu.logdata_flag:
        gu.log.info("RECEIVED:\n " + str(new_request) + "\nFROM:" + str(address))
    else:
        gu.log.info("RECEIVED DATA (logdata off) FROM:" + str(address))


def send_response(response: Message):
    gu.socket_.sendto(response.get_raw_data(), (gu.s_ip, int(gu.s_port)))


def close_execution():
    th.stop_threads()
    try:
        gu.msg_id_file.close()
        gu.token_file.close()
    except:
        pass


if __name__ == '__main__':

    for arg in sys.argv:
        if arg.startswith("--r_port"):
            temp, gu.r_port = arg.split("=")
        elif arg.startswith("--s_port"):
            temp, gu.s_port = arg.split("=")
        elif arg.startswith("--s_ip"):
            temp, gu.s_ip = arg.split("=")

    try:
        # Creare socket UDP
        gu.socket_.bind(('0.0.0.0', int(gu.r_port)))
    except Exception as e:
        gu.log.error(
            "if __name__ == '__main__': Eroare la creearea socketului UDP. Detalii:" + str(e) + ". Execution aborted!")
        sys.exit()

    try:
        th.start_threads()
    except Exception as e:
        gu.log.error(
            "if __name__ == '__main__': Eroare la pornirea thread‐urilor. Detalii:" + str(e) + ". Execution aborted!")
        sys.exit()

    while True:
        try:
            cmd = input("\n-->Working (CTRL+C to stop or insert cmd):\n-->")

            if cmd != "":
                ci.cmd_interpreter(cmd)

        except KeyboardInterrupt:
            close_execution()
            sys.exit()
