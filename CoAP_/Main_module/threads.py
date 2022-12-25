import select
import sys
import threading

import general_use as gu
import server_main as mn
from deduplicator import deduplicator
from message import Message
from request_processor import request_processor
from sintatic_analizer import sintatic_analizer


def service_th1_fct():
    gu.log.info("service_th1_fct(): " + str(threading.current_thread()) + ". Thread started!")
    while running_sth_1_event.is_set():
        try:
            msg: Message = gu.req_q1.pop(0)
            if sintatic_analizer(msg):
                if deduplicator(msg):
                    awake_sth_2_event.set()
                    pass
        except IndexError:
            awake_sth_1_event.wait(gu.wait_time_value)
            awake_sth_1_event.clear()

    gu.log.info("service_th1_fct(): " + str(threading.current_thread()) + ". Thread stoped!")


def service_th2_fct():
    gu.log.info("service_th2_fct(): " + str(threading.current_thread()) + ". Thread started!")
    while running_sth_2_event.is_set():
        try:
            msg: Message = gu.req_q2.pop(0)
            request_processor(msg)
        except IndexError:
            awake_sth_2_event.wait(gu.wait_time_value)
            awake_sth_2_event.clear()

    gu.log.info("service_th2_fct(): " + str(threading.current_thread()) + ". Thread stoped!")


def main_th_fct():
    gu.log.info("main_th_fct(): " + str(threading.current_thread()) + ". Thread started!")
    try:
        while running_mth_event.is_set():
            # Apelam la functia sistem IO -select- pentru a verifca daca socket-ul are date in bufferul de receptie
            # Stabilim un timeout de 1 secunda
            recpt, _, _ = select.select([gu.socket_], [], [], 1)
            if recpt:
                mn.receive_request()
                awake_sth_1_event.set()
    except Exception as e:
        gu.log.error("main_th_fct(): " + str(e) + ". Execution aborted!")
        sys.exit()
    gu.log.info("main_th_fct(): " + str(threading.current_thread()) + ". Thread stoped!")


def start_threads():
    try:
        gu.log.info("==============================================================================================")
        running_mth_event.set()
        running_sth_2_event.set()
        running_sth_1_event.set()

        main_thread.start()
        service_th_1.start()
        service_th_2.start()
    except Exception as e:
        gu.log.error("start_threads(): " + str(e))


def stop_threads():
    try:
        running_mth_event.clear()
        running_sth_1_event.clear()
        running_sth_2_event.clear()

        main_thread.join()
        service_th_1.join()
        service_th_2.join()
        gu.log.info("Threads joined with success!")
    except Exception as e:
        gu.log.error("stop_threads(): " + str(e))


# threadurile folosite
main_thread = threading.Thread(target=main_th_fct, name="Main Thread")
service_th_1 = threading.Thread(target=service_th1_fct, name="Service Thread1")
service_th_2 = threading.Thread(target=service_th2_fct, name="Service Thread2")

# evenimentele ce determina functionarea th-urilor
running_mth_event = threading.Event()
running_sth_1_event = threading.Event()
running_sth_2_event = threading.Event()

# evenimentele ce determina "trezirea" ths1 si ths2
awake_sth_1_event = threading.Event()
awake_sth_2_event = threading.Event()
