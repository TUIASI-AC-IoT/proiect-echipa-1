import socket
import sys
import threading
from threading import Lock
from enum import Enum, auto
from typing import TypeAlias

import select
from bitarray import *
from numpy import floor

# py main.py --r_port=65415 --s_port=65416 --s_ip=192.168.0.103

# variabile diverse
Token: TypeAlias = int
max_up_size = 65507  # max udp payload size
total_nr_options = 3  # numarul total de optiuni posibile intr-un mesaj
running = False
lock_q1 = Lock()
lock_q2 = Lock()
req_q1: list['Message'] = list()  # request queue1
req_q2: list['Message'] = list()  # request queue2
upload_collection: dict[Token, 'Content'] = dict()


class MsgType(Enum):
    Request = auto()
    Response = auto()


class Type(Enum):
    CON = 0
    NON = 1
    ACK = 2
    RESET = 3


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

    # todo
    # def get_content(self) -> str:
    #     if self.is_valid():
    #         return ''.join(self.__packets[i] for i in sorted(self.__packets))

    def add_packet(self, pck_ord_no: int, pck_data: bytes):
        self.__packets[pck_ord_no] = pck_data


# clasa generica pentru mesajele coap specifice
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
        self.msg_type = msg_type
        self.is_valid = False
        self.invalid_reasons = []

    # Request specific method
    def set_raw_data(self, raw_request):
        bitarray.frombytes(self.raw_request, raw_request)
        try:
            self.__disassemble_req()
        except:
            self.is_valid = False

    # Response specific method
    def get_raw_data(self):
        try:
            self.__assemble_resp()
            return self.raw_request.tobytes()
        except:
            return bytes("00")

    def __disassemble_req(self):
        # obs1. s-a luat in considerare pentru aceasta aplicatie doar utilizarea a trei optiuni:
        # 8 - location-Path -> ascii encode
        # 12 - content-format -> ascii encode
        # 60 - Size1 -> ascii encoded
        # obs2. aceste trei optiuni nu au caracteristica de a fi repetabile => prezenta a mai mult de trei optiuni indica o problema

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
        while bits_to_int(self.raw_request[idx:idx + 8]) != int(0xFF) and option_nr < total_nr_options:
            ext_delta_bytes = 0  # extra delta bytes
            ext_option_bytes = 0  # extra length bytes

            # option_delta
            option_number = bits_to_int(self.raw_request[idx:idx + 4])

            if option_number < 13:
                option_number += prev_option_number
            elif option_number == 13:
                option_number = bits_to_int(self.raw_request[idx + 8:idx + 16]) - 13 + prev_option_number
                ext_delta_bytes = 1
            elif option_number == 14:
                option_number = bits_to_int(self.raw_request[idx + 8:idx + 24]) - 269 + prev_option_number
                ext_delta_bytes = 2
            else:
                self.invalid_reasons.append(
                    "__disassemble_req: Option delta incorect (teoretic 15, practic >=15): " + str(option_number))
                raise Exception
            prev_option_number = option_number

            # option length
            option_length = bits_to_int(self.raw_request[idx + 4:idx + 8])

            try:
                if option_length > 0:
                    if option_length < 13:
                        option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (
                                ext_delta_bytes + option_length + 1) * 8]).tobytes().decode("utf-8")
                        self.options.append([option_number, option_value])
                    elif option_length == 13:
                        option_length = bits_to_int(
                            self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (ext_delta_bytes + 2) * 8]) - 13
                        option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 2):idx + (
                                ext_delta_bytes + option_length + 2) * 8]).tobytes().decode("utf-8")
                        self.options.append([option_number, option_value])
                        ext_option_bytes = 1
                    elif option_length == 14:
                        option_length = bits_to_int(
                            self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (ext_delta_bytes + 3) * 8]) - 269
                        option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 3):idx + (
                                ext_delta_bytes + option_length + 3) * 8]).tobytes().decode("utf-8")
                        self.options.append([option_number, option_value])
                        ext_option_bytes = 2
                    else:
                        self.invalid_reasons.append(
                            "__disassemble_req:option lenght incorect (teoretic 15, practic >=15): " + str(
                                option_length))
                        raise Exception
                else:
                    self.invalid_reasons.append(
                        "__disassemble_req:option lenght incorect (teoretic 15, practic >=15): " + str(option_length))
                    raise Exception

                idx = idx + (ext_delta_bytes + option_length + ext_option_bytes + 1) * 8
                option_nr += 1
            except Exception as e:
                self.invalid_reasons.append("__disassemble_req:" + str(e))
                raise e

        # for coap payload
        if bits_to_int(self.raw_request[idx:idx + 8]) == int(0xFF):
            self.is_valid = True
            idx += 8
            self.op_code = bits_to_int(self.raw_request[idx:idx + 3])
            self.ord_no = bits_to_int(self.raw_request[idx + 3:idx + 19])
            try:
                self.oper_param = (self.raw_request[idx + 19:]).tobytes().decode("utf-8")
            except Exception as e:
                self.invalid_reasons.append("__disassemble_req:" + str(e))
                raise e

    def __assemble_resp(self):
        # version
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.version, 1))
        result = value[-2:]

        # type
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.type, 1))
        result += value[-2:]

        # token length
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.tkn_length, 1))
        result += value[-4:]

        # code.class
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.code_class, 1))
        result += value[-3:]

        # code.details
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.code_details, 1))
        result += value[-5:]

        # message id
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.msg_id, 2))
        result += value

        # token value
        if self.tkn_length > 0:
            value = bitarray()
            bitarray.frombytes(value, int_to_bytes(self.token, self.tkn_length))
            result += value

        # options
        # options[idx][0] - option nr
        # options[idx][1] - option value
        prev_option_nr = 0

        for idx in range(len(self.options)):

            if len(self.options[idx][1].encode('utf-8')) > 0:
                option_delta = self.options[idx][0] - prev_option_nr
                prev_option_nr = self.options[idx][0]

                if option_delta < 13:
                    result = self.__method(result, option_delta, 1, False)

                    if len(self.options[idx][1].encode('utf-8')) < 13:
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')), 1, False)

                    elif len(self.options[idx][1].encode('utf-8')) < 243:  # 256-13
                        result = self.__method(result, 13, 1, False)
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')) + 13, 1, True)

                    elif len(self.options[idx][1].encode('utf-8')) < 65266:  # 65535-269
                        result = self.__method(result, 14, 1, False)
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')) + 269, 2, True)
                    else:
                        self.invalid_reasons.append("__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[idx][1].encode('utf-8'))))
                        raise Exception

                elif option_delta < 243:
                    result = self.__method(result, 13, 1, False)

                    if len(self.options[idx][1].encode('utf-8')) < 13:
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')), 1, False)
                        result = self.__method(result, option_delta + 13, 1, True)

                    elif len(self.options[idx][1].encode('utf-8')) < 243:  # 256-13
                        result = self.__method(result, 13, 1, False)
                        result = self.__method(result, option_delta + 13, 1, True)
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')) + 13, 1, True)

                    elif len(self.options[idx][1].encode('utf-8')) < 65266:  # 65535-269
                        result = self.__method(result, 14, 1, False)
                        result = self.__method(result, option_delta + 13, 1, True)
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')) + 269, 2, True)
                    else:
                        self.invalid_reasons.append("__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[idx][1].encode('utf-8'))))
                        raise Exception

                elif option_delta < 65266:
                    result = self.__method(result, 14, 1, False)

                    if len(self.options[idx][1].encode('utf-8')) < 13:
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')), 1, False)
                        result = self.__method(result, option_delta + 269, 2, True)

                    elif len(self.options[idx][1].encode('utf-8')) < 243:  # 256-13
                        result = self.__method(result, 13, 1, False)
                        result = self.__method(result, option_delta + 269, 2, True)
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')) + 13, 1, True)

                    elif len(self.options[idx][1].encode('utf-8')) < 65266:  # 65535-269
                        result = self.__method(result, 14, 1, False)
                        result = self.__method(result, option_delta + 269, 2, True)
                        result = self.__method(result, len(self.options[idx][1].encode('utf-8')) + 269, 2, True)
                    else:
                        self.invalid_reasons.append("__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[idx][1].encode('utf-8'))))
                        raise Exception

                value = bitarray()
                bitarray.frombytes(value, self.options[idx][1].encode('utf-8'))
                result += value
            else:
                self.invalid_reasons.append("__assemble_resp: lungimea optiunii este 0")
                raise Exception

        # payload marker
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(int(0xFF), 1))
        result += value

        # operation code
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.op_code, 1))
        result += value[-3:]

        # order number
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(self.ord_no, 2))
        result += value

        # operation parameter
        value = bitarray()
        bitarray.frombytes(value, self.oper_param.encode('utf-8'))
        result += value

        return result.tobytes()

    def __method(self, pack, val_to_conv, bytes_nr, add_full):
        value = bitarray()
        bitarray.frombytes(value, int_to_bytes(val_to_conv, bytes_nr))
        if add_full:
            pack += value
        else:
            pack += value[-4:]
        return pack

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
            return "Invalid request. Check reasons: " + str(self.invalid_reasons)


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

            new_request2 = Message(MsgType.Response)
            new_request2.set_raw_data(new_request.get_raw_data())

            # todo awake serv_th1
            print("DATA ===>\n", new_request, " \n<=== FROM: ", address)
            print("DATA ===>\n", new_request2, " \n<=== FROM: ", address)
            # # print("cnt= ", counter)


def int_to_bytes(value, length):
    return int(value).to_bytes(byteorder="big", signed=False, length=length)


def bits_to_int(value):
    if len(value) % 8 != 0:
        value = bitarray("0" * (int(floor((len(value) / 8) + 1) * 8) - len(value))) + value
        # print("param=> " + str(param))
    return int.from_bytes(value.tobytes(), "big")


def deduplicator(msg: Message):
    # check if message id already exists in ReqQueue2
    with lock_q2:
        if msg.msg_id not in [m.msg_id for m in req_q2]:
            req_q2.append(msg)
        else:
            pass  # todo eventual log


""" 

def gen_token():
    #TODO
    PASS
    
def gen_msg_id():
    #todo
    pass

def service_th1_fct():  
    #TODO
    pass


def service_th2_fct():  
    #TODO
    pass

def sintatic_analizer(params):
    # todo va face check pe response si pe request sa vada ca sunt corecte
    pass

"""

"""
def request_processor(params):  
    #TODO
    pass
"""

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
            useless = input("Send: ")
            test_data = bitarray('01101101 01100101 01110011 01100001 01101010 00100000 01101101 01100101 01110011')
            soc.sendto(test_data.tobytes(), (s_ip, int(s_port)))
        except KeyboardInterrupt:
            running = False
            print("Waiting for the thread to close...")
            main_thread.join()
            break
