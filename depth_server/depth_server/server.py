# TODO: Compare timestemps, set slop
# https://wiki.python.org/moin/TcpCommunication.html
# ΤΙ ΊΝΕΤΑΙ ΜΕ ΤΟ LATENCY? ΥΠΆΡΧΕΙ ΜΕΓΆΛΗ ΧΡΟΝΙΚΉ ΔΙΑΦΟΡΆ ΣΤΑ FRAMES
# ΠΡΈΠΕΙ ΝΑ ΣΤΈΛΝΕΤΑΙ ΚΑΙ TIMESTAMP
# Connect with receiver from topics broadcaster and keep only the last frame ????

# https://docs.python.org/3/builtins/threadsafety.html#thread-safety-for-dict-objects

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from rclpy.executors import ExternalShutdownException
import socket
import pickle
import time
import threading
from . import CONFIG, unflatten, red_fore, green_fore, blue_fore, info, warn, error

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
    
    def connection_callback(self, uv_and_timestamp:list[int], msg_counter:int):
        '''Input format: [u0, v0, u1, v1, u2, v2, ..., un, vn, timestamp]'''
        uv = uv_and_timestamp[:-1]
        timestamp = uv_and_timestamp[-1]
        depth_frame = self.retrieve(timestamp)
        if depth_frame is not None:
            # u = pair[0] (horizontal), v = pair[1] (vertical)
            try:
                depths = [depth_frame[pair[1]][pair[0]].item() for pair in unflatten(uv)]
            except IndexError as e:
                error(f"[{msg_counter}] Index out of range ({str(e)})")
                depths = []
            return depths
        else:
            warn(f"[{msg_counter}] No frame found")
            return []
    
    def start_server(self) -> None:
        info("Starting server ...")
        self.server.bind((self.config["IP_address"], self.config["port"]))
        self.server.listen(self.config["max_connections"])
        info(f"Listening @ {blue_fore(self.config['IP_address'])}:{blue_fore(self.config['port'])} [max conn.: {self.config['max_connections']}] [buffer: {self.config['server_buffer']}]")
        msg_counter = 0
        while True:
            try:
                msg_counter += 1
                connection, client_address = self.server.accept()
                info(f"[{msg_counter}] New connection: {blue_fore(client_address[0])}:{blue_fore(client_address[1])}")
                binary_in = connection.recv(self.config["server_buffer"])
                in_data = pickle.loads(binary_in)
                out_data = self.connection_callback(in_data, msg_counter)
                binary_out = pickle.dumps(out_data)
                if len(binary_out) >= self.config["client_buffer"]:
                    warn(f"[{msg_counter}] res:{binary_sent}B >= buffer:{self.config['client_buffer']}B {red_fore('\u2612')}\a")    
                    connection.send(b"")
                    break
                binary_sent = connection.send(binary_out)
                info(f"[{msg_counter}] req:{len(binary_in)}B --> res:{binary_sent}B {green_fore('\u2611')}")
            except KeyboardInterrupt:
                error(f"[{msg_counter}] Shutdown signal received by keyboard")
                raise ExternalShutdownException("Exit.")
            except pickle.PickleError as e:
                error(f"[{msg_counter}] Corrupted packet: \'{str(e)}\'")
            except BaseException as e:
                error(f"[{msg_counter}] {str(e)}")
            finally:
                try:
                    connection.close()
                except UnboundLocalError:
                    warn(f"[{msg_counter}] No connection to close.")

def main():
    try:
        rclpy.init()
        rclpy.spin(node=Server_Node(config=CONFIG))
    except (ExternalShutdownException, KeyboardInterrupt) as e:
        print(e)

if __name__ == "__main__":
    main()