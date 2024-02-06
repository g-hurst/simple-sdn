#!/usr/bin/env python3

import sys
from datetime import date, datetime, timedelta
import argparse
import socket
import threading 
import json
import copy

from com import Listener, Sender, PING_TIME, TIMEOUT

# The log file for switches are switch#.log, where # is the id of that switch (i.e. switch0.log, switch1.log). 
# The code for replacing # with a real number has been given to you in the main function.
LOG_FILE = "switch#.log" 

class Neighbor():
    def __init__(self, nb_id, host, port):
        self.id = nb_id
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self.ping_age = datetime.now()
        self.ping_delta = timedelta(seconds=TIMEOUT)
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
            is_alv = (datetime.now() - self.ping_age < self.ping_delta)
        return is_alv

class Switch():
    def __init__(self, sw_id, host, port, failure_id, sender):
        self.id   = sw_id
        self.host = host
        self.port = port
        self.failure_id = failure_id
        self.sender = sender
        self.lock = threading.Lock()
        self.log_file_name = LOG_FILE
        self.log_file_lock = threading.Lock()
        self.log  = []
        self.ping_age   = datetime.now()
        self.ping_delta = timedelta(seconds=PING_TIME)
        self.neighbors = dict()
        self.routing_table = []
        self.is_registered = False

    def register(self):
        msg = {'action':'register_request', 'data':self.id}
        self.sender.send_queue_append(
            (json.dumps(msg).encode(), (self.host, self.port))
        )
        self.log_register_request_sent()

    def handle_register_response(self, table):
        assert self.lock.locked()
        if self.is_registered == False:
            self.is_registered = True
            self.ping_age = datetime.now()
        for row in table:
            assert len(row) == 3
            self.neighbors[row[0]] = Neighbor(*row)
        self.log_register_response_received()

    def handle_neighbor_dead(self, nb_id:int):
        assert self.lock.locked()
        self.neighbors.pop(nb_id)
        print(f'DEAD: {self.id}->{nb_id}')
        self.log_neighbor_dead(nb_id)

    def handle_alive_ping(self, nb_id:int, host, port):
        assert self.lock.locked()
        if  nb_id != self.failure_id:
            if nb_id in self.neighbors:
                with self.neighbors[nb_id].lock:
                    self.neighbors[nb_id].ping_age = datetime.now()
            else:
                print(f'ALIVE: {self.id}->{nb_id}')
                self.neighbors[nb_id] = Neighbor(nb_id, host, port)
                self.log_neighbor_alive(nb_id)

    def handle_routing_table_update(self, table):
        assert self.lock.locked()
        self.routing_table = table
        self.log_routing_table_update()

    def do_alive_ping(self):
        for n in self.neighbors.values():
            if n.id != self.failure_id:
                msg = {'action':'keep_alive', 'data':self.id}
                self.sender.send_queue_append(
                    (json.dumps(msg).encode(), (n.host, n.port)), 
                    front=True
                )

    def do_topology_update(self):
        msg = {'action': 'topology_update', 
               'data':   {self.id:list(self.neighbors.keys())}
              }
        self.sender.send_queue_append(
            (json.dumps(msg).encode(), (self.host, self.port)), 
        )

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
    # Routing Complete
    def log_routing_table_update(self):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append("Routing Update\n")
        for dest_id, next_hop, _ in self.routing_table:
            self.log.append(f"{self.id},{dest_id}:{next_hop}\n")
        self.log.append("Routing Complete\n")
        self.dump_log()
    # Timestamp
    # Neighbor Alive <Neighbor ID>
    def log_neighbor_alive(self, switch_id):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Neighbor Alive {switch_id}\n")
        self.dump_log() 

def handle_event(event, switch)->None:
    (host, port), data = event
    data = json.loads(data.decode())
    try:
        action = data['action'].lower()
        if action == 'register_response':
            if switch.id != data['data']['id']:
                raise Exception(
                    'wrong register response recieved Switch({}) got {}'.format(
                        switch.id, data['data']['id']
                        )
                    )
            with switch.lock:
                switch.handle_register_response(data['data']['table'])
        elif action == 'keep_alive':
            with switch.lock:
                switch.handle_alive_ping(data['data'], host, port)
        elif action == 'routing_update':
            with switch.lock:
                switch.handle_routing_table_update(data['data'])
        
    except Exception as e:
        if switch.lock.locked():
            switch.lock.release()
        print(f'\nerrmsg: "{e}"\nERROR READING EVENT: {host}:{port}\n{data}\n')

def loop_handle_events(switch, listener, do_break=lambda: False):
    success = True
    try:
        while not do_break():
            # handle incoming events
            if listener.event_queue_size() > 0:
                event  = listener.event_queue_pop()
                thread = threading.Thread(target=handle_event, args=(event, switch))
                thread.start()
                
            
            with switch.lock:
                if switch.is_registered:
                    # send out topology update and pings to switch neighbors 
                    if (datetime.now() - switch.ping_age > switch.ping_delta):
                        switch.do_alive_ping()
                        switch.do_topology_update()
                        switch.ping_age = datetime.now()

                    # handle dead neighbors
                    for nb_id in copy.deepcopy(list(switch.neighbors.keys())):
                        if not switch.neighbors[nb_id].is_alive():
                            switch.handle_neighbor_dead(nb_id)

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
                        type=int,
                        default=None,
                        help='Uded for testing: The switch will run as usual, but the link to neighborID is killed to simulate failure')
    args = parser.parse_args()

    LOG_FILE = 'switch' + str(args.id) + ".log" 

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print('\n\nStarting listener'.upper())
    listener = Listener(socket=sock)
    listener.start()

    print('\n\nStarting sender'.upper())
    sender = Sender(sock)
    sender.start()

    print('\n\nSenging register request to controller'.upper())
    switch = Switch(
        args.id, 
        args.controller_hostname, 
        args.controller_port, 
        args.neighborID, 
        sender
    )
    switch.register()

    success = loop_handle_events(switch, listener)
    print(f'\n\nSwitch process complete: success = {success}'.upper())

    sender.kill()
    listener.kill()
    
if __name__ == "__main__":
    main()
