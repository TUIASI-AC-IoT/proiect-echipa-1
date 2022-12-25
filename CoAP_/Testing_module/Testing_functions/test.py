import json

from Main_module import general_use as gu
from Main_module.message import Message
from Main_module.sintatic_analizer import sintatic_analizer


def create_req_message(msg: dict) -> Message:
    mes = Message(gu.MsgType.Request)

    mes.is_valid = True
    mes.version = msg['version']
    mes.type = msg['type']
    mes.tkn_length = msg['tkn_length']
    mes.code_class = msg['code_class']
    mes.code_details = msg['code_details']
    mes.msg_id = msg['msg_id']
    mes.token = msg['token']
    mes.options = {int(k): v for k, v in msg['options'].items()}
    mes.op_code = msg['op_code']
    mes.ord_no = msg['ord_no']
    mes.oper_param = msg['oper_param']
    return mes


def update_req_message(name, msg: dict):
    mes = test_msg[name]
    print(mes)
    for elem in msg:
        exec(f'mes.{elem}, msg[elem] = msg[elem], mes.{elem}')

    print('\tFormat valid:', sintatic_analizer(mes))

    print(mes)
    # undo
    for elem in msg:
        exec(f'mes.{elem}, msg[elem] = msg[elem], mes.{elem}')


test_msg = dict()

if __name__ == '__main__':
    f = open('reqMessagesTest.json')
    data = json.load(f)
    for var_name in data:
        print('\n\n' + var_name)
        for_testing = var_name[0:str(var_name).find('_')]
        if for_testing in test_msg:
            update_req_message(for_testing, data[var_name])
        else:
            test_msg[for_testing] = create_req_message(data[var_name])
            valid = sintatic_analizer(test_msg[for_testing])
            print('\tFormat valid:', valid)
