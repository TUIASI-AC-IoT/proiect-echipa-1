from bitarray import *


# clasa care contine pachetele (componente ale unui fisier) si ordinea acestora
# todo -> check ord_no = 0, means endof transmission
class Content:

    def __init__(self, file_path: str, size: int):
        self.file_path: str = file_path
        self.theoretical_size: int = size
        self.__packets: dict[int, bytes] = dict()
        self.content_size: int = 0

    def is_valid(self):
        pck_ids = sorted(self.__packets)
        for i in range(1, len(pck_ids)):
            if pck_ids[i] - 1 != pck_ids[i - 1]:
                return False
        return True and self.is_compl_recv()

    def get_content(self) -> bitarray:
        result = bitarray()
        if self.is_valid():
            for x in self.__packets.values():
                bitarray.frombytes(result, x)
        return result

    def add_packet(self, pck_ord_no: int, pck_data: bytes):
        self.content_size += len(pck_data)
        self.__packets[pck_ord_no] = pck_data
        print(self.content_size, self.theoretical_size)

    def is_compl_recv(self):
        return self.content_size == self.theoretical_size
