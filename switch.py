#!/usr/bin/env python3

import sys
from datetime import date, datetime
import argparse
import socket
import threading 
import json

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "switch#.log" # The log file for switches are switch#.log, where # is the id of that switch (i.e. switch0.log, switch1.log). The code for replacing # with a real number has been given to you in the main function.

event_queue = []
event_queue_lock = threading.Lock()
def event_queue_pop(n=0):
    with event_queue_lock:
        val = event_queue.pop(n)
    return val
def event_queue_append(event):
    with event_queue_lock:
        event_queue.append(event)

send_queue = []
send_queue_lock = threading.Lock()
def send_queue_pop(n=0):
    with send_queue_lock:
        val = send_queue.pop(n)
    return val
def send_queue_append(event):
    with send_queue_lock:
        send_queue.append(event)
def send_queue_size():
    with send_queue_lock:
        sz = len(send_queue)
    return sz

class Listener(threading.Thread):
    def __init__(self, socket):
        super().__init__()
        self._sock = socket
    def run(self):
        print(f'listner (UDP) spinning up on: {self._sock.getsockname()}')
        while True:
            try:
                data, addr = self._sock.recvfrom(1024)
                event_queue_append((addr, data))
            except Exception as e:
                print(f'Listner broke: {e}')
                break
        print(f'listner (UDP) killed on: {self._sock.getsockname()}')


class Sender(threading.Thread):
    def __init__(self, socket):
        super().__init__()
        self._sock = socket
    def run(self):
        while True:
            if send_queue_size() > 0:
                self._sock.sendto( *send_queue_pop() )
        
class Switch():
    def __init__(self, sw_id, host, port):
        self.id   = sw_id
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log_file_name = LOG_FILE
        self.log_file_lock = threading.Lock()
        self.log       = []
    def register(self):
        msg = {'action':'register_request', 'data':self.id}
        send_queue_append((json.dumps(msg).encode(), (self.host, self.port)))
        self.log_register_request_sent()

    def handle_register_response(self, data):
        self.log_register_response_received()

    def dump_log(self):
        with self.log_file_lock:
            with open(self.log_file_name, 'a+') as log_file:
                log_file.write("\n\n")
                log_file.writelines(self.log)
                self.log = []
    # Timestamp
    # Register Request Sent
    def log_register_request_sent(self):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Register Request Sent\n")
        self.dump_log()
    # Timestamp
    # Register Response Received
    def log_register_response_received():
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Register Response received\n")
        self.dump_log() 

# For the parameter "routing_table", it should be a list of lists in the form of [[...], [...], ...]. 
# Within each list in the outermost list, the first element is <Switch ID>. The second is <Dest ID>, and the third is <Next Hop>.
# "Routing Update" Format is below:
#
# Timestamp
# Routing Update 
# <Switch ID>,<Dest ID>:<Next Hop>
# ...
# ...
# Routing Complete
# 
# You should also include all of the Self routes in your routing_table argument -- e.g.,  Switch (ID = 4) should include the following entry: 		
# 4,4:4
def routing_table_update(routing_table):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append("Routing Update\n")
    for row in routing_table:
        log.append(f"{row[0]},{row[1]}:{row[2]}\n")
    log.append("Routing Complete\n")
    write_to_log(log)

# "Unresponsive/Dead Neighbor Detected" Format is below:
#
# Timestamp
# Neighbor Dead <Neighbor ID>
def neighbor_dead(switch_id):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Neighbor Dead {switch_id}\n")
    write_to_log(log) 

# "Unresponsive/Dead Neighbor comes back online" Format is below:
#
# Timestamp
# Neighbor Alive <Neighbor ID>
def neighbor_alive(switch_id):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Neighbor Alive {switch_id}\n")
    write_to_log(log) 

def write_to_log(log):
    with open(LOG_FILE, 'a+') as log_file:
        log_file.write("\n\n")
        # Write to log
        log_file.writelines(log)

def handle_event(event, switch)->None:
    # print(f'event detected: {event}')
    (host, port), data = event
    data = json.loads(data.decode())
    try:
        if data['action'].lower() == 'register_response':
            if switch.id != data['data']['id']:
                raise Exception('wrong register response recieved Switch({}) got {}'.format(switch.id, data['data']['id']))
            

    except Exception as e:
        if switch.lock.locked():
            switch.lock.release()
        print(f'{e}\nERROR READING EVENT: {host}:{port}\n{data}\n')

def loop_handle_events(switch, do_break=lambda: False):
    success = True
    try:
        while not do_break():
            if len(event_queue) > 0:
                event  = event_queue_pop()
                thread = threading.Thread(target=handle_event, args=(event, switch))
                thread.start()
    except KeyboardInterrupt:
        print('keyboard interrupt in loop_handle_events()')
        success = False
        if switch.lock.locked():
            switch.lock.release()
    return success

def main():
    global LOG_FILE

    parser = argparse.ArgumentParser(
                        prog='Switch.py',
                        description='Simple Software Defnined Netowrk (SDN) Switch')
    parser.add_argument('id', 
                        type=int, 
                        help='id of the switch (must be integer)')
    parser.add_argument('controller_hostname', 
                        type=str, 
                        help='host that the switch reaches out to')
    parser.add_argument('controller_port', 
                        type=int, 
                        help='port on host that the switch communicates on (must be integer)')
    parser.add_argument('-f', '--neighborID',
                        type=str, 
                        help='Uded for testing: The switch will run as usual, but the link to neighborID is killed to simulate failure')
    args = parser.parse_args()

    LOG_FILE = 'switch' + str(args.id) + ".log" 

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print('\n\nStarting listner'.upper())
    listner = Listener(sock)
    listner.start()
    
    print('\n\nStarting sender'.upper())
    sender = Sender(sock)
    sender.start()

    print('\n\nSenging register request to controller'.upper())
    switch = Switch(args.id, args.controller_hostname, args.controller_port)
    switch.register()

    success = loop_handle_events(switch)
    print(f'\n\nSwitch process complete: success = {success}'.upper())

    
if __name__ == "__main__":
    main()
