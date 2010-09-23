import gevent
import logging
import os
import signal
import sys
from development_settings import BASE_DOMAIN_NAME

bind = BASE_DOMAIN_NAME
backlog = 2048

workers = 5
worker_class = 'egg:gunicorn#sync'
worker_connections = 1000
timeout = 30
keepalive = 2

debug = False
spew = False

daemon = False
pidfile = None
umask = 0
user = 'ubuntu_de'
group = 'ubuntu_de'
tmp_upload_dir = '/tmp'

#
# Logging
#
# logfile - The path to a log file to write to.
#
# A path string. "-" means log to stdout.
#
# loglevel - The granularity of log output
#
# A string of "debug", "info", "warning", "error", "critical"
#

logfile = '-'
loglevel = 'debug'

proc_name = 'inyoka.gunicorn'


def after_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)" % worker.pid)

def before_fork(server, worker):
    pass

def before_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    def monitor():
        modify_times = {}
        while True:
            for module in sys.modules.values():
                path = getattr(module, "__file__", None)
                if not path: continue
                if path.endswith(".pyc") or path.endswith(".pyo"):
                    path = path[:-1]
                try:
                    modified = os.stat(path).st_mtime
                except:
                    continue
                if path not in modify_times:
                    modify_times[path] = modified
                    continue
                if modify_times[path] != modified:
                    logging.info("%s modified; restarting server", path)
                    os.kill(os.getpid(), signal.SIGHUP)
                    modify_times = {}
                    break
            gevent.sleep(1)

    gevent.Greenlet.spawn(monitor)
