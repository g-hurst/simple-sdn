#!/usr/bin/env python3

import sys
from datetime import date, datetime, timedelta
import argparse
import socket
import threading
import json
import heapq
from copy import deepcopy
from itertools import permutations

from com import Listener, Sender, PING_TIME, TIMEOUT

LOG_FILE = "Controller.log"

class Switch():
    def __init__(self, id, host, port, sender):
        self.id   = id
        self.host = host
        self.port = port
        self._lock   = threading.Lock()
        self._sender = sender
        self.ping_age   = datetime.now()
        self.ping_delta = timedelta(seconds=TIMEOUT)
    def __str__(self):
        msg = 'Switch:\n  '
        msg += '\n  '.join([f'{k} == {v}' for (k,v) in self.__dict__.items()])
        return msg
    def __repr__(self):
        return f'<Switch({self.id})>'
    def send(self, msg):
        self._sender.send_queue_append((msg.encode(), (self.host, self.port)))
    def is_alive(self):
        assert not self._lock.locked()
        with self._lock:
            is_alv = (datetime.now() - self.ping_age < self.ping_delta)
        return is_alv

class Controller():
    def __init__(self, cfg, sender):
        self._djk_max   = 9999
        self.topology = cfg.get('num_switches')
        self.map           = {}
        self.bootstrapped_map = {}
        self.routing_table = {}
        for edge in cfg.get('edges'): 
            self.update_map(edge)
        self._sender    = sender
        self.paths     = {}
        self.lock      = threading.Lock()
        self.registery = dict()
        self.log_file_name = LOG_FILE
        self.log       = []
        self.is_booted = False
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

    def calc_routing_table_djk(self):
        print(f'calculating routing table on {self.map}')
        unseen_combos = set(permutations(self.bootstrapped_map.keys(), 2))
        self.routing_table = {}
        for start in self.map:
            # do djkstras
            distances = {node: self._djk_max for node in self.map}
            distances[start] = 0
            paths = {node: [start,] for node in self.map}
            visited = set()
            queue = [(0, start)]
            while queue:
                current_distance, current_node = heapq.heappop(queue)
                if current_node not in visited:
                    visited.add(current_node)
                    for adjacent, weight in self.map[current_node].items():
                        distance = current_distance + weight
                        if distances.get(adjacent) and distance < distances[adjacent]:
                            distances[adjacent] = distance
                            paths[adjacent] = paths[current_node] + [adjacent]
                            heapq.heappush(queue, (distance, adjacent))
            # unwrap the info for the table
            row = []
            for k in self.map:
                dest_id  = paths[k][-1]
                if len(paths[k]) > 1:
                    next_hop = paths[k][1]
                else:
                    next_hop = dest_id
                if (start, dest_id)  in unseen_combos:
                    unseen_combos.remove((start, dest_id))
                row.append((dest_id, next_hop, distances[k]))
            self.routing_table[start] = row

        # add infinite states for unreachable destinations
        for (start, dest) in unseen_combos:
            if self.routing_table.get(start) == None:
                continue
            self.routing_table[start].append((dest, -1, self._djk_max))

    def send_register_response(self, switch_id=None):
        if switch_id == None:
            switches = self.registery.values()
        else:
            switches = [self.registery[switch_id],]
        for s in switches:
            msg = {'action':'register_response',
                    'data': {'id':s.id, 
                             'table':[(self.registery[neighbor_id].id, 
                                       self.registery[neighbor_id].host, 
                                       self.registery[neighbor_id].port) for neighbor_id in self.map[s.id].keys()]}}

            s.send(json.dumps(msg))
            self.log_register_response_sent(s.id)

    def send_routing_table_update(self, switch_id=None):
        if switch_id == None:
            switches = self.registery.values()
        else:
            switches = [self.registery[switch_id],]
        for s in switches:
            msg = {'action':'routing_update', 'data':self.routing_table[s.id]}
            s.send(json.dumps(msg))
        self.log_routing_table_update()

    # handles when switches regiser durring bootstrap process
    # when bootstrapped, also handles when switch becomes re-alive
    def handle_register_request(self, host, port, switch_id):
        assert self.lock.locked()
        self.registery[switch_id] = Switch(switch_id, host, port, self._sender) 
        self.log_register_request_received(switch_id)
        if self.is_booted:
            # update the map with the stored data from bootstrapping
            self.map[switch_id] = self.bootstrapped_map.get(switch_id)
            for bsm_id in self.bootstrapped_map.keys():
                if switch_id in self.bootstrapped_map[bsm_id]:
                    self.map[bsm_id][switch_id] = self.bootstrapped_map[bsm_id][switch_id]

            self.calc_routing_table_djk()
            self.log_topology_update_switch_alive(switch_id)
            self.send_register_response()
            self.send_routing_table_update()
        print(f'registered {switch_id}')
    
    def handle_topology_update(self, top_update):
        assert self.lock.locked()
        do_calc = False
        sw_id = list(top_update.keys())[0]
        if int(sw_id) in self.map:
            # update switch alive status
            self.registery[int(sw_id)].ping_age = datetime.now()
            # check for dead links and recompute if needed
            for link_id in deepcopy(list(self.map[int(sw_id)].keys())):
                if link_id not in top_update[sw_id]:
                    do_calc = True
                    self.log_topology_update_link_dead(sw_id, link_id)
                    self.map[int(sw_id)].pop(link_id)
                    print(f'link dead {sw_id}->{link_id}')
            if do_calc:
                self.calc_routing_table_djk()
                self.send_routing_table_update()

    def handle_switch_dead(self, sw_id):
        assert self.lock.locked()
        self.registery.pop(sw_id)
        for k in self.map.keys():
            if sw_id in  self.map[k].keys():
                self.map[k].pop(sw_id)
        self.map.pop(sw_id)
        print(f'DEAD SWITCH: {sw_id}')
        self.log_topology_update_switch_dead(sw_id)
        self.calc_routing_table_djk()
        self.send_routing_table_update()
                
    def dump_log(self):
        assert self.lock.locked()
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
    # Timestamp
    # Routing Update 
    # <Switch ID>,<Dest ID>:<Next Hop>,<Shortest distance>
    # ...
    # ...
    # Routing Complete
    def log_routing_table_update(self):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append("Routing Update\n")
        for switch_id in sorted(self.routing_table.keys()):
            for dest_id, next_hop, dist_min in sorted(self.routing_table[switch_id], key=lambda x: x[0]):
                self.log.append(f"{switch_id},{dest_id}:{next_hop},{dist_min}\n")
        self.log.append("Routing Complete\n")
        self.dump_log()
    #  Timestamp
    #  Link Dead <Switch ID 1>,<Switch ID 2>
    def log_topology_update_link_dead(self, switch_id_1, switch_id_2):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Link Dead {switch_id_1},{switch_id_2}\n")
        self.dump_log() 
    #  Timestamp
    #  Switch Dead <Switch ID>
    def log_topology_update_switch_dead(self, switch_id):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Switch Dead {switch_id}\n")
        self.dump_log() 
    #  Timestamp
    #  Switch Alive <Switch ID>
    def log_topology_update_switch_alive(self, switch_id):
        self.log.append(str(datetime.time(datetime.now())) + "\n")
        self.log.append(f"Switch Alive {switch_id}\n")
        self.dump_log() 

# collects information from the configuration file
# and returns it in dictionary format
def read_config(f_name):
    lines = [line.strip() for line in open(f_name, 'r')]
    cfg = {
        'num_switches':int(lines.pop(0)),
        'edges':[list(map(int, l.split())) for l in lines]
    }
    return cfg

def handle_event(event, controller:Controller)->None:
    (host, port), data = event
    data = json.loads(data.decode())
    try:
        action = data['action'].lower()
        if action == 'register_request':
            with controller.lock:
                controller.handle_register_request(host, port, data['data'])

        # not locked becasue is_booted is only modified one time within
        # a lock after the bootstrap process is completed
        if controller.is_booted:
            if action == 'topology_update':
                with controller.lock:
                    controller.handle_topology_update(data['data'])

    except Exception as e:
        if controller.lock.locked():
            controller.lock.release()
        print(f'{e}\nERROR READING EVENT: {host}:{port}\n{data}\n')

def loop_handle_events(controller, listener, do_break=lambda: False):
    success = True
    try:
        while not do_break():
            # handle incoming events
            if listener.event_queue_size() > 0:
                event  = listener.event_queue_pop()
                thread = threading.Thread(target=handle_event, args=(event, controller))
                thread.start()

            with controller.lock:
                if controller.is_booted:
                    # handle dead switches
                    for sw_id in deepcopy(list(controller.registery.keys())):
                        if not controller.registery[sw_id].is_alive():
                            controller.handle_switch_dead(sw_id)
    except KeyboardInterrupt:
        print('keyboard interrupt in loop_handle_events()')
        success = False
        if controller.lock.locked():
            controller.lock.release()
    return success

def main():
    parser = argparse.ArgumentParser(
                        prog='Controller.py',
                        description='Simple Software Defnined Netowrk (SDN) Controller')
    parser.add_argument('port', type=int, help='port for the controller to listen on (must be integer)')
    parser.add_argument('config_path', type=str, help='path of the config file')
    args = parser.parse_args()
    
    print('\n\nStarting listener'.upper())
    listener = Listener(args.port)
    listener.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print('\n\nStarting sender'.upper())
    sender = Sender(sock)
    sender.start()

    cfg = read_config(args.config_path)
    controller = Controller(cfg, sender)

    # bootstraping process
    # waiting for all switches to register
    # all events that are not register requests durring this time are ignored
    do_break = False
    def is_booted():
        ret = False
        with controller.lock:
            if controller.topology == len(controller.registery.keys()):
                ret = True
        return ret
    success = loop_handle_events(controller, listener, is_booted)
    controller.bootstrapped_map = deepcopy(controller.map)
    for sw_id in deepcopy(list(controller.registery.keys())):
        controller.registery[sw_id].ping_age = datetime.now()
    print(f'\n\nBootstrap process completed: success = {success}'.upper())
    print(controller)

    if success:
        # bootstraping process complete, so broadcast register responses
        with controller.lock:
            controller.is_booted = True
            controller.send_register_response()
            print('\n\nRegister responses sent'.upper())

            controller.calc_routing_table_djk()
            controller.send_routing_table_update()
            print(f'\n\nCalculated and writing routing table'.upper())

        # start the main controller process 
        print('\n\nStarting main controller process'.upper())
        success = loop_handle_events(controller, listener)
        print(f'\n\nMain controller process completed: success = {success}'.upper())

    listener.kill()
    print('program complete ')

if __name__ == "__main__":
    main()
