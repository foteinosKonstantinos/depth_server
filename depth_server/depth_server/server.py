# TODO: Compare timestemps, set slop
# https://wiki.python.org/moin/TcpCommunication.html
# ΤΙ ΊΝΕΤΑΙ ΜΕ ΤΟ LATENCY? ΥΠΆΡΧΕΙ ΜΕΓΆΛΗ ΧΡΟΝΙΚΉ ΔΙΑΦΟΡΆ ΣΤΑ FRAMES
# ΠΡΈΠΕΙ ΝΑ ΣΤΈΛΝΕΤΑΙ ΚΑΙ TIMESTAMP

# https://docs.python.org/3/builtins/threadsafety.html#thread-safety-for-dict-objects

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from rclpy.executors import ExternalShutdownException
import socket
import pickle
import numpy as np
import time
import threading
# from . import CONFIG

red_back = lambda x:f"\033[1;101m{x}\033[0;0m"
green_back = lambda x:f"\033[1;102m{x}\033[0;0m"
blue_back = lambda x:f"\033[1;104m{x}\033[0;0m"

red_fore = lambda x:f"\033[1;91m{x}\033[0;0m"
green_fore = lambda x:f"\033[1;92m{x}\033[0;0m"
blue_fore = lambda x:f"\033[1;94m{x}\033[0;0m"

CONFIG = {
    "IP_address": "127.0.0.1",
    "port": 49_153,
    "client_buffer": 1024,
    "server_buffer": 1024,
    "max_connections": 1,
    "increment": 16,
    "topic_name": "/b2/camera_front_435i/realsense_front_435i/aligned_depth_to_color/image_raw",
    "decode_image": lambda depth: (np.frombuffer(depth.data, dtype=np.uint16).reshape((depth.height, depth.width)), depth.header.stamp.sec),
    "history": 20,
    "interval": 0.2, # 1 / FPS
    "slop": 1, # sec
}

def unflatten(uv:list[int]) -> list[tuple[int]]:
    '''Input format: [u0, v0, u1, v1, u2, v2, ...]'''
    res = []
    previous = None
    for item in uv:
        if previous is None:
            previous = item
        else:
            res.append((previous, item))
            previous = None
    return res

class Server_Node(Node):
    
    def __init__(self, config:dict=CONFIG):
        
        super().__init__("server_node")
        
        self.config = config

        self.history = []
        self.history_lock = threading.Lock()

        self.subsrciber = self.create_subscription(msg_type=Image, topic=config["topic_name"], qos_profile=1, callback=self.topic_callback)
        self.previous = None

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, config["client_buffer"])
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, config["server_buffer"])

        network_thread = threading.Thread(target=self.start_server)
        network_thread.start()
    
    def info(self, msg:str):
        print("[INFO] "+msg)
    
    def warn(self, msg:str):
        print("[WARN] "+msg)
    
    def error(self, msg:str):
        print("[ERROR] "+msg)

    def push(self, data):
        with self.history_lock:
            self.history.append(data)
            if len(self.history) > self.config["history"]:
                self.history.pop(0)

    def retrieve(self, soft_key):
        with self.history_lock:
            for pair in self.history:
                if abs(pair[1]-soft_key) <= self.config["slop"]:
                    return pair[0]
        return None

    def topic_callback(self, image:Image):
        now = time.time()
        if (self.previous is not None) and (now - self.previous < self.config["interval"]):
            return
        self.previous = now
        decoded_image = self.config["decode_image"](image)
        self.push(decoded_image)
    
    def connection_callback(self, uv_and_timestamp:list[int]):
        '''Input format: [u0, v0, u1, v1, u2, v2, ..., un, vn, timestamp]'''
        uv = uv_and_timestamp[:-1]
        timestamp = uv_and_timestamp[-1]
        depth_frame = self.retrieve(timestamp)
        if depth_frame is not None:
            # u = pair[0] (horizontal), v = pair[1] (vertical)
            depths = [depth_frame[pair[1]][pair[0]].item() for pair in unflatten(uv)]
            return depths
        else:
            return []
    
    def start_server(self) -> None:
        self.info(f"Starting server ...")
        self.server.bind((self.config["IP_address"], self.config["port"]))
        self.server.listen(self.config["max_connections"])
        self.info(f"Listening @ {self.config['IP_address']}:{self.config['port']} [max conn.: {self.config['max_connections']}] [buffer: {self.config['server_buffer']}]")
        msg_counter = 0
        while True:
            try:
                msg_counter += 1
                connection, client_address = self.server.accept()
                binary_in = connection.recv(self.config["server_buffer"])
                in_data = pickle.loads(binary_in)
                out_data = self.connection_callback(in_data)
                binary_out = pickle.dumps(out_data)
                if len(binary_out) >= self.config["client_buffer"]:
                    self.warn(f"[{msg_counter}] {client_address[0]}:{client_address[1]} res:{binary_sent}B >= buffer:{self.config['client_buffer']}B {red_fore('\u2612')}\a")    
                    connection.send(b"")
                    break
                binary_sent = connection.send(binary_out)
                self.info(f"[{msg_counter}] {client_address[0]}:{client_address[1]} req:{len(binary_in)}B --> res:{binary_sent}B {green_fore('\u2611')}")
            except KeyboardInterrupt:
                self.error(f"[{msg_counter}] Shutdown signal received by keyboard \a{red_fore('\u2620')}")
                raise ExternalShutdownException("Exit.")
            except pickle.PickleError as e:
                self.error(f"[{msg_counter}] Corrupted packet: \'{str(e)}\'")
            except BaseException as e:
                self.error(f"[{msg_counter}] {str(e)}")
            finally:
                try:
                    connection.close()
                except UnboundLocalError:
                    self.warn(f"[{msg_counter}] No connection to close.")

def main():
    try:
        rclpy.init()
        rclpy.spin(node=Server_Node(config=CONFIG))
    except (ExternalShutdownException, KeyboardInterrupt) as e:
        print(e)

if __name__ == "__main__":
    main()