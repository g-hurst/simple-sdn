# simple-sdn

## Overview
This project is for Purdue ECE 50863 building a simple software definded network.

## Usage
**Controller:**
```
usage: Controller.py [-h] port config_path

Simple Software Defnined Netowrk (SDN) Controller

positional arguments:
  port         port for the controller to listen on (must be integer)
  config_path  path of the config file

options:
  -h, --help   show this help message and exit
```

**Switch:**
```
usage: Switch.py [-h] [-f NEIGHBORID] id controller_hostname controller_port

Simple Software Defnined Netowrk (SDN) Switch

positional arguments:
  id                    id of the switch (must be integer)
  controller_hostname   host that the switch reaches out to
  controller_port       port on host that the switch communicates on (must be integer)

options:
  -h, --help            show this help message and exit
  -f NEIGHBORID, --neighborID NEIGHBORID
                        Uded for testing: The switch will run as usual, but the link to neighborID is killed to simulate failure
```


## Message Structure
