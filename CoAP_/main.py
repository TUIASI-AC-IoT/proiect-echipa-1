import socket
import sys
import threading
from enum import Enum, auto
from threading import Lock
from typing import TypeAlias

import bitarray.util as ut
import select
from bitarray import *
from numpy import floor

# py main.py --r_port=65415 --s_port=65416 --s_ip=192.168.0.103
# from bitstring import * #posibil de ajutor

# variabile diverse
Token: TypeAlias = int
max_up_size = 1024  # max udp payload size
running = False
lock_q1 = Lock()
lock_q2 = Lock()
req_q1: list['Message'] = list()  # request queue1
req_q2: list['Message'] = list()  # request queue2
upload_collection: dict[Token, 'Content'] = dict()

# 2.01 | Created, 2.02 | Deleted, 2.03 | Valid,2.04 | Changed, 2.05 | Content
# 4.00 | Bad Request, 4.02 | Bad Option, 4.04 | Not Found
# 5.00 | Internal Server Error
RESPONSE_CODES = {
    2: [1, 2, 4, 5],
    4: [0, 2, 4],
    5: [0]
}
# 8 | Location-Path, 12 | Content-Format, 60 | Size1
OPTIONS_NUMBERS = [8, 12, 60]


class MethodCodes(Enum):
    GET = 1
    POST = 2
    PUT = 3
    DELETE = 4


class Type(Enum):
    CON = 0
    NON = 1
    ACK = 2
    RESET = 3


class MsgType(Enum):
    Request = auto()
    Response = auto()


# todo check if need prior queue

# clasa care contine pachetele si ordinea acestora
class Content:

    def __init__(self, file_path: str):
        self.file_path: str = file_path
        self.__packets: dict[int, bytes] = dict()

    def is_valid(self):
        pck_ids = sorted(self.__packets)
        for i in range(1, len(pck_ids)):
            if pck_ids[i] - 1 != pck_ids[i - 1]:
                return False
        return True

    def get_content(self) -> str:
        if self.is_valid():
            return ''.join(self.__packets[i].decode("utf-8") for i in sorted(self.__packets))

    def add_packet(self, pck_ord_no: int, pck_data: bytes):
        self.__packets[pck_ord_no] = pck_data


class Message:
    def __init__(self, msg_type):
        self.oper_param: str
        self.ord_no: int
        self.op_code: int
        self.options = None
        self.token: int
        self.msg_id: int
        self.code_details: int
        self.code_class: int
        self.tkn_length: int
        self.type: int
        self.version: int
        self.raw_request = bitarray()
        self.is_valid = False
        self.msg_type = msg_type

    # Request specific method
    def set_raw_data(self, raw_request):
        bitarray.frombytes(self.raw_request, raw_request)
        self.__disassemble_req()

    # Response specific method
    def get_raw_data(self):
        # todo continue
        self.__assemble_resp()
        return self.raw_request.tobytes()

    # todo add try catch
    def __disassemble_req(self):
        # obs1. s-a luat in considerare pentru aceasta aplicatie doar utilizarea a doua optiuni:
        # 8 - location-Path -> ascii encode
        # 12 - content-format -> ascii encode
        # obs2. aceste doua optiuni nu au caracteristica de a fi repetabile => prezenta a mai mult de doua optiuni indica o problema

        self.version = bits_to_int(self.raw_request[0:2])
        self.type = bits_to_int(self.raw_request[2:4])
        self.tkn_length = bits_to_int(self.raw_request[4:8])
        self.code_class = bits_to_int(self.raw_request[8:11])
        self.code_details = bits_to_int(self.raw_request[11:16])
        self.msg_id = bits_to_int(self.raw_request[16:32])

        idx = 32
        self.token = 0

        # for token
        if self.tkn_length > 0:
            idx = (32 + self.tkn_length * 8)
            self.token = bits_to_int(self.raw_request[32:idx])

        self.options = [[]]
        self.options.remove([])
        prev_option_number = 0
        option_nr = 0

        # for options
        while bits_to_int(self.raw_request[idx:idx + 8]) != int(0xFF) and option_nr < 2:
            # crapa la accesare indecsi, daca sirul este invalid
            option_number = bits_to_int(self.raw_request[idx:idx + 4]) + prev_option_number
            prev_option_number = option_number
            option_length = bits_to_int(self.raw_request[idx + 4:idx + 8])
            option_value = (self.raw_request[idx + 8:idx + (option_length + 1) * 8]).tobytes().decode("utf-8")
            self.options.append([option_number, option_value])
            idx = idx + (option_length + 1) * 8
            option_nr += 1

        # for coap payload
        if bits_to_int(self.raw_request[idx:idx + 8]) == int(0xFF):
            self.is_valid = True
            idx += 8
            self.op_code = bits_to_int(self.raw_request[idx:idx + 3])
            self.ord_no = bits_to_int(self.raw_request[idx + 3:idx + 19])
            self.oper_param = (self.raw_request[idx + 19:]).tobytes().decode("utf-8")

    def __assemble_resp(self):
        # todo not good now
        bitarray.frombytes(self.raw_request, int_to_bytes(self.version, 1))
        ut.strip(self.raw_request, "left")
        part = bitarray()
        bitarray.frombytes(part, int_to_bytes(self.type, 1))
        ut.strip(part, "left")
        self.raw_request += part
        # todo continue

    def __repr__(self):
        if self.is_valid:
            return "raw_req: " + str(self.raw_request).replace("bitarray('", "").replace("')",
                                                                                         "") + "\nversion: " + str(
                self.version) + \
                   "\ntype: " + str(self.type) + "\ntkn_length: " + str(self.tkn_length) + \
                   "\ncode_class: " + str(self.code_class) + "\ncode_details: " + str(self.code_details) + \
                   "\nmsg_id: " + str(self.msg_id) + "\ntoken: " + str(self.token) + \
                   "\noptions: " + str(self.options) + "\nop_code: " + str(self.op_code) + \
                   "\nord_no: " + str(self.ord_no) + "\noper_param: " + str(self.oper_param)
        else:
            return "invalid request"


def main_th_fct():
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
            data_rcv, address = soc.recvfrom(max_up_size)
            new_request = Message(MsgType.Request)
            new_request.set_raw_data(data_rcv)
            req_q1.append(new_request)
            # todo awake serv_th1
            print("RECEIVED ===> ", new_request, " <=== FROM: ", address)
            # print("cnt= ", counter)


def int_to_bytes(value, length):
    return int(value).to_bytes(byteorder="big", signed=False, length=length)


def bits_to_int(value):
    if len(value) % 8 != 0:
        value = bitarray("0" * (int(floor((len(value) / 8) + 1) * 8) - len(value))) + value
        # print("param=> " + str(param))
    return int.from_bytes(value.tobytes(), "big")


# START ------ check functions for CoAP header ------ START

def check_type(msg: Message):
    return msg.type in [t.value for t in Type]


def check_code(msg: Message):
    if msg.msg_type == MsgType.Request:
        if msg.code_class == 0 and msg.code_details in [mc.value for mc in MethodCodes]:
            return True
    else:
        if msg.code_class in RESPONSE_CODES.keys():
            if msg.code_details in RESPONSE_CODES[msg.code_details]:
                return True
    return False


def check_msg_id(msg: Message):
    return msg.msg_id is not None


def check_token_tkl(msg: Message):
    return (0 <= msg.tkn_length <= 8) and (msg.token is not None)


def check_options(msg: Message):
    for opt in msg.options:
        if opt[0] not in OPTIONS_NUMBERS or opt[1] is None:
            return False
    return True


def check_op_code(msg: Message):
    return 0 <= msg.op_code <= 7


def check_ord_no(msg: Message):
    if msg.op_code > 0:
        if msg.ord_no != 0:
            return False
    else:
        if msg.ord_no < 0:
            return False
    return True


def check_oper_param(msg: Message):
    result = False
    if msg.op_code == 0:
        if msg.code_class == 0:
            if msg.code_details == MethodCodes.PUT.value:
                result = bool(msg.oper_param)
            elif msg.code_details == MethodCodes.GET.value:
                result = not msg.oper_param
    elif msg.op_code in [2, 4, 6]:
        result = not msg.oper_param
    else:
        result = bool(msg.oper_param)

    return result


# END ------ check functions for CoAP header ------ END

# functions that check the header without the payload part
check_functions = [
    [check_type, check_code, check_msg_id, check_token_tkl, check_options],  # part1 without payload
    [check_op_code, check_ord_no, check_oper_param]  # payload part
]


def sintatic_analizer(msg: Message) -> bool:
    valid: bool = msg.is_valid
    if valid:
        # messages with version number not equal to 1 MUST be silently ignored
        if msg.version == 1:

            for fun in check_functions[0]:
                value = fun(msg)
                if not value:
                    valid = False
                    break

            # if the CoAP format is invalid
            if not valid:
                # todo send RST
                pass
            else:
                # check the payload format
                for fun in check_functions[1]:
                    if not fun(msg):
                        valid = False
                        break
                if valid:
                    # todo send ACK
                    pass

        else:
            valid = False

    return valid


def deduplicator(msg: Message) -> bool:
    # check if message id already exists in ReqQueue2
    with lock_q2:
        if msg.msg_id not in [m.msg_id for m in req_q2]:
            req_q2.append(msg)
            return True
        else:
            pass  # eventual log
    return False


def service_th1_fct():
    while len(req_q1) != 0:
        msg: Message
        with lock_q1:
            msg = req_q1.pop(0)
        if msg is not None:
            if sintatic_analizer(msg):
                if deduplicator(msg):
                    # todo awake thread 2
                    pass


def service_th2_fct():
    while len(req_q2) != 0:
        pass


"""
def request_processor(params):  
    #TODO
    pass
"""

if __name__ == '__main__':

    # todo awake and sleep mecans for threads
    # todo colectie care contine toate thread urile petru join sau alte necesitati

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
            useless = input("Send: ")
            test_data = bitarray('01101101 01100101 01110011 01100001 01101010 00100000 01101101 01100101 01110011')
            soc.sendto(test_data.tobytes(), (s_ip, int(s_port)))
        except KeyboardInterrupt:
            running = False
            print("Waiting for the thread to close...")
            main_thread.join()
            break

"""
def bytes_to_bits(data):
    def access_bit(data_inn, num):
        #sursa functie access_bit: https://stackoverflow.com/questions/43787031/python-byte-array-to-bit-array
        base = int(num // 8)
        shift = int(num % 8)
        return (data_inn[base] >> shift) & 0x1

    return str([access_bit(data, i) for i in range(len(data) * 8)]).replace(",", "").replace("[", "").replace("]", "").replace(" ", "")
 #used as #bitarray(bytes_to_bits(data_rcv))
"""
