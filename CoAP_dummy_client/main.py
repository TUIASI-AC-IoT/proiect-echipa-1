import socket
import sys
import threading
from enum import Enum, auto
from threading import Lock
from typing import TypeAlias
import select
from bitarray import *
from numpy import floor

# py main.py --r_port=65416 --s_port=65415 --s_ip=192.168.0.103

# variabile diverse
Token: TypeAlias = int
max_up_size = 65507  # max udp payload size
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
total_nr_options = len(OPTIONS_NUMBERS)  # numarul total de optiuni posibile intr-un mesaj

class MsgType(Enum):
    Request = auto()
    Response = auto()


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
            return self.__assemble_resp()
        except:
            return int(0).to_bytes(1,"little",signed=False)

    def __disassemble_req(self):
        # obs1. soc-a luat in considerare pentru aceasta aplicatie doar utilizarea a trei optiuni:
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
            self.op_code = bits_to_int(self.raw_request[idx:idx + 4])
            self.ord_no = bits_to_int(self.raw_request[idx + 4:idx + 20])
            try:
                self.oper_param = (self.raw_request[idx + 20:]).tobytes().decode("utf-8")
                # todo be carefull added for removing unknow aperance reason char
                self.oper_param = self.oper_param[:len(self.oper_param) - 1]
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
        result = self.__method(result, self.msg_id, 2, True)

        # token value
        if self.tkn_length > 0:
            result = self.__method(result, self.token, self.tkn_length, True)

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
        result += value[-4:]

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


def int_to_bytes(value, length):
    return int(value).to_bytes(byteorder="big", signed=False, length=length)


def bits_to_int(value):
    if len(value) % 8 != 0:
        value = bitarray("0" * (int(floor((len(value) / 8) + 1) * 8) - len(value))) + value
    return int.from_bytes(value.tobytes(), "big")


def receive_fct():
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
            data_rcv, address = soc.recvfrom(max_up_size)
            new_request = Message(MsgType.Request)
            new_request.set_raw_data(data_rcv)
            req_q1.append(new_request)
            # todo awake serv_th1
            print("\nDATA ===>\n", new_request, " \n<=== FROM: ", address)
            # # print("cnt= ", counter)


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
soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

soc.bind(('0.0.0.0', int(r_port)))

running = True

try:
    receive_thread = threading.Thread(target=receive_fct)
    receive_thread.start()
except:
    print("Eroare la pornirea thread‐ului")
    sys.exit()

while True:
    try:
        useless = input("Send(enter): ")
        response = Message(MsgType.Response)
        response.version = 1
        response.type = Type.CON.value
        response.tkn_length = 5
        response.code_class = 0
        response.code_details = MethodCodes.PUT.value
        response.msg_id = 200
        response.token = 20
        response.options = [[8, "If you're visiting this page, you're likely here because you're searching for a random sentence. Sometimes a random word just isn't enough, and that is where the random sentence generator comes into play. By inputting the desired number, you can make a list of as many random sentences as you want or need. Producing random sentences can be helpful in a number of different ways."], [12, "cacaca"], [60,"acadele de text"]]
        response.op_code = 0
        response.ord_no = 0
        response.oper_param = "text in payload de test"
        # set response data
        data=response.get_raw_data()
        soc.sendto(data,(s_ip, int(s_port)))
        #     test_data = bitarray('00 11 0001 111 00000 1111111111111111 11111111    1110 1101 00000001 01010011 00100111 01000001 01000011 01000101 01010011 01010100 01000001 00100000 01000101 01010011 01010100 01000101 00100000 01010101 01001110 00100000 01010100 01000101 01011000 01010100 00100000 01000100 01000101 00100000 01010000 01010010 01001111  1101 1110 00111000 0000001000000001 01100100 01110010 01100001 01100111 01100001 00100000 01101010 01110101 01110010 01101110 01100001 01101100 00100000 01100001 01110011 01110100 01100001 01111010 01101001 00100000 01100101 01110101 00100000 01101101 00101101 01100001 01101101 00100000 01100001 01110000 01110101 01100011 01100001 01110100 00100000 01100100 01100101 00100000 01100011 01101111 01100100 01100001 01110100 00100000 01101100 01100001 00100000 01110000 01110010 01101111 01101001 01100101 01100011 01110100 00100000 01110110 01110010 01100101 01100001 01110101 00100000 01110011 01100001 00100000 01110011 01110000 01110101 01101110 00100000 01100011 01100001 00100000 01101001 01101101 01101001 00100000 01110110 01101001 01101110 01100101 00100000 01110011 01100001 00100000 01101001 01101101 01101001 00100000 01100010 01100001 01100111 00100000 01110000 01110101 01101100 01100001 00100000 01101001 01101110 00100000 01100101 01101100 00100000 01100011 01100001 00100000 01101101 01101001 00100000 01110011 01100101 00100000 01110000 01100001 01110010 01100101 00100000 01100110 01101111 01100001 01110010 01110100 01100101 00100000 01100110 01101111 01100001 01110010 01110100 01100101 00100000 01101111 01100010 01101111 01110011 01101001 01110100 01101111 01110010 00100000 01110011 01101001 00100000 01100001 01100011 01110101 01101101 00100000 01100101 01110101 00100000 01110011 01100011 01110010 01101001 01110101 00100000 01110101 01101110 00100000 01110100 01100101 01111000 01110100 00100000 01100100 01100101 00100000 01110100 01100101 01110011 01110100 00100000 01100100 01100101 00100000 01101100 01110101 01101110 01100111 01101001 01101101 01100101 00100000 00110010 00110100 00110100 00100000 00110001 00110101 00100000 01110011 01101001 00100000 01100011 01110101 00100000 00110001 00110101 00100000 01110011 01101001 00100000 00110001 00110101 00101110 00100000 01110000 01110101 01101100 01100001 00100000 01101101 01100101 01100001 00100000 01100101 01110011 01110100 01100101 00100000 01100110 01101111 01100001 01110010 01110100 01100101 00100000 01100110 01101111 01100001 01110010 01110100 01100101 00100000 01101101 01100001 01110010 01100101 00100000 01101101 01100001 01110010 011001011111 1111 000 1111111111111111 01110100 01100101 01111000 01110100 00100000 01100100 01100101 00100000 01110100 01100101 01110011 01110100')
        #     soc.sendto(test_data.tobytes(), (s_ip, int(s_port)))
    except KeyboardInterrupt:
        running = False
        print("Waiting for the thread to close...")
        receive_thread.join()
        break
