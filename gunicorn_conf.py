import logging
import os
import signal
import socket
import sys

# override pickle
sys.modules['cPickle'] = __import__('pickle')

#bind = BASE_DOMAIN_NAME
bind = '0.0.0.0:8000'
backlog = 2048

# default workers, special configuration is below
workers = 5

# special server config
_hostname = socket.gethostname()
if _hostname == 'oya':
    workers = 2
elif _hostname == 'unkul':
    workers = 4
elif _hostname == 'dongo':
    workers = 6


worker_class = 'egg:meinheld#gunicorn_worker'
worker_connections = 1000
timeout = 30
keepalive = 2
preload = True

debug = False
spew = False

daemon = True
pidfile = '/tmp/gunicorn_inyoka.pid'
umask = 0
user = 'ubuntu_de'
group = 'ubuntu_de'
tmp_upload_dir = None

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

logfile = '/var/log/www/gunicorn_de/error.log'
#logfile = '-'
loglevel = 'debug'

proc_name = 'ubuntuusers'


def after_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)" % worker.pid)

def before_fork(server, worker):
    pass

def before_exec(server):
    server.log.info("Forked child, re-executing.")

#def when_ready(server):
#    def monitor():
#        modify_times = {}
#        while True:
#            path = 'gunicorn.trigger'
#            try:
#                modified = os.stat(path).st_mtime
#            except:
#                continue
#            if path not in modify_times:
#                modify_times[path] = modified
#                continue
#            if modify_times[path] != modified:
#                logging.info("%s modified; restarting server", path)
#                os.kill(os.getpid(), signal.SIGHUP)
#                modify_times = {}
#            gevent.sleep(1)
#
#    import gevent
#    gevent.spawn(monitor)
