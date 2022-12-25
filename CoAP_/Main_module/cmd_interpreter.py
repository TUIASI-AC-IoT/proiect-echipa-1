import sys

import general_use as gu
import threads as th


def indexOf(str, substr):
    try:
        return str.index(substr)
    except:
        return -1


def cmd_interpreter(cmd: str):
    if cmd.upper() == "LOG-DATA":
        gu.logdata_flag = not gu.logdata_flag
        print("LOG-DATA: " + str(gu.logdata_flag))
    elif indexOf(cmd.upper(), "WAIT-TIME") != -1:
        gu.wait_time_value = int(cmd.upper().split("WAIT-TIME")[1])
        print("WAIT-TIME: " + str(gu.wait_time_value))
    elif cmd.upper() == "EXIT":
        print("CLOSING")
        th.stop_threads()
        sys.exit()
    elif indexOf(cmd.upper(), "UDP-PAYLOAD-MSIZE") != -1:
        gu.max_up_size = int(cmd.upper().split("UDP-PAYLOAD-MSIZE")[1])
        print("UDP-PAYLOAD-MSIZE: " + str(gu.max_up_size))
    elif cmd.upper() == "R-PORT":
        print("R-PORT: " + str(gu.r_port))
    elif cmd.upper() == "S-PORT":
        print("S-PORT: " + str(gu.s_port))
    elif cmd.upper() == "S-IP":
        print("S-IP: " + str(gu.s_ip))
    elif cmd.upper() == "PRINT-DATA":
        gu.printdata_flag=not gu.printdata_flag
        print("PRINT-DATA: "+str(gu.printdata_flag))
    elif cmd.upper() == "CMD-LIST":
        print("CMD-LIST: LOG-DATA, WAIT-TIME, EXIT, R-PORT, S-PORT, S-IP, UDP-PAYLOAD-MSIZE, PRINT-DATA")
    else:
        print("Unknown command: " + cmd + "\n")
