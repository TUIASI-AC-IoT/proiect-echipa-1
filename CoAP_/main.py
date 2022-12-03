import shutil
import socket
import sys
import threading
from enum import Enum, auto
from os.path import *
from threading import Lock
from typing import TypeAlias

import select
from bitarray import *
from numpy import floor

# py main.py --r_port=65415 --s_port=65416 --s_ip=192.168.0.103

# variabile diverse
Token: TypeAlias = int

# path of the server root files
ROOT = r''

max_up_size = 65507  # max udp payload size
running = False

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
class OptionNumbers(Enum):
    LocationPath = 8
    ContentFormat = 12
    Size1 = 60


total_nr_options = len(OptionNumbers)  # numarul total de optiuni posibile intr-un mesaj


class MsgList:
    def __init__(self):
        self.__list: list['Message'] = list()
        self.__lock = Lock()

    def append(self, obj) -> None:
        with self.__lock:
            self.__list.append(obj)

    def __getitem__(self, index):
        with self.__lock:
            return self.__list[index]

    def pop(self, index):
        with self.__lock:
            return self.__list.pop(index)

    # @property
    # def len(self):
    #     with self.__lock:
    #         return len(self.__list)

    def get_msg_id_list(self):
        with self.__lock:
            return [m.msg_id for m in self.__list]


req_q1 = MsgList()  # request queue1
req_q2 = MsgList()  # request queue2


# pentru trimiterea unui raspuns care va folosi metodele PUT, GET, ... se va seta mesajul ca
# fiind de tipul Requests
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


# contains the operations codes that is assigned to the method used for request

# operations_methods = {
#     MethodCodes.GET.value: [0],
#     MethodCodes.PUT.value: [0, 4],
#     MethodCodes.POST.value: [1, 5],
#     MethodCodes.DELETE.value: [2, 6]
# }


# clasa care contine pachetele si ordinea acestora
class Content:

    def __init__(self, file_path: str, file_type: str):
        self.file_path: str = file_path
        self.file_type: str = file_type
        self.__packets: dict[int, bytes] = dict()

    def is_valid(self):
        pck_ids = sorted(self.__packets)
        for i in range(1, len(pck_ids)):
            if pck_ids[i] - 1 != pck_ids[i - 1]:
                return False
        return True

    def get_content(self) -> bitarray:
        result = bitarray()
        if self.is_valid():
            for x in self.__packets.values():
                result.extend(x)
        return result

    def add_packet(self, pck_ord_no: int, pck_data: bytes):
        self.__packets[pck_ord_no] = pck_data


# clasa generica pentru mesajele coap specifice
class Message:
    def __init__(self, msg_type):
        self.oper_param: str
        self.ord_no: int
        self.op_code: int
        self.options: dict[int, str] = dict()
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

        self.options = dict()
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
                        self.options[option_number] = option_value
                    elif option_length == 13:
                        option_length = bits_to_int(
                            self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (ext_delta_bytes + 2) * 8]) - 13
                        option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 2):idx + (
                                ext_delta_bytes + option_length + 2) * 8]).tobytes().decode("utf-8")
                        self.options[option_number] = option_value
                        ext_option_bytes = 1
                    elif option_length == 14:
                        option_length = bits_to_int(
                            self.raw_request[idx + 8 * (ext_delta_bytes + 1):idx + (ext_delta_bytes + 3) * 8]) - 269
                        option_value = (self.raw_request[idx + 8 * (ext_delta_bytes + 3):idx + (
                                ext_delta_bytes + option_length + 3) * 8]).tobytes().decode("utf-8")
                        self.options[option_number] = option_value
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
                        self.invalid_reasons.append("__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[opt_no].encode('utf-8'))))
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
                        self.invalid_reasons.append("__assemble_resp: lungimea optiunii invalida: " + str(
                            len(self.options[opt_no].encode('utf-8'))))
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


# START ------ check functions for CoAP header ------ START
# TODO DE VERIFICAT DACA OPTIUNILE SUNT NECESARE PENTRU FUNCTIILE CARE SE DORESC A FI APELATE

def check_type(msg: Message):
    return msg.type in [t.value for t in Type]


def check_code(msg: Message):
    if msg.msg_type == MsgType.Request:
        if msg.code_class == 0 and msg.code_details in [mc.value for mc in MethodCodes]:
            return True
    else:
        if msg.code_class in RESPONSE_CODES.keys():
            if msg.code_details in RESPONSE_CODES[msg.code_class]:
                return True
    return False


def check_msg_id(msg: Message):
    return msg.msg_id is not None


def check_token_tkl(msg: Message):
    return (0 <= msg.tkn_length <= 8) and (msg.token is not None)


def check_options(msg: Message):
    for opt in msg.options:
        if opt not in [o.value for o in OptionNumbers] or msg.options[opt] is None:
            return False
    return True


# todo + pentru fiecare code, metoda(PUT, GET, POST, DELETE) corespunde cu op_code-ul mesajului
# todo - optiuni obligatorii pt op_code
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


# TODO END
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
    if msg.msg_id not in req_q2.get_msg_id_list():
        req_q2.append(msg)
        return True
    else:
        pass  # todo eventual log
    return False


""" 

def gen_token():
    #TODO
    PASS
    
def gen_msg_id():
    #todo
    pass

"""


def service_th1_fct():
    running_th1 = True
    while running_th1:
        try:
            msg: Message = req_q1.pop(0)
            if sintatic_analizer(msg):
                if deduplicator(msg):
                    # todo awake thread 2
                    pass
        except IndexError:
            running_th1 = False


def service_th2_fct():
    running_th2 = True
    while running_th2:
        try:
            msg: Message = req_q2.pop(0)
            # TODO call request_processor
            request_processor(msg)
        except IndexError:
            running_th2 = False


def get_normalized_path(path: str):
    return normpath(join(ROOT, path))


def move_(msg: Message):
    # variabila care retine daca operatiunea s-a efectuat sau nu, folosind direct codurile de raspuns
    # si pe baza acesteia trimite raspunsul
    src_name: str = get_normalized_path(msg.options[OptionNumbers.LocationPath.value])
    dest_name: str = get_normalized_path(msg.oper_param)
    if exists(src_name):
        # 2 optiuni:    - fie este obligatoriu ca dest_name sa existe
        #               - fie se creeaza folder-ul daca nu exista
        # conditie: dest_name trebuie sa fie director
        if isdir(dest_name):
            shutil.move(src_name, dest_name)
            # TODO send response, success
        else:
            # TODO send response, not moved
            pass
    else:
        # TODO send response,the source file name is wrong
        pass


def delete_(msg: Message):
    src_name: str = msg.options[OptionNumbers.LocationPath.value]
    # shutil.rmtree -> for directories
    #  os.remove -> for files


def rename_(msg: Message):
    src_name: str = get_normalized_path(msg.options[OptionNumbers.LocationPath.value])
    new_name: str = msg.oper_param
    # os.rename
    # new_name  -> fie e toata calea si numele e schimbat
    #           -> fie e doar numele nou


def create_(msg: Message):
    fpath: str = msg.options[OptionNumbers.LocationPath.value]
    # fpath -> nu trebuie sa existe
    # os.makedirs -> daca sirul nu se termina cu extensie de fisier
    # daca e fisier: os.makedirs + open(file) pt creare


def upload_(msg: Message):
    pass


def download_(msg: Message):
    pass


def request_processor(msg: Message):
    if msg.op_code in [1, 5]:  # check MOVE function
        move_(msg)
    elif msg.op_code in [2, 6]:  # check if delete function
        delete_(msg)
    elif msg.op_code in [3, 7]:  # check if rename function
        rename_(msg)
    elif msg.op_code == 4:  # check if create function
        create_(msg)
    elif msg.op_code == 0:
        # TODO de reverificat daca e garantat acest lucru
        if msg.code_details == MethodCodes.PUT.value:
            upload_(msg)
        else:
            download_(msg)


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
