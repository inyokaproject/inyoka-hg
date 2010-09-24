# -*- coding: utf-8 -*-
"""
    inyoka.utils.async
    ~~~~~~~~~~~~~~~~~~

    Utilities to better work on async webservers like gevent.wsgi.

    :copyright: 2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
try:
    import eventlet
except ImportError:
    eventlet = None


def get_file_descriptor(fname, mode='r', bufsize=-1):
    if eventlet:
        return eventlet.greenio.GreenPipe(fname, mode, bufsize)
    return open(fname, mode, bufsize)


#TODO: implement a silent and a non-silent version
def write_data_to_fd(fname, data, mode='w', bufsize=-1):
    fd = get_file_descriptor(fname, mode, bufsize)
    try:
        fd.write(data)
    finally:
        fd.close()
    return True
