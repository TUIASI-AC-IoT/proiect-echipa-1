import general_use as gu
from message import Message


def check_type(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        return msg.type in [gu.Type.CON.value, gu.Type.NON.value]
    else:
        return msg.type in [gu.Type.ACK.value, gu.Type.NON.value]


def check_tkl(msg: Message):
    return 0 <= msg.tkn_length <= 8


def check_code(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        return msg.code_class == 0 and msg.code_details in gu.MethodCodes
    elif msg.code_class in gu.MESSAGE_CODES.keys():
        return msg.code_details in gu.MESSAGE_CODES[msg.code_class]
    return False


def check_msg_id(msg: Message):
    return msg.msg_id is not None


def check_token(msg: Message):
    if msg.tkn_length == 0:
        return not bool(msg.token)
    else:
        return msg.token is not None


def check_options(msg: Message):
    for opt in msg.options:
        if opt not in gu.OptionNumbers or msg.options[opt] is None:
            return False
    return True


# payload part
def check_op_code(msg: Message):
    return 0 <= msg.op_code <= 8


def check_ordno_operp(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        if msg.op_code == 0:
            return (msg.ord_no == 0 and (not bool(msg.oper_param))) or \
                   (msg.ord_no > 0 and bool(msg.oper_param))
        else:
            val = (msg.ord_no == 0)
            if val:
                if msg.op_code in range(1, 8, 2):  # start, end, step
                    val = val and (not bool(msg.oper_param))
                else:
                    val = val and bool(msg.oper_param)
            return val
    else:
        if msg.op_code == 1:
            return (msg.ord_no == 0 and (not bool(msg.oper_param))) or \
                   (msg.ord_no > 0 and bool(msg.oper_param))
        else:
            return msg.ord_no == 0 and (not bool(msg.oper_param))


def check_method(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        if msg.op_code in [0, 5]:
            return msg.code_details == gu.PUT
        if msg.op_code in [2, 6]:
            return msg.code_details == gu.POST
        if msg.op_code in [3, 7]:
            return msg.code_details == gu.DELETE
        if msg.op_code in [4, 8]:
            return msg.code_details == gu.JOMAG4
        if msg.op_code == 1:
            return msg.code_details == gu.GET
    else:
        value: bool = msg.code_class == 2
        # daca e de raspuns de succes, atunci trebuie sa respecte un anumit code_details
        if value:
            if msg.code_details == 3:
                return True
            if msg.op_code in [0, 5]:
                return msg.code_details == 1
            elif msg.op_code in [2, 4, 6, 8]:
                return msg.code_details == 4
            elif msg.op_code in [3, 7]:
                return msg.code_details == 2
            else:
                return msg.code_details == 5
        else:
            # este raspuns de eroare, iar verificarea este satisfacuta deja
            return True


def verify_options_and_length(options: dict, man_opt: list):
    return len(options) == len(man_opt) and all(x in options for x in man_opt)


def check_mandatory_options(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        if msg.op_code == 0:
            return verify_options_and_length(msg.options, [8, 12, 60])
        else:
            return verify_options_and_length(msg.options, [8])
    else:
        if msg.op_code == 1:
            return verify_options_and_length(msg.options, [12, 60])
        else:
            return not bool(msg.options)


def check_mandatory_type(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        if msg.op_code == 0:
            return msg.type == gu.Type.CON.value
    return True


# functions that check the header without the payload part
check_functions = [
    [check_type, check_tkl, check_code, check_msg_id, check_token, check_options],  # part1 without payload
    [check_op_code, check_ordno_operp],  # payload part
    [check_method, check_mandatory_options, check_mandatory_type]  # mandatory functions
]


def sintatic_analizer(msg: Message) -> bool:
    valid: bool = msg.is_valid and (msg.msg_type in gu.MsgType)
    if valid:
        # messages with version number not equal to 1 MUST be silently ignored
        if msg.version == 1:
            # check if message is empty message
            if msg.code_class == 0 and msg.code_details == 0:
                value = any(map(bool, [msg.token, msg.options, msg.op_code, msg.ord_no, msg.oper_param]))
                if not value and msg.tkn_length == 0 and msg.type in [0, 2, 3]:  # 0-con, 2-ack, 3-rst
                    gu.send_rst_response(msg, gu.Type.RESET.value)
                else:
                    pass
                return False
            else:
                def get_valid(message, fun_list):
                    for f in fun_list:
                        if not f(message):
                            return False
                    return True

                # if the CoAP format is invalid
                if not get_valid(msg, check_functions[0]):
                    gu.send_rst_response(msg, gu.Type.RESET.value)
                    valid = False
                else:
                    # check the payload format
                    if get_valid(msg, check_functions[1]):
                        if get_valid(msg, check_functions[2]):  # check mandatory things
                            gu.log.info(f'sintactic_analizer() sucessfull (msg_id: {msg.msg_id}, token:{msg.token})')
                            gu.send_response(msg, gu.VALID, gu.Type.ACK.value)
                        else:
                            gu.log.error(f'sintactic_analizer(): invalid payload - mandatory things '
                                         f'(msg_id: {msg.msg_id}, token:{msg.token})')
                            gu.send_rst_response(msg, gu.Type.RESET.value)
                            valid = False
                    else:
                        gu.log.error(f'sintactic_analizer(): invalid payload'
                                     f'(msg_id: {msg.msg_id}, token:{msg.token})')
                        gu.send_response(msg, gu.BAD_REQUEST)
                        valid = False
        else:
            valid = False
            gu.log.error(f'sintactic_analizer(): invalid message version'
                         f'(msg_id: {msg.msg_id}, token:{msg.token})')
    else:
        if msg.invalid_code == 0:
            gu.send_response(msg, gu.BAD_REQUEST)
        elif msg.invalid_code == 2:
            gu.send_response(msg, gu.BAD_OPTION)
    return valid
