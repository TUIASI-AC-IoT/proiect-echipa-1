import os
import shutil
from os import remove
from os.path import *

from message import Message
import general_use as gu


def delete_(msg: Message):
    src_name: str = msg.options[gu.OptionNumbers.LocationPath.value]
    if exists(src_name):
        if isdir(src_name):
            shutil.rmtree(src_name)
        else:
            remove(src_name)
        # TODO SEND RESPONSE -> SUCCESS
    else:
        pass
        # TODO SEND RESPONSE -> INVALID PATH


def rename_(msg: Message):
    src_name: str = get_normalized_path(msg.options[gu.OptionNumbers.LocationPath.value])
    src_path, src_f_name = split(src_name)

    new_name: str = get_normalized_path(msg.oper_param)
    if exists(src_name):
        # check new_name
        new_path, new_f_name = split(new_name)
        if new_f_name != '':
            if new_path == '':
                # am primit doar numele fisierului
                os.rename(src_name, join(src_path, new_f_name))
            elif new_path == src_path:
                # difera doar numele fisierului
                os.rename(src_name, new_name)
            else:
                # este invalid
                # TODO SEND RESPONSE -> invalid new_path
                pass
        else:
            # TODO SEND REPSONSE -> INVALID NEW_
            pass
    else:
        pass
        # TODO SEND RESPONSE -> INVALID PATH


def create_(msg: Message):
    fpath: str = msg.options[gu.OptionNumbers.LocationPath.value]
    # fpath -> nu trebuie sa existe
    # os.makedirs -> daca sirul nu se termina cu extensie de fisier
    # daca e fisier: os.makedirs + open(file) pt creare


def upload_(msg: Message):
    pass


def download_(msg: Message):
    pass


def get_normalized_path(path: str):
    return normpath(join(gu.ROOT, path))


def move_(msg: Message):
    # variabila care retine daca operatiunea s-a efectuat sau nu, folosind direct codurile de raspuns
    # si pe baza acesteia trimite raspunsul
    src_name: str = get_normalized_path(msg.options[gu.OptionNumbers.LocationPath.value])
    dest_name: str = get_normalized_path(msg.oper_param)
    if exists(src_name):
        if isdir(dest_name):
            shutil.move(src_name, dest_name)
            # TODO send response, success
        else:
            # TODO send response, not moved
            pass
    else:
        # TODO send response,the source file name is wrong
        pass
