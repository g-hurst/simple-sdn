#!/usr/bin/env python3

import sys
from datetime import date, datetime, timedelta
import argparse
import socket
import threading 
import json
import copy

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "switch#.log" # The log file for switches are switch#.log, where # is the id of that switch (i.e. switch0.log, switch1.log). The code for replacing # with a real number has been given to you in the main function.

K = 2               # every K seconds, a broadcast alive ping to all neighbors
TIMEOUT = 3 * K     # neighbors flagged as DEAD if have not recieved an alive ping by timeout

class Listener(threading.Thread):
    def __init__(self, socket):
        super().__init__()
        self._sock = socket
        self._event_queue = []
        self._event_queue_lock = threading.Lock()
    def run(self):
        print(f'listner (UDP) spinning up on: {self._sock.getsockname()}')
        while True:
            try:
                data, addr = self._sock.recvfrom(1024)
                self._event_queue_append((addr, data))
            except Exception as e:
                print(f'Listner broke: {e}')
                break
        print(f'listner (UDP) killed on: {self._sock.getsockname()}')
    def event_queue_pop(self, n=0):
        with self._event_queue_lock:
            val = self._event_queue.pop(n)
        return val
    def _event_queue_append(self, event):
        with self._event_queue_lock:
            self._event_queue.append(event)
    def event_queue_size(self):
        with self._event_queue_lock:
            sz = len(self._event_queue)
        return sz


class Sender(threading.Thread):
    def __init__(self, socket):
        super().__init__()
        self._sock = socket
        self._send_queue = []
        self._send_queue_lock = threading.Lock()
    def run(self):
        while True:
            if self.send_queue_size() > 0:
                self._sock.sendto( *self._send_queue_pop() )
    def _send_queue_pop(self, n=0):
        with self._send_queue_lock:
            val = self._send_queue.pop(n)
        return val
    def send_queue_append(self, event, front=False):
        with self._send_queue_lock:
            if front:
                self._send_queue.insert(0, event)
            else:
                self._send_queue.append(event)
    def send_queue_size(self):
        with self._send_queue_lock:
            sz = len(self._send_queue)
        return sz
        
class Neighbor():
    def __init__(self, nb_id, host, port):
        self.id = nb_id
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self.alive_ping_age = datetime.now()
        self.alive_ping_delta = timedelta(seconds=TIMEOUT)
        self._is_alive = True
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
    def __init__(self, sw_id, host, port, sender):
        self.id   = sw_id
        self.host = host
        self.port = port
        self.sender = sender
        self.lock = threading.Lock()
        self.log_file_name = LOG_FILE
        self.log_file_lock = threading.Lock()
        self.log  = []
        self.alive_ping_age   = datetime.now()
        self.alive_ping_delta = timedelta(seconds=K)
        self.neighbors = dict()
        self.routing_table = []

    def register(self):
        msg = {'action':'register_request', 'data':self.id}
        self.sender.send_queue_append((json.dumps(msg).encode(), (self.host, self.port)))
        self.log_register_request_sent()

    def handle_register_response(self, table):
        assert self.lock.locked()
        for row in table:
            assert len(row) == 3
            self.neighbors[row[0]] = Neighbor(*row)
        self.log_register_response_received()
    def handle_neighbor_dead(self, nb_id:int):
        assert self.lock.locked()
        self.neighbors.pop(nb_id)
        print(f'DEAD: {self.id}->{nb_id}')
        self.log_neighbor_dead(nb_id)
    def handle_alive_ping(self, nb_id:int):
        assert self.lock.locked()
        with self.neighbors[nb_id].lock:
            self.neighbors[nb_id].alive_ping_age = datetime.now()
    def handle_routing_table_update(self, table):
        assert self.lock.locked()
        self.routing_table = table
        self.log_routing_table_update()

    def do_alive_ping(self):
        for n in self.neighbors.values():
            msg = {'action':'keep_alive', 'data':self.id}
            self.sender.send_queue_append((json.dumps(msg).encode(), (n.host, n.port)), front=True)

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
    # Timestamp
    # Routing Update 
    # <Switch ID>,<Dest ID>:<Next Hop>
    # ...
    # ...
    # Routing Complete
    def log_routing_table_update(self):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append("Routing Update\n")
        for dest_id, next_hop, _ in self.routing_table:
            self.log.append(f"{self.id},{dest_id}:{next_hop}\n")
        self.log.append("Routing Complete\n")
        self.dump_log()

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
        elif action == 'routing_update':
            with switch.lock:
                switch.handle_routing_table_update(data['data'])
        
    except Exception as e:
        if switch.lock.locked():
            switch.lock.release()
        print(f'\nerrmsg: "{e}"\nERROR READING EVENT: {host}:{port}\n{data}\n')

def loop_handle_events(switch, listner, do_break=lambda: False):
    success = True
    try:
        while not do_break():
            with switch.lock:
                # send out pings to switch neghbors
                if (datetime.now() - switch.alive_ping_age > switch.alive_ping_delta):
                    switch.do_alive_ping()
                    switch.alive_ping_age = datetime.now()

                # handle dead neighbors
                for nb_id in copy.deepcopy(list(switch.neighbors.keys())):
                    if not switch.neighbors[nb_id].is_alive():
                        switch.handle_neighbor_dead(nb_id)

            if listner.event_queue_size() > 0:
                event  = listner.event_queue_pop()
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
    switch = Switch(args.id, args.controller_hostname, args.controller_port, sender)
    switch.register()

    success = loop_handle_events(switch, listner)
    print(f'\n\nSwitch process complete: success = {success}'.upper())

    
if __name__ == "__main__":
    main()
