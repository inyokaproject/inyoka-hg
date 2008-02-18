#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.create_templates
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Creates the standard templates of ubuntuusers.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
from inyoka.wiki.models import Page

note = """<@ if $arguments.0 @>
----
'''Anmerkung:''' <@ $arguments.0 @>
<@ endif @>"""

templates = {
    u'Archiviert': u"""{{|<title="Archivierte Anleitung">
Dieser Artikel wurde archiviert, da er - oder Teile daraus -
nur noch unter einer älteren Ubuntu-Version nutzbar ist. Diese
Anleitung wird vom Wiki-Team weder auf Richtigkeit überprüft
noch anderweitig gepflegt. Zusätzlich wurde der Artikel für
weitere Änderungen gesperrt.%s
|}}""" % note,
    u'Ausbaufähig': u"""{{|<title="Ausbaufähige Anleitung">
Dieser Anleitung fehlen noch einige Informationen. Wenn Du etwas
verbessern kannst, dann editiere den Beitrag, um die Qualität
des Wikis noch weiter zu verbessern.%s
|}}""" % note,
    u'Fehlerhaft': u"""{{|<title="Fehlerhafte Anleitung">
Diese Anleitung ist fehlerhaft. Wenn du weißt, wie du sie
ausbessern kannst, nimm dir bitte die Zeit und bessere sie aus.%s
|}}""" % note,
    u'Fortgeschritten': u"""{{|<title="Artikel für fortgeschrittene \
Anwender">
Dieser Artikel erfordert mehr Erfahrung im Umgang mit
Linux und ist daher nur für fortgeschrittene Benutzer
gedacht.
|}}""",
    u'Getestet': u"""{{|<title="Dieser Artikel wurde für die folgenden \
Ubuntu-Versionen getestet:">
<@ if $arguments contain 'dapper' @>
  * [:Ubuntu_Dapper_Drake:Ubuntu Dapper Drake 6.06]
<@ endif @><@ if $arguments contain 'edgy' @>
  * [:Ubuntu_Edgy_Eft:Ubuntu Edgy Eft 6.10]
<@ endif @><@ if $arguments contain 'feisty' @>
  * [:Ubuntu_Feisty_Fawn:Ubuntu Feisty Fawn 7.04]
<@ endif @><@ if $arguments contain 'gutsy' @>
  * [:Ubuntu_Gutsy_Gibbon:Ubuntu Gutsy Gibbon 7.10]
<@ endif @>
|}}""",
    u'Verlassen': u"""{{|<title="Verlassene Anleitung">
Dieser Artikel wurde von seinem Ersteller verlassen und wird
nicht mehr weiter von ihm gepflegt. Wenn Du den Artikel
fertigstellen oder erweitern kannst, dann bessere ihn bitte aus.%s
|}}""" % note,
    u'Pakete': u"""{{|<class="package-list">
Paketliste zum Kopieren:
{{|<class="bash">sudo apt-get install <@ $arguments join_with " " @>
|}}
{{|<class="bash">sudo aptitude install <@ $arguments join_with " " @>
|}}
|}}""",
    u'InArbeit': u"""<@ if $arguments.0 as stripped == "" or $arguments.0 matches_regex "(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})" @>
Dieser Artikel wird momentan
<@if $arguments.1 @>
von [http://ubuntuusers.de/users/<@ $arguments.1 @> <@ $arguments.1 @>]
<@ endif @>
überarbeitet.
<@ if $arguments.0 as stripped @>
Als Fertigstellungsdatum wurde der <@ $arguments.0 @> angegeben.
<@ else @> Solltest du dir nicht sicher sein, ob an dieser Anleitung noch gearbeitet wird, kontrolliere das Datum der letzten Änderung und entscheide, wie du weiter vorgehst.
<@ endif @>
----
'''Achtung''': Insbesondere heißt das, dass dieser Artikel noch nicht fertig ist und dass wichtige Teile fehlen oder sogar falsch sein können. Bitte diesen Artikel nicht als Anleitung für Problemlösungen benutzen!
<@ else @>
'''Parameterfehler''': Ungültiges Datum
<@ endif @> """
}

def create():
    for name, content in templates.iteritems():
        Page.objects.create(u'Wiki/Vorlagen/%s' % name,
                            u'# X-Preprocess: Page-Template\n%s' % content,
                            note=u'Vorlage automatisch erstellt')


if __name__ == '__main__':
    create()
