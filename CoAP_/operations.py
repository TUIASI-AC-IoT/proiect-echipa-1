import shutil
from os.path import *

from message import Message
import general_use as gu


def delete_(msg: Message):
    src_name: str = msg.options[gu.OptionNumbers.LocationPath.value]
    # shutil.rmtree -> for directories
    #  os.remove -> for files


def rename_(msg: Message):
    src_name: str = get_normalized_path(msg.options[gu.OptionNumbers.LocationPath.value])
    new_name: str = msg.oper_param
    # os.rename
    # new_name  -> fie e toata calea si numele e schimbat
    #           -> fie e doar numele nou


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
        # 2 optiuni:    - fie este obligatoriu ca dest_name sa existe
        #               - fie se creeaza folder-ul daca nu exista
        # conditie: dest_name trebuie sa fie director
        if isdir(dest_name):
            shutil.move(src_name, dest_name)
            # TODO send response, success
        else:
            # TODO send response, not moved
            pass
    else:
        # TODO send response,the source file name is wrong
        pass
