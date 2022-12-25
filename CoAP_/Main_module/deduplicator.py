import general_use as gu
from message import Message


def deduplicator(msg: Message) -> bool:
    # check if message id already exists in ReqQueue2

    if msg.msg_id not in gu.req_q2.get_msg_id_list():
        gu.req_q2.append(msg)
        return True
    else:
        pass
    return False
