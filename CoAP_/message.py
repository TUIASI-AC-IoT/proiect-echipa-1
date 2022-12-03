from bitarray import *
from numpy import floor

from main import send_response
import general_use as gu


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
            return self.__assemble_resp()
        except:
            return int(0).to_bytes(1, "little", signed=False)

    def send_response(self):
        if self.is_valid:
            send_response(self)

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

        while bits_to_int(self.raw_request[idx:idx + 8]) != int(0xFF) and option_nr < gu.total_nr_options:
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


def int_to_bytes(value, length):
    return int(value).to_bytes(byteorder="big", signed=False, length=length)


def bits_to_int(value):
    if len(value) % 8 != 0:
        value = bitarray("0" * (int(floor((len(value) / 8) + 1) * 8) - len(value))) + value
    return int.from_bytes(value.tobytes(), "big")


def str_to_list(str_param: str):
    params = str_param.split(",")
    result = []
    for elem in params:
        result.append(int(elem))
    return result


def find_idx(len_to_search):
    for idx in range(len(gu.last_tokens)):
        if gu.last_tokens[idx][0] == len_to_search:
            return idx

    return -1


def lists_to_str():
    result = list()
    for _list in gu.last_tokens:
        result.append(str(_list[0]) + "," + str(_list[1]))

    return result


def gen_token(tkn_length_in_bits):
    if gu.first_run_token:
        with open("token.txt", "r") as f:
            result_list = f.read().splitlines()
            gu.token_file = f
            gu.token_file.close()
        for idx in range(len(result_list)):
            gu.last_tokens.append(str_to_list(result_list[idx]))
        gu.first_run_token = False

    _idx = find_idx(tkn_length_in_bits)
    if _idx > -1:
        if gu.last_tokens[_idx][1] < pow(2, tkn_length_in_bits) - 1:
            result = gu.last_tokens[_idx][1] + 1
        else:
            result = 0
    else:
        result = 0

    gu.token_file = open("token.txt", 'w')
    gu.token_file.close()
    gu.token_file = open("token.txt", 'a')
    if _idx == -1:
        gu.last_tokens.append([tkn_length_in_bits, result])
    else:
        gu.last_tokens[_idx][1] = result
    for line in lists_to_str():
        gu.token_file.write(line + "\n")
    gu.token_file.close()

    return result


def gen_msg_id():
    if gu.first_run_msg_id:
        gu.msg_id_file = open("msg_id.txt", "r", encoding='utf-16')
        gu.last_msg_id = int(gu.msg_id_file.read())
        gu.first_run_msg_id = False
        gu.msg_id_file.close()

    if gu.last_msg_id < pow(2, 16) - 1:
        gu.last_msg_id += 1
    else:
        gu.last_msg_id = 0

    gu.msg_id_file = open("msg_id.txt", 'w', encoding='utf-16')
    gu.msg_id_file.close()
    gu.msg_id_file = open("msg_id.txt", 'a', encoding='utf-16')
    gu.msg_id_file.write(str(gu.last_msg_id))
    gu.msg_id_file.close()

    return gu.last_msg_id