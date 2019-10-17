import os
import sys
import csv
import psutil
from psutil._common import bytes2human
import time
from datetime import datetime
from argparse import ArgumentParser

def monitor_process(p, interval):    
    cpu_perc = p.cpu_percent(interval=interval)
    mem = p.memory_info()
    ts = round(time.time(), 1)
    print("{:<15}\t{}\t{}".format('time', 'CPU(%)', "MEM"))
    print("{:<15}\t{}\t{}".format(ts, cpu_perc, bytes2human(mem.rss)))
    return [ts, cpu_perc, mem.rss]

def monitor_process_metrics(p, interval, writer):
    tuples = monitor_process(p, interval)
    writer.writerow(tuples)

def find_pid(pname):
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        if pname.lower() in proc.info['name'].lower():
            return proc.info['pid']
    return None

def extractFileName(name):
    name = os.path.basename(name)
    name = os.path.splitext(name)[0]
    return name.lower()

if __name__ == "__main__":
    parser = ArgumentParser(prog=str(__file__))
    parser.add_argument('--name', '-n', dest='name', help='Process name for binding after searching.')
    parser.add_argument('--pid', '-p', dest='pid', help='Process id (PID) for direct binding.')
    interval = 0.5
    parser.add_argument('--interval', '-i', default=interval, dest='interval', help='Interval (sec.) for monitoring. default: {} sec.'.format(interval))
    argv = parser.parse_args()

    if not argv.pid and not argv.name:
        print("need PID or process name for binding.")
        sys.exit(1)
    pid = argv.pid or find_pid(argv.name)
    if pid == None or not psutil.pid_exists(int(pid)):
        if argv.name: print("not match any process name by given '{}'".format(argv.name))
        else: print("not found PID in system by given {}".format(pid))
        print("(On Ubuntu) please use 'ps aux | grep -i {}' to check your process is running.".format(argv.name))
        sys.exit(1)
    pid = int(pid)
    interval = argv.interval
    p = psutil.Process(pid)
    name = p.name()
    print("Find the PID of '{}' (pattern: {}) is {}".format(name, argv.name, pid))
    
    filename = "{}_{}.csv".format(extractFileName(name), pid)
    isNewFile = not os.path.isfile(filename)
    print(filename, isNewFile)

    fields = ['timestamp', 'CPU(%)', 'MEM(bytes)']    
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        if isNewFile:
             writer.writerow(fields)
        while(1):
            monitor_process_metrics(p, interval, writer)