# -*- coding: utf-8 -*-
"""
    inyoka.tasks
    ~~~~~~~~~~~~

    Various tasks that needs to be done using celery and our amqp backend.

    :copyright: 2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import os
import re
import shutil
import urllib2
from email.mime.text import MIMEText
from email.header import Header
from cStringIO import StringIO
from tempfile import TemporaryFile
from hashlib import sha1
from itertools import ifilter
from inyoka.conf import settings
from inyoka.utils.urls import href, is_external_target
from subprocess import Popen, PIPE
from celery.decorators import task


@task
def generate_thumbnail(location, dimension, destination, force=False, external=False):
    # check if we already have a thumbnail for this hash
    if os.path.exists(os.path.join(settings.MEDIA_ROOT, destination)):
        return destination

    # get the source stream. if the location is an url we load it using
    # the urllib2 and convert it into a StringIO so that we can fetch the
    # data multiple times. If we are operating on a wiki page we load the
    # most recent revision and get the attachment as stream.
    if external:
        try:
            src = StringIO(urllib2.urlopen(location).read())
        except IOError:
            return
    else:
        src = open(os.path.join(settings.MEDIA_ROOT, location), 'rb')


    # convert into the PNG and JPEG using imagemagick. Right now this
    # rethumbnails for every format. This should be improved that it
    # generates the thumbnail first into a raw format and convert to
    # png/jpeg from there.
    base_params = [os.path.join(settings.IMAGEMAGICK_PATH, 'convert'),
                   '-', '-resize', dimension, '-sharpen', '0.5', '-format']

    result = None
    format, quality = ('png', '100')
    try:
        dst = TemporaryFile()
        client = Popen(base_params + [format, '-quality', quality, '-'],
                       stdin=PIPE, stdout=dst, stderr=PIPE)
        src.seek(0)
        shutil.copyfileobj(src, client.stdin)
        client.stdin.close()
        client.stderr.close()
        if client.wait():
            return
        dst.seek(0, 2)
        result = (dst, format)
    except (IOError, OSError):
        pass
    finally:
        src.close()

    # Return none if there were errors in thumbnail rendering, that way we can
    # raise 404 exceptions instead of raising 500 exceptions for the user.
    if not result:
        return None

    # select the smaller of the two versions and copy and get the filename for
    # that format. Then ensure that the target folder exists
    fp, extension = result
    filename = '%s.%s' % (
        destination.rsplit('.', 1)[0],
        extension
    )
    real_filename = os.path.join(settings.MEDIA_ROOT, filename)
    try:
        os.makedirs(os.path.dirname(real_filename))
    except OSError:
        pass

    # rewind the descriptor and copy the data over to the target filename.
    fp.seek(0)
    f = open(real_filename, 'wb')
    try:
        shutil.copyfileobj(fp, f)
    finally:
        fp.close()
        f.close()


@task
def send_mail(subject, message_, from_, to):
    assert len(to) == 1
    if to[0].endswith('.invalid'):
        return

    message = u'From: %s\nTo: %s' % (from_ , to[0])
    # Ignore für den Fall, dass wir hier blöde emailadressen bekommen…
    # TODO: non ascii adressen erlauben
    message = message.encode('ascii', 'ignore')
    message += '\nSubject: ' + Header(subject, 'utf-8', header_name='Subject').encode() + '\n'
    message += MIMEText(message_.encode('utf-8'), _charset='utf-8').as_string()

    try:
        proc = Popen(['/usr/sbin/sendmail', '-t'], stdin=PIPE)
        proc.stdin.write(message)
        proc.stdin.close()
        # replace with os.wait() in a outer level to not wait to much?!
        proc.wait()
    except OSError:
        if settings.DEBUG:
            print message
        else:
            raise
