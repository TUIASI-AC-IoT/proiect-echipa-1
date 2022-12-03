from deduplicator import deduplicator
import general_use as gu
from message import Message
from sintatic_analizer import sintatic_analizer


def service_th1_fct():
    running_th1 = True
    while running_th1:
        try:
            msg: Message = gu.req_q1.pop(0)
            if sintatic_analizer(msg):
                if deduplicator(msg):
                    # todo awake thread 2
                    pass
        except IndexError:
            running_th1 = False
