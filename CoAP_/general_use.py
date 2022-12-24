import logging
import logging as log
from enum import Enum, auto
from threading import Lock

from content import Content
from message import Message

# variabile diverse
Token = int
ROOT = r''  # path of the server root files
max_up_size = 65507  # max udp payload size
first_run_msg_id = True
msg_id_file = None
last_msg_id = int
token_file = None
first_run_token = True
last_tokens = []
running = False
log.basicConfig(filename="log.txt", filemode="a", level=logging.INFO,
                format='%(asctime)s :: %(levelname)-8s :: %(message)s')

upload_collection: dict[Token, Content] = dict()

# GET = 1, POST = 2, PUT = 3, DELETE = 4, JOMAG4 = 5
GET, POST, PUT, DELETE, JOMAG4 = 1, 2, 3, 4, 5
MethodCodes = [GET, POST, PUT, DELETE, JOMAG4]

# 2.01 = Created, 2.02 = Deleted, 2.04 = Changed, 2.05 = Content
# 4.00 = Bad Request, 4.02 = Bad Option, 4.04 = Not Found
# 5.00 = Internal Server Error
MESSAGE_CODES = {
    2: [1, 2, 4, 5],
    4: [0, 2, 4],
    5: [0]
}

# 8 = Location-Path, 12 = Content-Format, 60 = Size1
LocationPath, ContentFormat, Size1 = 8, 12, 60
OptionNumbers = [LocationPath, ContentFormat, Size1]

total_nr_options = len(OptionNumbers)  # numarul total de optiuni posibile intr-un mesaj


class MsgList:
    def __init__(self):
        self.__list: list[Message] = list()
        self.__lock = Lock()

    def append(self, obj) -> None:
        with self.__lock:
            self.__list.append(obj)

    def __getitem__(self, index):
        with self.__lock:
            return self.__list[index]

    def pop(self, index):
        with self.__lock:
            return self.__list.pop(index)

    # @property
    # def len(self):
    #     with self.__lock:
    #         return len(self.__list)

    def get_msg_id_list(self):
        with self.__lock:
            return [m.msg_id for m in self.__list]


req_q1 = MsgList()  # request queue1
req_q2 = MsgList()  # request queue2


class MsgType(Enum):
    Request = auto()
    Response = auto()


class Type(Enum):
    CON = 0
    NON = 1
    ACK = 2
    RESET = 3
