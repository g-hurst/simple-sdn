#!/usr/bin/env python3

import sys
from datetime import date, datetime, timedelta
import argparse
import socket
import threading 
import json

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "switch#.log" # The log file for switches are switch#.log, where # is the id of that switch (i.e. switch0.log, switch1.log). The code for replacing # with a real number has been given to you in the main function.

K = 2               # every K seconds, a broadcast alive ping to all neighbors
TIMEOUT = 3 * K     # neighbors flagged as DEAD if have not recieved an alive ping by timeout

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
def send_queue_append(event, front=False):
    with send_queue_lock:
        if front:
            send_queue.insert(0, event)
        else:
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
        
class Neighbor():
    def __init__(self, nb_id, host, port):
        self.id = nb_id
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self.alive_ping_age = datetime.now()
        self.alive_ping_delta = timedelta(seconds=TIMEOUT)
    def __str__(self, blocking=True):
        if blocking: self.lock.acquire()
        msg = 'Neighbor:\n  '
        msg += '\n  '.join([f'{k} == {v}' for (k,v) in self.__dict__.items()])
        if blocking: self.lock.release()
        return msg
    def __repr__(self):
        return f'<Neighbor({self.id})>'

    def is_alive(self):
        assert not self.lock.locked()
        with self.lock:
            is_alv = (datetime.now() - self.alive_ping_age < self.alive_ping_delta)
        return is_alv

class Switch():
    def __init__(self, sw_id, host, port):
        self.id   = sw_id
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self.log_file_name = LOG_FILE
        self.log_file_lock = threading.Lock()
        self.log  = []
        self.alive_ping_age   = datetime.now()
        self.alive_ping_delta = timedelta(seconds=K)
        self.neighbors = dict()

    def register(self):
        msg = {'action':'register_request', 'data':self.id}
        send_queue_append((json.dumps(msg).encode(), (self.host, self.port)))
        self.log_register_request_sent()

    def handle_register_response(self, table):
        assert self.lock.locked()
        for row in table:
            assert len(row) == 3
            self.neighbors[row[0]] = Neighbor(*row)
        self.log_register_response_received()
    def handle_neighbor_dead(self, nb_id:int):
        # TODO: fix spam when neighbor dies
        print(f'DEAD: {self.id}->{nb_id}')
        self.log_neighbor_dead(nb_id)
    def handle_alive_ping(self, nb_id:int):
        assert self.lock.locked()
        with self.neighbors[nb_id].lock:
            self.neighbors[nb_id].alive_ping_age = datetime.now()

    def do_alive_ping(self):
        for n in self.neighbors.values():
            msg = {'action':'keep_alive', 'data':self.id}
            send_queue_append((json.dumps(msg).encode(), (n.host, n.port)), front=True)

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
    def log_register_response_received(self):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Register Response received\n")
        self.dump_log() 
    # Timestamp
    # Neighbor Dead <Neighbor ID>
    def log_neighbor_dead(self, switch_id):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Neighbor Dead {switch_id}\n")
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
    (host, port), data = event
    data = json.loads(data.decode())
    try:
        action = data['action'].lower()
        if action == 'register_response':
            if switch.id != data['data']['id']:
                raise Exception('wrong register response recieved Switch({}) got {}'.format(switch.id, data['data']['id']))
            with switch.lock:
                switch.handle_register_response(data['data']['table'])
        elif action == 'keep_alive':
            with switch.lock:
                switch.handle_alive_ping(data['data'])
        
    except Exception as e:
        if switch.lock.locked():
            switch.lock.release()
        print(f'\nerrmsg: "{e}"\nERROR READING EVENT: {host}:{port}\n{data}\n')

def loop_handle_events(switch, do_break=lambda: False):
    success = True
    try:
        while not do_break():
            with switch.lock:
                # send out pings to switch neghbors
                if (datetime.now() - switch.alive_ping_age > switch.alive_ping_delta):
                    switch.do_alive_ping()
                    switch.alive_ping_age = datetime.now()

                # handle dead neighbors
                for n in switch.neighbors.values():
                    if not n.is_alive():
                        switch.handle_neighbor_dead(n.id)

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
