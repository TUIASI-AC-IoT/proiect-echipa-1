import os
import shutil
from os import remove
from os.path import *

import general_use as gu
from message import Message, gen_msg_id


def get_normalized_path(path: str):
    return normpath(join(gu.ROOT, path))


# todo -> pg 92 coap -> codificare media type?
def path_from_options(msg: Message):
    fpath = msg.options[gu.LocationPath]
    if msg.op_code <= 4:
        fpath += '.' + msg.options[gu.ContentFormat]
    return get_normalized_path(fpath)


def move_(msg: Message):
    src_name: str = path_from_options(msg)
    dest_name: str = get_normalized_path(msg.oper_param)
    if exists(src_name):
        if isdir(dest_name):
            shutil.move(src_name, dest_name)
            gu.send_response(msg, 2, 4)
        else:
            gu.log.error(f'{dest_name} is not a directory')
    else:
        gu.log.error(f'{src_name} non-existent')
        gu.send_response(msg, 4, 4)


def delete_(msg: Message):
    src_name: str = path_from_options(msg)

    if exists(src_name):
        if isdir(src_name):
            shutil.rmtree(src_name)
        else:
            remove(src_name)
        gu.send_response(msg, 2, 2)
    else:
        gu.send_response(msg, 4, 4)


def rename_(msg: Message):
    src_name: str = path_from_options(msg)
    src_path, src_f_name = split(src_name)

    new_name: str = get_normalized_path(msg.oper_param)
    if exists(src_name):
        # check new_name
        new_path, new_f_name = split(new_name)
        if new_f_name != '':
            if new_path == '':
                # am primit doar numele fisierului
                os.rename(src_name, join(src_path, new_f_name))
                gu.send_response(msg, 2, 4)
            elif new_path == src_path:
                # difera doar numele fisierului
                os.rename(src_name, new_name)
                gu.send_response(msg, 2, 4)
            else:
                # este invalid
                # TODO SEND RESPONSE -> invalid new_path -> 4.00?
                gu.send_response(msg, 4, 0)
        else:
            # TODO SEND REPSONSE -> INVALID NEW_F_NAME -> 4.00?
            gu.send_response(msg, 4, 0)
    else:
        # TODO SEND RESPONSE -> INVALID SOURCE PATH -> 4.00?
        gu.send_response(msg, 4, 0)


def create_(msg: Message):
    fpath: str = path_from_options(msg)
    if not exists(fpath):
        os.makedirs(fpath)
        # todo send response -> 2.01
        gu.send_response(msg, 2, 1)
    else:
        # the path exists
        # TODO SEND RESPONSE -> INVALID PATH, ALREADY EXISTS -> 4.00?
        gu.send_response(msg, 4, 0)


# todo check when received last packet(0 as ord_no)
def upload_(msg: Message):
    if msg.token not in gu.upload_collection:
        gu.upload_collection[msg.token] = gu.Content(path_from_options(msg), int(msg.options[gu.Size1]))
    if msg.ord_no != 0:
        gu.upload_collection[msg.token].add_packet(msg.ord_no, bytes(msg.oper_param))
    else:
        if gu.upload_collection[msg.token].is_valid():
            file = gu.ROOT + gu.upload_collection[msg.token].file_path
            with open(file, 'wb') as f:
                gu.upload_collection[msg.token].get_content().tofile(f)
            gu.send_response(msg, 2, 1)


def download_(msg: Message):
    file: str = path_from_options(msg)

    if isfile(file):
        msg_to_send: Message = msg.get_response_message(2, 5)
        msg_to_send.options[gu.Size1] = str(os.stat(file).st_size)
        msg_to_send.options[gu.ContentFormat] = msg.options[gu.ContentFormat]
        ord_no = 1
        max_value = 2 ** 16 - 1

        with open(file, 'r') as f:
            seq = f.read(gu.max_up_size - 3)  # - 3 (2 octeti pt ord_no_rule, 3 biti pentru op_code)
            while seq != '':
                msg_to_send.msg_id = gen_msg_id()
                msg_to_send.ord_no = ord_no
                msg_to_send.oper_param = seq

                msg.send_response()

                ord_no += 1
                if ord_no > max_value:
                    ord_no = 1
                seq = f.read(gu.max_up_size - 3)  # read next sequence

            msg_to_send.msg_id = gen_msg_id()
            msg_to_send.ord_no = 0
            msg_to_send.oper_param = ''

            msg.send_response()
    else:
        # TODO send 'not a file' RESPONSE
        gu.send_response(msg, 4, 0)
        pass


def request_processor(msg: Message):
    if msg.op_code == 0:
        upload_(msg)
    elif msg.op_code == 1:
        download_(msg)
    elif msg.op_code in [2, 6]:  # check MOVE function
        move_(msg)
    elif msg.op_code in [3, 7]:  # check if delete function
        delete_(msg)
    elif msg.op_code in [4, 8]:  # check if rename function
        rename_(msg)