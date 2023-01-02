import json
import general_use as gu
from message import Message
from sintatic_analizer import sintatic_analizer


def create_message(msg: dict, msg_type) -> Message:
    mes = Message(msg_type)

    mes.is_valid = True
    try:
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
    except KeyError or Exception:
        pass

    return mes


def alternate_message(name, msg: dict):
    mes = test_msg[name]
    for elem in msg:
        print(f'\tnew_{elem} = {msg[elem]}')
        exec(f'mes.{elem}, msg[elem] = msg[elem], mes.{elem}')

    print('\tFormat valid:', sintatic_analizer(mes))

    # undo
    for elem in msg:
        exec(f'mes.{elem}, msg[elem] = msg[elem], mes.{elem}')


test_msg = dict()


def test(data: dict, msg_type):
    for var_name in data:
        print('\n' + var_name)
        for_testing = var_name[0:str(var_name).find('_')]
        if for_testing in test_msg:
            alternate_message(for_testing, data[var_name])
        else:
            test_msg[for_testing] = create_message(data[var_name], msg_type)
            valid = sintatic_analizer(test_msg[for_testing])
            print('\tFormat valid:', valid)


if __name__ == '__main__':
    f = open('reqMessagesTest.json')
    f2 = open('sndMessagesTest.json')
    print('Requests TESTING')
    test(json.load(f), gu.MsgType.Request)

    print('\n\nResponse TESTING')
    test(json.load(f2), gu.MsgType.Response)
