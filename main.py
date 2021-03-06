import os
import sys
import csv
import psutil
import time
from datetime import datetime
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import threading

def bytes2MiB(b):
    b = b / 1024.0 / 1024.0
    return "{:.1f}".format(b)

def monitor_process(p, interval):    
    cpu_perc = p.cpu_percent(interval=interval)
    mem = p.memory_info()
    ts = round(time.time(), 1)
    return OrderedDict([
        ("pid", p.pid),
        ("ts", ts),
        ("cpu", cpu_perc),
        ("mem", bytes2MiB(mem.rss)),
    ])

def find_pid(pattern):
    pattern = pattern.lower()
    groupPID = []
    for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
        proc_name = proc.info['name'] or ""
        proc_cmdline = " ".join(proc.info['cmdline'])
        if pattern in proc_name.lower() or pattern in proc_cmdline.lower():
            groupPID.append(proc.info['pid'])
    return groupPID

def extractFileName(name):
    name = os.path.basename(name)
    name = os.path.splitext(name)[0]
    return name.lower()


def monitor_system(interval=1):
    ts = round(time.time(), 1)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    metrics = [
        ("ts", ts),
        ("mem_total", bytes2MiB(mem.total)),
        ("mem_available", bytes2MiB(mem.available)),
        ("mem_used", bytes2MiB(mem.used)),
        ("mem_free", bytes2MiB(mem.free)),
        ("swap_total", bytes2MiB(swap.total)),
        ("swap_used", bytes2MiB(swap.used)),
        ("swap_free", bytes2MiB(swap.free)),
        ("swap_percent", bytes2MiB(swap.percent)),
    ]
    cpus = psutil.cpu_percent(percpu=True, interval=interval)
    metrics = metrics + [ 
        (f"cpu_{idx}", cpu)
        for idx, cpu in enumerate(cpus)]
    return OrderedDict(metrics)

class SystemMonitor(object):
    def __init__(self, dump=False, fname=None):
        self.writer = None
        self.dump = dump
        if self.dump:
            self.filename = fname or "monitor-system.csv"
            self.isNeedInit = not os.path.isfile(self.filename)
            self.fout = open(self.filename, 'a', newline='') if dump else None 

    def _append2file(self, results):
        if self.dump:
            if self.writer == None:
                self.writer = csv.DictWriter(self.fout, fieldnames=list(results[0].keys()))
                if self.isNeedInit:
                    self.writer.writeheader()
            if self.writer:
                self.writer.writerows(results)

    def start(self, interval=1):
        while True:
            result = monitor_system(interval)
            print(result)
            print("================================")
            self._append2file([result])

class ProcessMonitor(object):
    def __init__(self, pids=None, pattern=None, dump=False, fname=None):        
        if pids != None:
            for pid in pids:
                if not  psutil.pid_exists(pid):
                    raise KeyError("not found PID in system (given: {})".format(pid))        
        
        pids = pids if pids else find_pid(pattern)
        
        if not pids: 
            raise KeyError("not match any process name by given '{}'".format(pattern))
        
        selfPID = os.getpid()
        print("selfPID: ", selfPID)
        self.procs = [ psutil.Process(pid) for pid in pids if pid != selfPID ]

        filename_concate = []        
        for idx, p in enumerate(self.procs):            
            p_pid = p.pid
            p_name = p.name()
            filename_concate.append(f"{extractFileName(p_name)}-{p_pid}")
            p_cmdline = " ".join(p.cmdline())
            print("({}/{}) Find out th PID ({}) matched pattern. (cmdline: {})".format(idx+1, len(self.procs), p_pid, p_cmdline))
        filename_concate = "_".join(filename_concate)

        self.executor = ThreadPoolExecutor(max_workers=len(self.procs))        

        self.filename = None
        self.isNeedInit = None
        self.fout = None
        self.dump = dump
        self.writer = None
        if self.dump:
            self.filename = fname or f"monitor_{pattern or 'EMPTY'}_{filename_concate}.csv"
            self.isNeedInit = not os.path.isfile(self.filename)
            self.fout = open(self.filename, 'a', newline='') if dump else None    

    def _append2file(self, results):
        if self.dump:
            if self.writer == None:
                self.writer = csv.DictWriter(self.fout, fieldnames=list(results[0].keys()))
                if self.isNeedInit:
                    self.writer.writeheader()
            if self.writer:
                self.writer.writerows(results)

    def start(self, interval):
        while True:
            future_to_pid = { self.executor.submit(monitor_process, p, interval): p.pid for p in self.procs }
            results = []
            for future in future_to_pid:
                result = future.result()
                results.append(result)
                print("\t".join(map(str, result.values())))
            print("\t".join(result))
            print("======")
            self._append2file(results)


if __name__ == "__main__":
    parser = ArgumentParser(prog=str(__file__))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--name', '-n', dest='name', help='Process name for binding after searching.')
    group.add_argument('--pid', '-p', nargs='+', dest='pid', help='Process id (take 1 or more) for direct binding.', type=int)
    group.add_argument('--dump-system', '-s', action="store_true", 
        help='dump system metrics or not. default: false')
    # parser.add_argument('--interval', '-i', default=interval, dest='interval', help='Interval (sec.) for monitoring. default: {} sec.'.format(interval), type=float)
    parser.add_argument('--dump', '-d', action="store_true", 
        help='dump metrics to file or not. default: false')
    parser.add_argument('--file-name', '-f', 
        help='specify file name for storing dump file or use default syntax.')
    parser.add_argument('--interval', '-i', dest='interval', default=1, help='Monitor interval. default: 1 sec.', type=int)
    argv = parser.parse_args()

    interval = float(argv.interval)
    filename = argv.file_name
    if argv.dump_system:
        sm = SystemMonitor(dump=argv.dump, fname=filename)
        sm.start(interval)
    else:
        pm = ProcessMonitor(pids=argv.pid, pattern=argv.name, dump=argv.dump, fname=filename)
        pm.start(interval)
