import socket
import sys
import select
import threading
from queue import *
from bitarray import *
from numpy import floor

#py main.py --r_port=65415 --s_port=65416 --s_ip=192.168.0.103
#from bitstring import * #posibil de ajutor

# variabile diverse
max_up_size = 1024  #max udp payload size
running = False
req_q1 = Queue(0)  #request queue1
req_q2 = Queue(0)  #request queue2
#todo check if need prior queue
upload_collection =[[[]]]  #todo


class Request:
    def __init__(self, raw_request):
        self.oper_param = int
        self.ord_no = int
        self.op_code = int
        self.options = None
        self.token = int
        self.msg_id = int
        self.code_details = int
        self.code_class = int
        self.tkn_length = int
        self.type = int
        self.version = int
        self.raw_request = bitarray()
        self.is_valid = False
        bitarray.frombytes(self.raw_request, raw_request)
        self.disassemble_req()

    def disassemble_req(self):
        #obs1. s-a luat in considerare pentru aceasta aplicatie doar utilizarea a doua optiuni:
        #8 - location-Path -> ascii encode
        #12 - content-format -> ascii encode
        #obs2. aceste doua optiuni nu au caracteristica de a fi repetabile => prezenta a mai mult de doua optiuni indica o problema

        self.version = bits_to_int(self.raw_request[0:2])
        self.type = bits_to_int(self.raw_request[2:4])
        self.tkn_length = bits_to_int(self.raw_request[4:8])
        self.code_class = bits_to_int(self.raw_request[8:11])
        self.code_details = bits_to_int(self.raw_request[11:16])
        self.msg_id = bits_to_int(self.raw_request[16:32])

        idx = 32
        self.token = 0

        if self.tkn_length > 0:
            idx = (32 + self.tkn_length * 8)
            self.token = bits_to_int(self.raw_request[32:idx])

        self.options = [[]]
        self.options.remove([])
        prev_option_number = 0
        option_nr = 0

        while bits_to_int(self.raw_request[idx:idx + 8]) != int(0xFF) and option_nr < 2:
            option_number = bits_to_int(self.raw_request[idx:idx + 4]) + prev_option_number
            prev_option_number = option_number
            option_length = bits_to_int(self.raw_request[idx + 4:idx + 8])
            option_value = (self.raw_request[idx + 8:idx + (option_length + 1) * 8]).tobytes().decode("utf-8")
            self.options.append([option_number, option_value])
            idx = idx + (option_length + 1) * 8
            option_nr += 1

        if bits_to_int(self.raw_request[idx:idx + 8]) == int(0xFF):
            self.is_valid=True
            idx += 8
            self.op_code = bits_to_int(self.raw_request[idx:idx + 3])
            self.ord_no = bits_to_int(self.raw_request[idx + 3:idx + 19])
            self.oper_param = bits_to_int(self.raw_request[idx + 19:])

    def __repr__(self):
        if self.is_valid:
            return "raw_req: "+str(self.raw_request).replace("bitarray('","").replace("')","")+"\nversion: "+str(self.version)+\
               "\ntype: "+str(self.type)+"\ntkn_length: "+str(self.tkn_length)+\
                "\ncode_class: "+str(self.code_class)+"\ncode_details: "+str(self.code_details)+\
                "\nmsg_id: "+str(self.msg_id)+"\ntoken: "+str(self.token)+\
                "\noptions: "+str(self.options)+"\nop_code: "+str(self.op_code)+\
                "\nord_no: "+str(self.ord_no)+"\noper_param: "+str(self.oper_param)
        else:
            return "invalid request"


def main_th_fct():
    counter = 0
    while running:
        # todo de intrebat rol
        # Apelam la functia sistem IO -select- pentru a verifca daca socket-ul are date in bufferul de receptie
        # Stabilim un timeout de 1 secunda
        r, _, _ = select.select([soc], [], [], 1)
        if not r:
            counter = counter + 1
            #todo de intrebat rol
        else:
            data_rcv, address = soc.recvfrom(max_up_size)
            new_request = Request(data_rcv)
            req_q1.put(new_request)
            #todo awake serv_th1
            print("RECEIVED ===> ", new_request, " <=== FROM: ", address)
            #print("cnt= ", counter)


def bits_to_int(param):
    if len(param) % 8 != 0:
        param=bitarray("0"*(int(floor((len(param)/8)+1)*8)-len(param)))+param
        #print("param=> " + str(param))
    return int.from_bytes(param.tobytes(), "big")

""" 
def service_th1_fct():  
    #TODO
    pass


def service_th2_fct():  
    #TODO
    pass


def sintatic_analizer(params):  
    #TODO
    pass


def deduplicator(params):  
    #TODO
    pass


def request_processor(params):  
    #TODO
    pass


def assemble_req(params):  
    #todo
    pass
"""

if __name__ == '__main__':
    # todo awake and sleep mecans for threads
    # todo control comands for basic terminal
    # todo colectie care contine toate thread urile petru join sau alte necesitati

    if len(sys.argv) != 4:
        print("Help : ")
        print("  --r_port=receive port number ")
        print("  --s_port=send port number ")
        print("  --s_ip=send ip ")
        sys.exit()

    for arg in sys.argv:
        if arg.startswith("--r_port"):
            temp, r_port = arg.split("=")
        elif arg.startswith("--s_port"):
            temp, s_port = arg.split("=")
        elif arg.startswith("--s_ip"):
            temp, s_ip = arg.split("=")

    # Creare socket UDP
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    soc.bind(('0.0.0.0', int(r_port)))

    running = True

    try:
        # todo pornit celelalte threaduri
        main_thread = threading.Thread(target=main_th_fct, name="Main Thread")
        main_thread.start()
    except:
        print("Eroare la pornirea main thread‐ului")
        sys.exit()

    while True:
        try:
            useless = input("Send: ")
            test_data = bitarray('01101101 01100101 01110011 01100001 01101010 00100000 01101101 01100101 01110011')
            soc.sendto(test_data.tobytes(), (s_ip, int(s_port)))
        except KeyboardInterrupt:
            running = False
            print("Waiting for the thread to close...")
            main_thread.join()
            break

"""
def bytes_to_bits(data):
    def access_bit(data_inn, num):
        #sursa functie access_bit: https://stackoverflow.com/questions/43787031/python-byte-array-to-bit-array
        base = int(num // 8)
        shift = int(num % 8)
        return (data_inn[base] >> shift) & 0x1

    return str([access_bit(data, i) for i in range(len(data) * 8)]).replace(",", "").replace("[", "").replace("]", "").replace(" ", "")
 #used as #bitarray(bytes_to_bits(data_rcv))
"""