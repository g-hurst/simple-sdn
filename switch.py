#!/usr/bin/env python3

import sys
from datetime import date, datetime
import argparse
import socket

# Please do not modify the name of the log file, otherwise you will lose points because the grader won't be able to find your log file
LOG_FILE = "switch#.log" # The log file for switches are switch#.log, where # is the id of that switch (i.e. switch0.log, switch1.log). The code for replacing # with a real number has been given to you in the main function.

class Controller():
    def __init__(self, sw_id, host, port):
        self.id   = sw_id
        self.host = host
        self.port = port
    def register(self):
        self.send(f'{self.id} register_request')

    def send(self, msg):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(bytes(msg, "utf-8"), (self.host, self.port))


# Those are logging functions to help you follow the correct logging standard

# "Register Request" Format is below:
#
# Timestamp
# Register Request Sent
def register_request_sent():
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Register Request Sent\n")
    write_to_log(log)

# "Register Response" Format is below:
#
# Timestamp
# Register Response Received
def register_response_received():
    log = []
    log.append(str(datetime.time(datetime.now())) + "\n")
    log.append(f"Register Response received\n")
    write_to_log(log) 

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

    controller = Controller(args.id, args.controller_hostname, args.controller_port)
    controller.register()

    # Write your code below or elsewhere in this file
    
if __name__ == "__main__":
    main()
