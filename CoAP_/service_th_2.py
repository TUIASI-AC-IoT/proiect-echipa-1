import general_use as gu
from message import Message
from request_processor import request_processor


def service_th2_fct():
    running_th2 = True
    while running_th2:
        try:
            msg: Message = gu.req_q2.pop(0)
            # TODO call request_processor
            request_processor(msg)
        except IndexError:
            running_th2 = False
