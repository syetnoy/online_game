import datetime
import json
import socket
from threading import Thread
import time
from neo4j import TransactionError
import logging
from ubjson import EncoderException
import asyncio


class Cache():
    def __init__(self, offset=1) -> None:
        self.cache = []
        self.offset = offset
        self.actual_data = None
    
    def get_last_data(self):
        if self.cache:
            return self.cache[0]
        return []
    
    def get_data_by_offset(self, offset):
        if len(self.cache) < offset:
            return self.cache[offset]
        return {}
    
    def add_data(self, data):
        self.cache.insert(0, data)
        self.cache = self.cache[:self.offset]


class Client():
    def __init__(self, cache) -> None:
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.buffer_size = 2 ** 14
        self.tcp_src = None
        self.udp_src = None
        self.cache = cache
        
        self.udp_hooks = {}
    
    def call_tcp(self, method="ping", data=None,
                 response=False, callback=None):
        if type(data) not in (bytes, bytearray):
            if type(data) == dict:
                data = json.dumps(data).encode()
            else:
                raise EncoderException("Wrong data type!")
        request = {'type': method, 'data': data}
        self.send_tcp(request)
        if response:
            response = self.tcp_socket.recv(self.buffer_size)
            if callback:
                return callback(response)
            return response
    
    def call_udp(self, method="ping", data=None,
                 address=None, response=False, callback=None):
        if type(data) != dict:
            raise EncoderException("Wrong data type!")
        request = {'type': method, 'data': data}
        request = json.dumps(request).encode()
        self.send_udp(request, address)
        if response:
            response, addr = self.udp_socket.recvfrom(self.buffer_size)
            if callback:
                return callback(response)
            return response
    
    def create_session(self, remote):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect(remote)
        return self.tcp_socket
    
    def send_tcp(self, data):
        try:
            sock = self.tcp_socket
            sock.send(data)
            return True
        except:
            return False
    
    def send_udp(self, data, addr):
        try:
            sock = self.udp_socket
            sock.sendto(data, addr)
            return True
        except:
            return False
    
    def _run_udp_hook(self, address, callback, name="task"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(address)
        
        def udp_hook(socket, buffer_size, callback, name="task"):
            while True:
                try:
                    data, addr = socket.recvfrom(buffer_size)
                    logging.info(f"""
                                 UDP_LISTENER '{name}'
                                 GOT message
                                 FROM {addr[0]}: {addr[1]}
                                 """)
                    try:
                        request = json.loads(data)
                        callback(request)
                    except:
                        pass
                except:
                    socket.close()
        
        thread = Thread(target=udp_hook, args=(sock, self.buffer_size, callback))
        thread.start()
        return thread

    def run_udp_hook(self, address, callback, name='task'):
        thread = self._run_udp_hook(address, callback, name)
        if type(thread) != Thread:
            raise ValueError("Thread doesn't run")
        self.udp_hooks[name] = thread
    