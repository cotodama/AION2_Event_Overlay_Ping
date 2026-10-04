"""Bounded TCP measurements; workers never call Tk or persist latency history."""
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def measure(server):
    start=time.perf_counter()
    try:
        with socket.create_connection((server['host'],int(server['port'])),timeout=1.5):
            return (time.perf_counter()-start)*1000, ''
    except OSError as exc:
        return None, str(exc)

def latency_color(value):
    return '#40ff68' if value is not None and value < 100 else '#ff9b42' if value is not None and value < 200 else '#ff5252'

def scan(servers, generation, output, stop):
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(measure,s):s for s in servers if not stop.is_set()}
        for future in as_completed(futures):
            if stop.is_set():
                for pending in futures: pending.cancel()
                break
            value,error=future.result()
            output.put(('ping',generation,futures[future]['id'],value,error))
    output.put(('scan_done',generation))
