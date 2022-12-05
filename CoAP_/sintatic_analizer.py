import general_use as gu
from message import Message


def check_msg_type(msg: Message):
    return type(msg.msg_type) is gu.MsgType


def check_type(msg: Message):
    return msg.type in [t.value for t in gu.Type]


def check_msg_id(msg: Message):
    return msg.msg_id is not None


def check_token_tkl(msg: Message):
    if msg.tkn_length == 0:
        return msg.token is None
    elif 0 < msg.tkn_length <= 8:
        return msg.token is not None
    return False


def check_code(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        if msg.code_class == 0 and msg.code_details in gu.MESSAGE_CODES[0]:
            return True
    else:
        if msg.code_class in gu.MESSAGE_CODES.keys():
            if msg.code_details in gu.MESSAGE_CODES[msg.code_class]:
                return True
    return False


def check_options(msg: Message):
    for opt in msg.options:
        if opt not in [o.value for o in gu.OptionNumbers] or msg.options[opt] is None:
            return False
    return True


def check_op_code(msg: Message):
    return 0 <= msg.op_code <= 7


def check_ord_no(msg: Message):
    if 1 <= msg.op_code <= 7:
        return msg.ord_no == 0
    elif msg.op_code == 0:
        val1: int
        val2: int
        if msg.code_class == 0:
            if msg.msg_type == gu.MsgType.Request:
                val1 = gu.MethodCodes.GET.value
                val2 = gu.MethodCodes.PUT.value
            else:
                val1 = gu.MethodCodes.PUT.value
                val2 = gu.MethodCodes.GET.value

            if msg.code_details == val1:
                return msg.ord_no == 0
            elif msg.code_details == val2:
                return msg.ord_no >= 0
    return False


def check_oper_param(msg: Message):
    if msg.msg_type == gu.MsgType.Request:
        if msg.op_code == 0:
            if msg.code_details == gu.MethodCodes.GET.value:
                return not msg.oper_param
            elif msg.code_details == gu.MethodCodes.PUT.value:
                return bool(msg.oper_param)
        elif msg.op_code in [2, 4, 6]:
            return not msg.oper_param
        else:
            return bool(msg.oper_param)
    else:
        if msg.op_code == 0:
            if msg.code_class == 0:
                if msg.code_details == gu.MethodCodes.PUT.value:
                    return not msg.oper_param
                elif msg.code_details == gu.MethodCodes.GET.value:
                    return bool(msg.oper_param)
        else:
            return not msg.oper_param
    return False


def check_mandatory_options(msg: Message):
    if msg.op_code == 0:
        if msg.code_class == 0:
            if msg.msg_type == gu.MsgType.Request:
                val = gu.MethodCodes.PUT.value
            else:
                val = gu.MethodCodes.GET.value
            if msg.code_details == val:
                return all(x.value in msg.options for x in gu.OptionNumbers)
    else:
        if msg.op_code <= 3:
            result = len(msg.options) == 2
            result = result and gu.OptionNumbers.LocationPath.value in msg.options
            result = result and gu.OptionNumbers.ContentFormat.value in msg.options
        else:
            result = len(msg.options) == 1
            result = result and gu.OptionNumbers.LocationPath.value in msg.options
        return result
    return False


# END ------ check functions for CoAP header ------ END

# functions that check the header without the payload part
check_functions = [
    [check_type, check_code, check_msg_id, check_token_tkl, check_options],  # part1 without payload
    [check_op_code, check_ord_no, check_oper_param]  # payload part
]


def sintatic_analizer(msg: Message) -> bool:
    valid: bool = msg.is_valid and check_msg_type(msg)
    if valid:
        # messages with version number not equal to 1 MUST be silently ignored
        if msg.version == 1:
            # todo check if message is empty or reset message
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
                    if check_mandatory_options(msg):
                        # todo send ACK
                        pass
                    else:
                        # todo send RST
                        pass
        else:
            valid = False

    return valid
