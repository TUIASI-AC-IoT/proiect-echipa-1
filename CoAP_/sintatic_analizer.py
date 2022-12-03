import general_use as gu
from message import Message


def check_type(msg: Message):
    return msg.type in [t.value for t in gu.Type]


# todo msg_type obligatoriu sa fie confirmable pentru UPLOAD, DOWNLOAD
def check_code(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        if msg.code_class == 0 and msg.code_details in [mc.value for mc in gu.MethodCodes]:
            return True
    else:
        if msg.code_class in gu.RESPONSE_CODES.keys():
            if msg.code_details in gu.RESPONSE_CODES[msg.code_class]:
                return True
    return False


def check_msg_id(msg: Message):
    return msg.msg_id is not None


def check_token_tkl(msg: Message):
    return (0 <= msg.tkn_length <= 8) and (msg.token is not None)


def check_options(msg: Message):
    for opt in msg.options:
        if opt not in [o.value for o in gu.OptionNumbers] or msg.options[opt] is None:
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
            if msg.code_details == gu.MethodCodes.PUT.value:
                result = bool(msg.oper_param)
            elif msg.code_details == gu.MethodCodes.GET.value:
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
