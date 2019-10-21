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

def find_pid(pname):
    groupPID = []
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        if pname.lower() in proc.info['name'].lower():
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
        ("mem_total", mem.total),
        ("mem_available", mem.available),
        ("mem_used", mem.used),
        ("mem_free", mem.free),
        ("swap_total", swap.total),
        ("swap_used", swap.used),
        ("swap_free", swap.free),
        ("swap_percent", swap.percent),
    ]
    metrics = [ (name, bytes2MiB(byte)) for (name, byte) in metrics ]

    cpus = psutil.cpu_percent(percpu=True, interval=interval)
    metrics = metrics + [ 
        (f"cpu_{idx}", cpu)
        for idx, cpu in enumerate(cpus)]
    return OrderedDict(metrics)

class SystemMonitor(object):
    def __init__(self, dump=False):
        self.writer = None
        self.dump = dump
        if self.dump:
            self.filename = "monitor-system.csv"
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
    def __init__(self, pid=None, proc_name=None, dump=False):        
        if pid != None and not psutil.pid_exists(pid):
            raise KeyError("not found PID in system (given: {})".format(pid))        
        
        pids = [ pid ] if pid else find_pid(proc_name)
        
        if not pids: 
            raise KeyError("not match any process name by given '{}'".format(proc_name))
        
        self.procs = [ psutil.Process(pid) for pid in pids ]

        process_name_set = set()
        for idx, p in enumerate(self.procs):
            process_name_set.add(p.name())
            print("({}/{}) Find the PID of '{}' (pattern: {}) is {}".format(idx+1, len(self.procs), p.name(), proc_name, p.pid))
    
        self.executor = ThreadPoolExecutor(max_workers=len(self.procs))        

        self.filename = None
        self.isNeedInit = None
        self.fout = None
        self.dump = dump
        self.writer = None
        if self.dump:
            self.filename = "monitor-{}.csv".format("_".join(set(extractFileName(pname) for pname in process_name_set)))
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
    group.add_argument('--pid', '-p', dest='pid', help='Process id (PID) for direct binding.', type=int)
    group.add_argument('--dump-system', '-s', action="store_true", 
        help='dump system metrics or not. default: false')
    interval = 1.0
    parser.add_argument('--interval', '-i', default=interval, dest='interval', help='Interval (sec.) for monitoring. default: {} sec.'.format(interval), type=float)
    parser.add_argument('--dump', '-d', action="store_true", 
        help='dump metrics to file or not. filename syntax is: monitor-ProcName[_ProcName[_ProcName ...]].csv default: false')
    
    argv = parser.parse_args()
    interval = float(argv.interval)

    if argv.dump_system:
        sm = SystemMonitor(dump=argv.dump)
        sm.start(interval)
    else:
        pm = ProcessMonitor(pid=argv.pid, proc_name=argv.name, dump=argv.dump)
        pm.start(interval)

    


    
            