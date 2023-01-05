import os
import socket
import sys
import threading
from enum import Enum, auto
from os.path import isfile
from threading import Lock

import select
from bitarray import *
from numpy import floor

# python dummy_client_main.py --r_port=65416 --s_port=65415 --s_ip=127.0.0.1
# python dummy_client_main.py --r_port=65413 --s_port=65414 --s_ip=127.0.0.1

# variabile diverse
Token = int
max_up_size = 60000  # max udp payload size
running = False
lock_q1 = Lock()
lock_q2 = Lock()
req_q1: list['Message'] = list()  # request queue1
req_q2: list['Message'] = list()  # request queue2
msg_id = 0

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
        self.oper_param: str = str()
        self.ord_no: int = int()
        self.op_code: int = int()
        self.options: dict[int, str] = dict()
        self.token: int = int()
        self.msg_id: int = int()
        self.code_details: int = int()
        self.code_class: int = int()
        self.tkn_length: int = int()
        self.type: int = int()
        self.version: int = int()
        self.raw_request = bitarray()
        self.msg_type = msg_type
        self.is_valid = False
        self.invalid_code = -1  # for disassemble_req
        # 0 - payload
        # 2 - option
        # 1 || -1 - unknowed
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
            return int(0).to_bytes(1, "little", signed=False)

    def __disassemble_req(self):
        # obs1. s-a luat in considerare pentru aceasta aplicatie doar utilizarea a trei optiuni:
        # 8 - location-Path -> ascii encode
        # 12 - content-format -> ascii encode
        # 60 - Size1 -> ascii encoded
        # obs2. aceste trei optiuni nu au caracteristica de a fi repetabile => prezenta a
        # mai mult de trei optiuni indica o problema

        # is_valid = False daca:
        # delta, lungimea sau valoarea (duplicata) sunt malformate sau incorect ca format pentru o optiune
        # payload-ul este malformat sau incorect ca format

        self.version = bits_to_int(self.raw_request[0:2])
        self.type = bits_to_int(self.raw_request[2:4])
        self.tkn_length = bits_to_int(self.raw_request[4:8])
        self.code_class = bits_to_int(self.raw_request[8:11])
        self.code_details = bits_to_int(self.raw_request[11:16])
        self.msg_id = bits_to_int(self.raw_request[16:32])

        if self.code_class == 0 and self.code_details == 0:
            try:
                content = self.raw_request[32]
                self.is_valid = False
                self.invalid_reasons.append(
                    "__disassemble_req: 0.00-extra data: " + str(self.raw_request[32:]))
            except:
                self.is_valid = True
        else:
            # for token
            idx = 32
            # self.token = 0

            if self.tkn_length > 0:
                idx = (32 + self.tkn_length * 8)
                self.token = bits_to_int(self.raw_request[32:idx])

            # for options
            self.options = dict()
            prev_option_number = 0
            option_nr = 0

            while bits_to_int(self.raw_request[idx:idx + 8]) != int(0xFF) and option_nr < 3:
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
                    self.invalid_code = 2
                    raise Exception
                prev_option_number = option_number

                # option length
                option_length = bits_to_int(self.raw_request[idx + 4:idx + 8])

                try:
                    if option_length > 0:
                        if option_length < 13:
                            option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (
                                    ext_delta_bytes + option_length + 1) * 8]).tobytes().decode("utf-8")

                        elif option_length == 13:
                            option_length = bits_to_int(
                                self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (ext_delta_bytes + 2) * 8]) - 13
                            option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 2):idx + (
                                    ext_delta_bytes + option_length + 2) * 8]).tobytes().decode("utf-8")

                            ext_option_bytes = 1
                        elif option_length == 14:
                            option_length = bits_to_int(
                                self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (ext_delta_bytes + 3) * 8]) - 269
                            option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 3):idx + (
                                    ext_delta_bytes + option_length + 3) * 8]).tobytes().decode("utf-8")
                            ext_option_bytes = 2
                        else:
                            err = "__disassemble_req:option lenght incorect (teoretic 15, practic >=15): " + str(
                                option_length)
                            self.invalid_reasons.append(err)
                            self.invalid_code = 2
                            raise Exception

                        # add the option if it is not already added, or raise Exception if it is
                        if option_number in self.options.keys():
                            self.invalid_reasons.append(
                                "__disassemble_req:option value is duplicated " + str(option_value))
                            self.invalid_code = 2
                            raise Exception
                        self.options[option_number] = option_value
                    else:
                        self.invalid_reasons.append(
                            "__disassemble_req:option lenght incorect (teoretic 15, practic >=15): " + str(
                                option_length))
                        self.invalid_code = 2
                        raise Exception

                    idx = idx + (ext_delta_bytes + option_length + ext_option_bytes + 1) * 8
                    option_nr += 1
                except Exception as e:
                    self.invalid_reasons.append("__disassemble_req:" + str(e))
                    self.invalid_code = 1
                    raise e

            # for coap payload
            if bits_to_int(self.raw_request[idx:idx + 8]) == int(0xFF):
                try:
                    idx += 8
                    self.op_code = bits_to_int(self.raw_request[idx:idx + 4])
                    self.ord_no = bits_to_int(self.raw_request[idx + 4:idx + 20])
                    self.oper_param = (self.raw_request[idx + 20:]).tobytes().decode("utf-8")
                    # todo be carefull added for removing unknow aperance reason char
                    self.oper_param = self.oper_param[:len(self.oper_param) - 1]
                    self.is_valid = True
                except Exception as e:
                    self.invalid_reasons.append("__disassemble_req:" + str(e))
                    self.invalid_code = 0
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

        if self.code_class == 0 and self.code_details == 0:
            return result.tobytes()

        # token value
        if self.tkn_length > 0:
            result = self.__method(result, self.token, self.tkn_length, True)

        # options
        # options[idx][0] - option nr
        # options[idx][1] - option value
        prev_option_nr = 0

        for opt_no in sorted(self.options.keys()):

            if len(self.options[opt_no].encode('utf-8')) > 0:
                option_delta = opt_no - prev_option_nr
                prev_option_nr = opt_no

                if option_delta < 13:
                    result = self.__method(result, option_delta, 1, False)

                    if len(self.options[opt_no].encode('utf-8')) < 13:
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')), 1, False)

                    elif len(self.options[opt_no].encode('utf-8')) < 243:  # 256-13
                        result = self.__method(result, 13, 1, False)
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')) + 13, 1, True)

                    elif len(self.options[opt_no].encode('utf-8')) < 65266:  # 65535-269
                        result = self.__method(result, 14, 1, False)
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')) + 269, 2, True)
                    else:
                        err = "__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[opt_no].encode('utf-8')))
                        self.invalid_reasons.append(err)
                        raise Exception

                elif option_delta < 243:
                    result = self.__method(result, 13, 1, False)

                    if len(self.options[opt_no].encode('utf-8')) < 13:
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')), 1, False)
                        result = self.__method(result, option_delta + 13, 1, True)

                    elif len(self.options[opt_no].encode('utf-8')) < 243:  # 256-13
                        result = self.__method(result, 13, 1, False)
                        result = self.__method(result, option_delta + 13, 1, True)
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')) + 13, 1, True)

                    elif len(self.options[opt_no].encode('utf-8')) < 65266:  # 65535-269
                        result = self.__method(result, 14, 1, False)
                        result = self.__method(result, option_delta + 13, 1, True)
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')) + 269, 2, True)
                    else:
                        err = "__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[opt_no].encode('utf-8')))
                        self.invalid_reasons.append(err)
                        raise Exception

                elif option_delta < 65266:
                    result = self.__method(result, 14, 1, False)

                    if len(self.options[opt_no].encode('utf-8')) < 13:
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')), 1, False)
                        result = self.__method(result, option_delta + 269, 2, True)

                    elif len(self.options[opt_no].encode('utf-8')) < 243:  # 256-13
                        result = self.__method(result, 13, 1, False)
                        result = self.__method(result, option_delta + 269, 2, True)
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')) + 13, 1, True)

                    elif len(self.options[opt_no].encode('utf-8')) < 65266:  # 65535-269
                        result = self.__method(result, 14, 1, False)
                        result = self.__method(result, option_delta + 269, 2, True)
                        result = self.__method(result, len(self.options[opt_no].encode('utf-8')) + 269, 2, True)
                    else:
                        self.invalid_reasons.append("__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[opt_no].encode('utf-8'))))
                        raise Exception

                value = bitarray()
                bitarray.frombytes(value, self.options[opt_no].encode('utf-8'))
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
        bitarray.frombytes(value, self.oper_param)
        result += value

        self.is_valid = True

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
            if self.code_class == 0 and self.code_details == 0:
                return "version: " + str(
                    self.version) + \
                    "\ntype: " + str(self.type) + "\ntkn_length: " + str(self.tkn_length) + \
                    "\ncode_class: " + str(self.code_class) + "\ncode_details: " + str(self.code_details) + \
                    "\nmsg_id: " + str(self.msg_id)
            else:
                return "version: " + str(
                    self.version) + \
                    "\ntype: " + str(self.type) + "\ntkn_length: " + str(self.tkn_length) + \
                    "\ncode_class: " + str(self.code_class) + "\ncode_details: " + str(self.code_details) + \
                    "\nmsg_id: " + str(self.msg_id) + "\ntoken: " + str(self.token) + \
                    "\noptions: " + str(self.options) + "\nop_code: " + str(self.op_code) + \
                    "\nord_no: " + str(self.ord_no) + "\noper_param: " + str(self.oper_param)
        else:
            if len(self.invalid_reasons) != 0:
                return "Invalid message. Check reasons: " + str(self.invalid_reasons)
            else:
                return "Invalid message. Uncheck or unknown reason, check log file."


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
            new_response = Message(MsgType.Response)
            new_response.set_raw_data(data_rcv)
            print("\nDATA ===>\n", new_response, " \n<=== FROM: ", address)


def upload(file_path: str, upload_name: str, token):
    global msg_id
    if isfile(file_path):
        upload_msg = Message(MsgType.Request)
        upload_msg.version = 1
        upload_msg.type = Type.CON.value
        upload_msg.tkn_length = 5
        upload_msg.code_class = 0
        upload_msg.code_details = 3
        upload_msg.msg_id = 0
        upload_msg.token = token
        upload_msg.op_code = 0
        upload_msg.options[8] = upload_name  # location path
        upload_msg.options[12] = os.path.splitext(file_path)[1][1:]  # content format
        upload_msg.options[60] = str(os.stat(file_path).st_size)  # size1
        upload_msg.is_valid = True

        ord_no = 1
        max_value = 2 ** 16 - 1

        with open(file_path, 'rb') as f:
            seq = f.read(max_up_size - 3)  # - 3 (2 octeti pt ord_no_rule, 3 biti pentru op_code)
            while seq != b'':
                upload_msg.msg_id = msg_id
                upload_msg.ord_no = ord_no
                upload_msg.oper_param = seq

                data = upload_msg.get_raw_data()
                soc.sendto(data, (s_ip, int(s_port)))

                ord_no += 1
                if ord_no > max_value:
                    ord_no = 1
                seq = f.read(max_up_size - 3)  # read next sequence
                msg_id = msg_id + 1

            upload_msg.msg_id = msg_id
            upload_msg.ord_no = 0
            upload_msg.oper_param = b''
            msg_id = msg_id + 1

            data = upload_msg.get_raw_data()
            soc.sendto(data, (s_ip, int(s_port)))
            print(msg_id)
    else:
        print('fisierul nu exista')


def tester(test_nr: int):
    if test_nr == 0:
        ping = Message(MsgType.Request)
        ping.version = 1
        ping.type = Type.CON.value
        ping.tkn_length = 0
        ping.code_class = 0
        ping.code_details = 0
        ping.msg_id = 0
        ping.is_valid = True
        test = ping
    elif test_nr == 11:
        upload(r'C:\Users\admin\Documents\GitHub\proiect-echipa-1\CoAP_\Testing_module\Upload testing files\test.docx',
               'test.docx', 1)
    elif test_nr == 12:
        upload(r'C:\Users\admin\Documents\GitHub\proiect-echipa-1\CoAP_\Testing_module\Upload testing files\test.pdf',
               'test.pdf', 2)
    elif test_nr == 13:
        upload(r'C:\Users\admin\Documents\GitHub\proiect-echipa-1\CoAP_\Testing_module\Upload testing files\test.jpg',
               'test.jpg', 3)
    elif test_nr == 14:
        upload(r'C:\Users\admin\Documents\GitHub\proiect-echipa-1\CoAP_\Testing_module\Upload testing files\test.png',
               'test.png', 4)
    elif test_nr == 15:
        upload(r'C:\Users\admin\Documents\GitHub\proiect-echipa-1\CoAP_\Testing_module\Upload testing files\test.py',
               'file\\test.py', 5)
    elif test_nr == 16:
        upload(r'C:\Users\admin\Documents\GitHub\proiect-echipa-1\CoAP_\Testing_module\Upload testing files\test.txt',
               'test.txt', 6)
    elif test_nr == 17:
        upload(r'C:\Users\admin\Documents\GitHub\proiect-echipa-1\CoAP_\Testing_module\Upload testing files\test.wav',
               'test.wav', 7)
    elif test_nr == 2:
        pass
    elif test_nr == 3:
        move_file = Message(MsgType.Request)
        move_file.version = 1
        move_file.type = Type.CON.value
        move_file.tkn_length = 5
        move_file.code_class = 0
        move_file.code_details = 2
        move_file.msg_id = 0
        move_file.token = 20
        move_file.options = {8: "file\\test.py"}
        move_file.op_code = 2
        move_file.ord_no = 0
        move_file.oper_param = b'root'
        move_file.is_valid = True
        test = move_file
    elif test_nr == 4:
        delete_file = Message(MsgType.Request)
        delete_file.version = 1
        delete_file.type = Type.NON.value
        delete_file.tkn_length = 5
        delete_file.code_class = 0
        delete_file.code_details = 4
        delete_file.msg_id = 0
        delete_file.token = 20
        delete_file.options = {8: "test3.jpeg"}
        delete_file.op_code = 3
        delete_file.ord_no = 0
        delete_file.oper_param = b''
        delete_file.is_valid = True
        test = delete_file
    elif test_nr == 5:
        rename = Message(MsgType.Request)
        rename.version = 1
        rename.type = Type.NON.value
        rename.tkn_length = 5
        rename.code_class = 0
        rename.code_details = 5
        rename.msg_id = 0
        rename.token = 20
        rename.options = {8: "test2.png"}
        rename.op_code = 4
        rename.ord_no = 0
        rename.oper_param = b'test3.jpeg'
        rename.is_valid = True
        test = rename
    elif test_nr == 6:
        create_directory = Message(MsgType.Request)
        create_directory.version = 1
        create_directory.type = Type.CON.value
        create_directory.tkn_length = 5
        create_directory.code_class = 0
        create_directory.code_details = 3
        create_directory.msg_id = 0
        create_directory.token = 20
        create_directory.options = {8: "folder_nou/folder"}
        create_directory.op_code = 5
        create_directory.ord_no = 0
        create_directory.oper_param = ""
        create_directory.is_valid = True
        test = create_directory
    elif test_nr == 7:
        move_dir = Message(MsgType.Request)
        move_dir.version = 1
        move_dir.type = Type.CON.value
        move_dir.tkn_length = 5
        move_dir.code_class = 0
        move_dir.code_details = 2
        move_dir.msg_id = 0
        move_dir.token = 20
        move_dir.options = {8: "file2\\dir"}
        move_dir.op_code = 6
        move_dir.ord_no = 0
        move_dir.oper_param = b'root'
        move_dir.is_valid = True
        test = move_dir
    elif test_nr == 8:
        delete_dir = Message(MsgType.Request)
        delete_dir.version = 1
        delete_dir.type = Type.NON.value
        delete_dir.tkn_length = 5
        delete_dir.code_class = 0
        delete_dir.code_details = 4
        delete_dir.msg_id = 0
        delete_dir.token = 20
        delete_dir.options = {8: "file2"}
        delete_dir.op_code = 7
        delete_dir.ord_no = 0
        delete_dir.oper_param = b''
        delete_dir.is_valid = True
        test = delete_dir
    elif test_nr == 9:
        rename_dir = Message(MsgType.Request)
        rename_dir.version = 1
        rename_dir.type = Type.NON.value
        rename_dir.tkn_length = 5
        rename_dir.code_class = 0
        rename_dir.code_details = 5
        rename_dir.msg_id = 0
        rename_dir.token = 20
        rename_dir.options = {8: "file"}
        rename_dir.op_code = 8
        rename_dir.ord_no = 0
        rename_dir.oper_param = b'file2'
        rename_dir.is_valid = True
        test = rename_dir
    else:
        print("unknown number!")

    # ping_wrong = Message(MsgType.Request)
    # ping_wrong.version = 1
    # ping_wrong.type = Type.CON.value
    # ping_wrong.tkn_length = 5
    # ping_wrong.code_class = 0
    # ping_wrong.code_details = 0
    # ping_wrong.msg_id = 0
    # ping_wrong.token = 20
    # ping_wrong.options = {8:
    #                           "If you're visiting this page, you're likely here because you're searching for a random sentence. Sometimes a random word just isn't enough, and that is where the random sentence generator comes into play. By inputting the desired number, you can make a list of as many random sentences as you want or need. Producing random sentences can be helpful in a number of different ways.",
    #                       12: "cacaca", 60: "acadele de text"}
    # ping_wrong.op_code = 0
    # ping_wrong.ord_no = 0
    # ping_wrong.oper_param = "text in payload de test"
    # ping_wrong.is_valid = True
    # test = ping_wrong

    if 0 < test_nr < 10:
        data = test.get_raw_data()
        soc.sendto(data, (s_ip, int(s_port)))


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
        test_nr = input("Test_nr= ")
        tester(test_nr)
    except KeyboardInterrupt:
        running = False
        print("Waiting for the thread to close...")
        receive_thread.join()
        break
