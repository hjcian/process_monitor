import os
import sys
import csv
import psutil
import time
from datetime import datetime
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict

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

if __name__ == "__main__":
    parser = ArgumentParser(prog=str(__file__))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--name', '-n', dest='name', help='Process name for binding after searching.')
    group.add_argument('--pid', '-p', dest='pid', help='Process id (PID) for direct binding.', type=int)
    interval = 1.0
    parser.add_argument('--interval', '-i', default=interval, dest='interval', help='Interval (sec.) for monitoring. default: {} sec.'.format(interval), type=float)
    parser.add_argument('--dump', '-d', action="store_true", 
        help='dump metrics to file or not. filename syntax is: monitor-ProcName[_ProcName[_ProcName ...]].csv default: false')
    argv = parser.parse_args()

    tmp_pid = int(argv.pid) if argv.pid else None
    if tmp_pid != None and not psutil.pid_exists(tmp_pid):
        print("not found PID in system by given {}".format(tmp_pid))
        sys.exit(1)
    
    pids = []
    if tmp_pid: 
        pids = [tmp_pid]
    else: 
        pids = find_pid(argv.name)
    
    if not pids: 
        print("not match any process name by given '{}'".format(argv.name))
        sys.exit(1)

    procs = [ psutil.Process(pid) for pid in pids ]
    process_name = set()
    for idx, p in enumerate(procs):
        process_name.add(p.name())
        print("({}/{}) Find the PID of '{}' (pattern: {}) is {}".format(idx+1, len(procs), p.name(), argv.name, p.pid))
    interval = float(argv.interval)
    
    filename = "monitor-{}.csv".format("_".join(set(extractFileName(pname) for pname in process_name)))
    isNeedInit = not os.path.isfile(filename)

    executor = ThreadPoolExecutor(max_workers=len(procs))
    fout = open(filename, 'a', newline='') if argv.dump else None    
    writer = None
    while(1):
        future_to_pid = {executor.submit(monitor_process, p, interval): p.pid for p in procs}
        results = []
        for future in future_to_pid:
            pid = future_to_pid[future]
            result = future.result()
            results.append(result)
            print("\t".join(map(str, result.values())))
        print("\t".join(result))
        print("======")
        if argv.dump:
            if writer == None:
                writer = csv.DictWriter(fout, fieldnames=list(result.keys()))
                if isNeedInit:
                    writer.writeheader()
            if writer:
                writer.writerows(results)
            