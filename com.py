import threading
import socket

PING_TIME = 2               # every PING_TIME seconds, a broadcast alive ping to all neighbors
TIMEOUT = 3 * PING_TIME     # neighbors flagged as DEAD if have not recieved an alive ping by timeout

class Listener(threading.Thread):
    def __init__(self, port=None, socket=None):
        super().__init__()
        self._port = port
        self._sock = socket
        self._event_queue = []
        self._event_queue_lock = threading.Lock()
        self._stay_alive = threading.Event()
    def run(self):
        self._stay_alive.set()
        try:
            print(f'listener (UDP) spinning up on: {socket.gethostname()}:{self._port}')
            while self._stay_alive.is_set():
                if self._sock == None:
                    self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                    self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self._sock.settimeout(15)
                    if self._port != None:
                        self._sock.bind(('0.0.0.0', self._port))
                while True:
                    try: 
                        data, addr = self._sock.recvfrom(1024)
                        self._event_queue_append((addr, data))
                    except socket.timeout:
                        break
            print(f'listener (UDP) killed on: {socket.gethostname()}:{self._port}')
        except KeyboardInterrupt:
            print('keyboard interrupt in listener loop'.upper())
            self.kill()
    def kill(self):
        self._stay_alive.clear()   
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
        self._stay_alive = threading.Event()
    def run(self):
        self._stay_alive.set()
        while self._stay_alive.is_set():
            try:
                if self.send_queue_size() > 0:
                    self._sock.sendto( *self._send_queue_pop() )
            except KeyboardInterrupt:
                print('keyboard interrupt in sender loop'.upper())
                self.kill()
    def kill(self):
        self._stay_alive.clear()   
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