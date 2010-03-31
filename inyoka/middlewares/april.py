# -*- coding: utf8 -*-
from inyoka.utils.flashing import flash, unflash

class AprilFoolMiddleware(object):
    def process_request(self, request):
        if u'chrome' not in request.META.get('HTTP_USER_AGENT', u'').lower():
            unflash('aprilfool')
            flash(u'Du benutzt einen nicht unterstützten Browser! Bitte '
                  u'lade dir <a href="http://www.google.com/chrome">Chrome'
                  u'</a> herunter.', False, classifier='aprilfool')
