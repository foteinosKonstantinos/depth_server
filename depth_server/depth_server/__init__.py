import numpy as np

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

def flatten(uv:list[tuple[int]]) -> list[int]:
    '''Input format: [(u0, v0), (u1, v1), ...]'''
    res = []
    for pair in uv:
        res.append(pair[0])
        res.append(pair[1])
    return res

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

red_back = lambda x:f"\033[1;101m{x}\033[0;0m"
green_back = lambda x:f"\033[1;102m{x}\033[0;0m"
blue_back = lambda x:f"\033[1;104m{x}\033[0;0m"

red_fore = lambda x:f"\033[1;91m{x}\033[0;0m"
green_fore = lambda x:f"\033[1;92m{x}\033[0;0m"
yellow_fore = lambda x:f"\033[1;93m{x}\033[0;0m"
blue_fore = lambda x:f"\033[1;94m{x}\033[0;0m"

info = lambda msg:print("[INFO] "+str(msg))
warn = lambda msg:print(yellow_fore("[WARN]")+" "+str(msg))
error = lambda msg:print(red_back("[ERROR]")+" "+str(msg)+" "+red_fore("\u2612")+"\a")