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
                        Uded for testing: The switch will run as usual, but the link to
                        neighborID is killed to simulate failure
```


## Message Structure

All messages are sent in JSON string format, and in the format: 
```
{'action':'', 'data':''}
```

### Messages Handled By Controller\

**register_request:** Message from Switch-to-Controller in order to allow 
switches to join the network in the bootstrapping process. Also allows for
switches to be identified once they come back alive. 
```
{'action':'register_request', 'data':<Switch_ID>}
```

**topology_update:** Message from Switch-to-Controller in order to keep the 
controllers network map structure updated. This allows for identification of 
dead links and also is used as a ping to keep switches alive on a timeout 
defined in `com.py`.
```
{'action': 'topology_update', 
  'data':   {<Switch_ID>:[<Neighbor_ID>, <Neighbor_ID>, ..., <Neighbor_ID>]}
}
```

### Messages Handled By Switch

**register_response:** Message from Controller-to-Switch that indicates
that the regiester request that the switch send was recieved. This 
gives the host and port information of the neighboring switches in 
order to send `keep_alive` messages. 
```
{'action':'register_response',
 'data': {'id':<Switch_ID>, 
          'table':[(<Neighbor_ID>, <Neighbor_Host>,<Neighbor_Port>),
                    ... ,
                    (<Neighbor_ID>, <Neighbor_Host>,<Neighbor_Port>)
           ]
  }
}
```

**routing_update:** Message from Controller-to-Switch in order to 
update the routing table. This distributes the centrally computed 
shortest paths throughout the network of switches. 
```
{'action':'routing_update', 
 'data':[
  (<Desitination_ID>, <Next_Routint_Hop_ID>, <Distance>),
  ... ,
  (<Desitination_ID>, <Next_Routint_Hop_ID>, <Distance>),
 ]
}
```

**keep_alive:** Message from Switch-to-Switch in order to 
monitor for dead neighbors upon a predefined timeout in `com.py`.
```
{'action':'keep_alive', 'data':<Switch_ID>}
```