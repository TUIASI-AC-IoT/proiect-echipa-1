import os
import shutil
from os import remove
from os.path import *

import general_use as gu
from message import Message, gen_msg_id


def get_normalized_path(path):
    if type(path) is bytes:
        path = path.decode('utf-8')
    return normpath(join(gu.ROOT, path))


def path_from_options(msg: Message):
    fpath = msg.options[gu.LocationPath]
    if msg.op_code <= 4 and not os.path.splitext(fpath)[1]:
        try:
            fpath += '.' + msg.options[gu.ContentFormat]
        except:
            pass
    return get_normalized_path(fpath)


def move_(msg: Message):
    src_name: str = path_from_options(msg)

    dest_name: str = get_normalized_path('' if msg.oper_param.decode('ascii') == 'root' else msg.oper_param)
    if exists(src_name):
        if isdir(dest_name):
            shutil.move(src_name, dest_name)
            gu.send_response(msg, gu.CHANGED)
            gu.log.info(f"move_({src_name}, {dest_name}) successful (msg_id: {msg.msg_id}, token:{msg.token})")
        else:
            gu.log.error(f"move_(): {dest_name} is not a directory (msg_id: {msg.msg_id}, token:{msg.token})")
    else:
        gu.send_response(msg, gu.NOT_FOUND)
        gu.log.error(f"move_(): {src_name} not found (msg_id: {msg.msg_id}, token:{msg.token})")


def delete_(msg: Message):
    src_name: str = path_from_options(msg)

    if exists(src_name):
        if isdir(src_name):
            shutil.rmtree(src_name)
        else:
            remove(src_name)
        gu.send_response(msg, gu.DELETED)
        gu.log.info(f"delete_({src_name}) successful (msg_id: {msg.msg_id}, token:{msg.token})")
    else:
        gu.send_response(msg, gu.NOT_FOUND)
        gu.log.info(f"delete_(): {src_name} not found (msg_id: {msg.msg_id}, token:{msg.token})")


def rename_(msg: Message):
    src_name: str = path_from_options(msg)
    src_path, src_f_name = split(src_name)

    new_name: str = get_normalized_path(msg.oper_param)
    if exists(src_name):
        if exists(new_name):
            gu.send_response(msg, gu.BAD_REQUEST)
            gu.log.error(
                f"rename_(): {new_name} already existent (msg_id: {msg.msg_id}, token:{msg.token})")
        else:
            # check new_name
            new_path, new_f_name = split(new_name)
            if new_f_name != '':
                if new_path == '':
                    # am primit doar numele fisierului
                    os.rename(src_name, join(src_path, new_f_name))
                    gu.send_response(msg, gu.CHANGED)
                    gu.log.info(f"rename_() successful (msg_id: {msg.msg_id}, token:{msg.token})")
                elif new_path == src_path:
                    # difera doar numele fisierului
                    os.rename(src_name, new_name)
                    gu.send_response(msg, gu.CHANGED)
                    gu.log.info(f"rename_() successful (msg_id: {msg.msg_id}, token:{msg.token})")
                else:
                    # invalid new_path -> 4.00
                    gu.send_response(msg, gu.BAD_REQUEST)
                    gu.log.error(
                        f"rename_(): {new_path} invalid or not existent (msg_id: {msg.msg_id}, token:{msg.token})")
            else:
                # INVALID NEW_F_NAME
                gu.send_response(msg, gu.BAD_REQUEST)
                gu.log.error(
                    f"rename_(): {new_f_name} invalid name (msg_id: {msg.msg_id}, token:{msg.token})")
    else:
        gu.send_response(msg, gu.BAD_OPTION)
        gu.log.error(
            f"rename_({src_name}, {new_name}): {src_name} not found"
            f" (msg_id: {msg.msg_id}, token:{msg.token})")


def create_(msg: Message):
    fpath: str = path_from_options(msg)
    if not exists(fpath):
        os.makedirs(fpath)
        gu.send_response(msg, gu.CREATED)
        gu.log.info(f"create_({fpath}) successful (msg_id: {msg.msg_id}, token:{msg.token})")
    else:
        # invalid, the path already exists -> 4.00
        gu.send_response(msg, gu.BAD_REQUEST)
        gu.log.error(f"create_():  {fpath} already exists (msg_id: {msg.msg_id}, token:{msg.token})")


def upload_(msg: Message):
    if msg.token not in gu.upload_collection:
        gu.upload_collection[msg.token] = gu.Content(path_from_options(msg), int(msg.options[gu.Size1]))
    if msg.ord_no != 0:
        gu.upload_collection[msg.token].add_packet(msg.ord_no, msg.oper_param)
    else:
        if gu.upload_collection[msg.token].is_valid():
            file_path = gu.upload_collection[msg.token].file_path
            with open(file_path, 'wb') as f:
                gu.upload_collection[msg.token].get_content().tofile(f)
            gu.send_response(msg, gu.CREATED)
            gu.log.info(f"upload_({file_path}) successfull (msg_id: {msg.msg_id}, token:{msg.token})")
            gu.upload_collection.pop(msg.token)
        else:
            gu.upload_collection.pop(msg.token)
            # gu.send_response(msg, gu.)
            gu.log.error(f"upload_() invalid collection (msg_id: {msg.msg_id}, token:{msg.token})")


def download_(msg: Message):
    file: str = path_from_options(msg)

    if isfile(file):
        msg_to_send: Message = msg.get_response_message(gu.CONTENT)
        msg_to_send.options[gu.Size1] = str(os.stat(file).st_size)
        ext = os.path.splitext(file)[1][1:]
        msg_to_send.options[gu.ContentFormat] = ext
        ord_no = 1
        max_value = 2 ** 16 - 1

        with open(file, 'rb') as f:
            seq = f.read(gu.max_up_size - 3)  # - 3 (2 octeti pt ord_no_rule, 3 biti pentru op_code)
            while seq != b'':
                msg_to_send.msg_id = gen_msg_id()
                msg_to_send.ord_no = ord_no
                msg_to_send.oper_param = seq

                msg_to_send.send_response()

                ord_no += 1
                if ord_no > max_value:
                    ord_no = 1
                seq = f.read(gu.max_up_size - 3)  # read next sequence

            msg_to_send.msg_id = gen_msg_id()
            msg_to_send.ord_no = 0
            msg_to_send.oper_param = b''

            msg_to_send.send_response()
    else:
        gu.send_response(msg, gu.NOT_FOUND)
        gu.log.error(f"dowload_():  {file} not found (msg_id: {msg.msg_id}, token:{msg.token})")


def request_processor(msg: Message):
    if msg.op_code == 0:
        upload_(msg)
    elif msg.op_code == 1:
        download_(msg)
    elif msg.op_code == 5:
        create_(msg)
    elif msg.op_code in [2, 6]:  # check MOVE function
        move_(msg)
    elif msg.op_code in [3, 7]:  # check if delete function
        delete_(msg)
    elif msg.op_code in [4, 8]:  # check if rename function
        rename_(msg)
