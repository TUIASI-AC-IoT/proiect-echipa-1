from bitarray import *


# clasa care contine pachetele si ordinea acestora
class Content:

    def __init__(self, file_path: str, file_type: str):
        self.file_path: str = file_path
        self.file_type: str = file_type
        self.__packets: dict[int, bytes] = dict()

    def is_valid(self):
        pck_ids = sorted(self.__packets)
        for i in range(1, len(pck_ids)):
            if pck_ids[i] - 1 != pck_ids[i - 1]:
                return False
        return True

    def get_content(self) -> bitarray:
        result = bitarray()
        if self.is_valid():
            for x in self.__packets.values():
                result.extend(x)
        return result

    def add_packet(self, pck_ord_no: int, pck_data: bytes):
        self.__packets[pck_ord_no] = pck_data
