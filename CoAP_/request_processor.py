from operations import *


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
        if msg.code_details == gu.MethodCodes.PUT.value:
            upload_(msg)
        else:
            download_(msg)
