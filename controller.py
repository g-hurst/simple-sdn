#!/usr/bin/env python3

import sys
from datetime import date, datetime
import argparse
import socket
import selectors
import types
import threading

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "Controller.log"

event_queue = []
def event_queue_pop(n=0):
    lock = threading.Lock()
    lock.acquire()
    val = event_queue.pop(n)
    lock.release()
    return val
def event_queue_append(event):
    lock = threading.Lock()
    lock.acquire()
    event_queue.append(event)
    lock.release()

class Listener():
    def __init__(self, port):
        self.port = port
        self.lock = threading.Lock()
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((socket.gethostname(), self.port))
        print(f'listner (UDP) started on port: {socket.gethostname()}:{self.port}')
        while True:
            data, addr = sock.recvfrom(1024)
            # print(f'{addr}: {data}')
            event_queue_append((addr, data))

class Switch():
    def __init__(self, id, host, port):
        self.id   = id
        self.host = host
        self.port = port
    def __str__(self):
        msg = 'Switch:\n  '
        msg += '\n  '.join([f'{k} == {v}' for (k,v) in self.__dict__.items()])
        return msg
    def __repr__(self):
        return f'<Switch({self.id})>'

class Controller():
    def __init__(self, cfg):
        self.dj_max   = sys.maxsize
        self.topology = cfg.get('num_switches')
        self.map      = {}
        for edge in cfg.get('edges'): 
            self.update_map(edge)
        self.paths     = {}
        self.lock      = threading.Lock()
        self.registery = dict()
        self.log_file_name = LOG_FILE
        self.log       = []
    def __str__(self, blocking=True):
        if blocking: self.lock.acquire()
        msg = 'Controller:\n  '
        msg += '\n  '.join([f'{k} == {v}' for (k,v) in self.__dict__.items()])
        if blocking: self.lock.release()
        return msg

    def update_map(self, edge):
        if self.map.get(edge[0]) == None: self.map[edge[0]]          = {edge[1]: edge[2]}
        else:                             self.map[edge[0]][edge[1]] = edge[2]
        if self.map.get(edge[1]) == None: self.map[edge[1]]          = {edge[0]: edge[2]}
        else:                             self.map[edge[1]][edge[0]] = edge[2]

    def send_register_response(self, switch_id=None):
        if switch_id == None:
            switches = self.registery.values()
        else:
            switches = [self.registery[switch_id],]
        for s in switches:
            self.log_register_response_sent(s.id)


    def dump_log(self):
        try:
            assert self.lock.locked()
        except: print('STOP BEING TRASH AT THREADDING :(')
        with open(self.log_file_name, 'a+') as log_file:
            log_file.write("\n\n")
            log_file.writelines(self.log)
            self.log = []
    # Timestamp
    # Register Request <Switch-ID>
    def log_register_request_received(self, switch_id):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Register Request {switch_id}\n")
        self.dump_log()
    # Timestamp
    # Register Response <Switch-ID>
    def log_register_response_sent(self, switch_id):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Register Response {switch_id}\n")
        self.dump_log() 

# For the parameter "routing_table", it should be a list of lists in the form of [[...], [...], ...]. 
# Within each list in the outermost list, the first element is <Switch ID>. The second is <Dest ID>, and the third is <Next Hop>, and the fourth is <Shortest distance>
# "Routing Update" Format is below:
#
# Timestamp
# Routing Update 
# <Switch ID>,<Dest ID>:<Next Hop>,<Shortest distance>
# ...
# ...
# Routing Complete
#
# You should also include all of the Self routes in your routing_table argument -- e.g.,  Switch (ID = 4) should include the following entry: 		
# 4,4:4,0
# 0 indicates ‘zero‘ distance
#
# For switches that can’t be reached, the next hop and shortest distance should be ‘-1’ and ‘9999’ respectively. (9999 means infinite distance so that that switch can’t be reached)
#  E.g, If switch=4 cannot reach switch=5, the following should be printed
#  4,5:-1,9999
#
# For any switch that has been killed, do not include the routes that are going out from that switch. 
# One example can be found in the sample log in starter code. 
# After switch 1 is killed, the routing update from the controller does not have routes from switch 1 to other switches.
def routing_table_update(routing_table):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append("Routing Update\n")
    for row in routing_table:
        log.append(f"{row[0]},{row[1]}:{row[2]},{row[3]}\n")
    log.append("Routing Complete\n")
    write_to_log(log)

# "Topology Update: Link Dead" Format is below: (Note: We do not require you to print out Link Alive log in this project)
#
#  Timestamp
#  Link Dead <Switch ID 1>,<Switch ID 2>
def topology_update_link_dead(switch_id_1, switch_id_2):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Link Dead {switch_id_1},{switch_id_2}\n")
    write_to_log(log) 

# "Topology Update: Switch Dead" Format is below:
#
#  Timestamp
#  Switch Dead <Switch ID>
def topology_update_switch_dead(switch_id):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Switch Dead {switch_id}\n")
    write_to_log(log) 

# "Topology Update: Switch Alive" Format is below:
#
#  Timestamp
#  Switch Alive <Switch ID>
def topology_update_switch_alive(switch_id):
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Switch Alive {switch_id}\n")
    write_to_log(log) 


def read_config(f_name):
    lines = [line.strip() for line in open(f_name, 'r')]
    cfg = {
        'num_switches':int(lines.pop(0)),
        'edges':[list(map(int, l.split())) for l in lines]
    }
    return cfg

def run_listner(port:int)->None:
    listner = Listener(port)
    listner.start()

def handle_event(event, controller:Controller)->None:
    (host, port), text = event
    text = text.decode()
    text = [l.split() for l in text.split('\n')]
    try:
        if text[0][1].lower() == 'register_request':
            controller.lock.acquire()
            switch_id = int(text[0][0])
            switch = Switch(switch_id, host, port) 
            controller.registery[switch_id] = switch
            controller.log_register_request_received(switch_id)
            controller.lock.release()
            print(switch)
            print(f'registered {text[0][0]}')
    except Exception as e:
        if controller.lock.locked():
            controller.lock.release()
        print(f'{e}\nERROR READING EVENT: {host}:{port}\n{text}\n')

def main():
    parser = argparse.ArgumentParser(
                        prog='Controller.py',
                        description='Simple Software Defnined Netowrk (SDN) Controller')
    parser.add_argument('port', type=int, help='port for the controller to listen on (must be integer)')
    parser.add_argument('config_path', type=str, help='path of the config file')
    args = parser.parse_args()
    
    # Write your code below or elsewhere in this file
    cfg = read_config(args.config_path)
    controller = Controller(cfg)

    listner_thread = threading.Thread(target=run_listner, args=(args.port,))
    listner_thread.start()

    # wait for all the switches to register
    do_break = False
    while not do_break:
        if len(event_queue) > 0:
            event  = event_queue_pop()
            thread = threading.Thread(target=handle_event, args=(event, controller))
            thread.start()

        controller.lock.acquire()
        if controller.topology == len(controller.registery.keys()):
            do_break = True
        controller.lock.release()
    print('\n\nbootstrap process completed'.upper())
    print(controller)
    controller.lock.acquire()
    controller.send_register_response()
    controller.lock.release()

if __name__ == "__main__":
    main()
