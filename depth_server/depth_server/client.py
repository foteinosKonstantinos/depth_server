import socket
#from . import CONFIG
import pickle

CONFIG = {
    "IP_address": "127.0.0.1",
    "port": 49_153,
    "client_buffer": 1024,
    "server_buffer": 1024
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

def get_depth_values_sync(uv:list[int], timestamp:int, ip_addr:str, port:int, client_buffer:int, server_buffer:int) -> list[int] | str:
    '''Input format (uv): [u0, v0, u1, v1, u2, v2, ...]'''
    try:
        if len(uv) % 2 != 0:
            return f"[PARAMETERS ERROR] total given items: {len(uv)} - must be multiple of two"
        total_pairs = len(uv) // 2
        msg = pickle.dumps(uv+[timestamp])
        if len(msg) >= server_buffer:
            return f"[PARAMETERS ERROR] message size ({len(msg)}) >= server buffer size ({server_buffer}) - reduce the uv list size"
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip_addr, port))
        client.send(msg)
        response = pickle.loads(client.recv(client_buffer))
        if len(response) != total_pairs:
            return f"[PROCESSING OR NETWORK ERROR] total pairs sent ({total_pairs}) != response length ({len(response)})"
        return response
    except pickle.PickleError as e:
        return f"[(DE)SERIALIZATION ERROR] Corrupted packet: \'{str(e)}\'"
    except ConnectionRefusedError:
        return "[NETWORK ERROR] Connection refused"
    except ConnectionResetError:
        return "[NETWORK ERROR] Connection reset"
    except BrokenPipeError:
        return "[NETWORK ERROR] Connection closed"
    except BaseException as e:
        return "[UNKNOWN ERROR] "+str(e)
    finally:
        try:
            client.close()
        except UnboundLocalError:
            print("[WARN] No connection to close.")

def get_depth_values_sync_wrapper(uv:list[tuple[int]], timestamp:int, config:dict=CONFIG) -> list[int]:
    '''Input format: [(u0, v0), (u1, v1), ...]'''
    uv_flattened = flatten(uv)
    return get_depth_values_sync(
        uv = uv_flattened,
        timestamp = timestamp,
        ip_addr = config["IP_address"],
        port = config["port"],
        client_buffer = config["client_buffer"],
        server_buffer = config["server_buffer"]
    )
     

if __name__ == "__main__":
    import time
    # https://learn.microsoft.com/en-us/windows/win32/direct3d9/images/uvcoordinates.jpg
    test_data = [
        [(10, 10)]*100,
        [(10, 10)]*300,
        [],
        [(150, 150), (100, 100), (60, 60), (10, 10), (639, 479)],
        [(480, 640)] # must raise error
    ]
    while True:
        time.sleep(1)
        for pairs in test_data:
            print(f"Sending {pairs} ...")
            print("Received: ",get_depth_values_sync_wrapper(uv=pairs, timestamp=111))