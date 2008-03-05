#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.create_templates
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Creates the standard templates of ubuntuusers.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
from inyoka.wiki.models import Page
from inyoka.utils.storage import storage


note = """<@ if $arguments.0 @>
----
'''Anmerkung:''' <@ $arguments.0 @>
<@ endif @>"""


def simple_box(name, class_):
    return u"""{{|<title="%s" class="box %s">
<@ $arguments @>
|}}""" % (name, class_)


templates = {
    u'Archiviert': u"""{{|<title="Archivierte Anleitung">
Dieser Artikel wurde archiviert, da er - oder Teile daraus -
nur noch unter einer älteren Ubuntu-Version nutzbar ist. Diese
Anleitung wird vom Wiki-Team weder auf Richtigkeit überprüft
noch anderweitig gepflegt. Zusätzlich wurde der Artikel für
weitere Änderungen gesperrt.%s
|}}""" % note,
    u'Ausbaufähig': u"""{{|<title="Ausbaufähige Anleitung"
                            class="box improvable">
Dieser Anleitung fehlen noch einige Informationen. Wenn Du etwas
verbessern kannst, dann editiere den Beitrag, um die Qualität
des Wikis noch weiter zu verbessern.%s
|}}""" % note,
    u'Fehlerhaft': u"""{{|<title="Fehlerhafte Anleitung"
                           class="box fixme">
Diese Anleitung ist fehlerhaft. Wenn du weißt, wie du sie
ausbessern kannst, nimm dir bitte die Zeit und bessere sie aus.%s
|}}""" % note,
    u'Fortgeschritten': u"""{{|<title="Artikel für fortgeschrittene Anwender"
                                class="box advanced">
Dieser Artikel erfordert mehr Erfahrung im Umgang mit
Linux und ist daher nur für fortgeschrittene Benutzer
gedacht.
|}}""",
    u'Getestet': u"""{{|<title="Dieser Artikel wurde für die folgenden
Ubuntu-Versionen getestet:" class="box tested_for">
<@ if $arguments contain 'general' @>
Dieser Artikel ist größtenteils für alle Ubuntu-Versionen gültig.
<@ else @>
<@ if $arguments contain 'dapper' @>
  * [:Ubuntu_Dapper_Drake:Ubuntu Dapper Drake 6.06]
<@ endif @><@ if $arguments contain 'edgy' @>
  * [:Ubuntu_Edgy_Eft:Ubuntu Edgy Eft 6.10]
<@ endif @><@ if $arguments contain 'feisty' @>
  * [:Ubuntu_Feisty_Fawn:Ubuntu Feisty Fawn 7.04]
<@ endif @><@ if $arguments contain 'gutsy' @>
  * [:Ubuntu_Gutsy_Gibbon:Ubuntu Gutsy Gibbon 7.10]
<@ endif @>
<@ endif @>
|}}""",
    u'Verlassen': u"""{{|<title="Verlassene Anleitung"
                          class="box left">
Dieser Artikel wurde von seinem Ersteller verlassen und wird
nicht mehr weiter von ihm gepflegt. Wenn Du den Artikel
fertigstellen oder erweitern kannst, dann bessere ihn bitte aus.%s
|}}""" % note,
    u'Pakete': u"""{{|<class="package-list">
Paketliste zum Kopieren:
[[Vorlage(Wiki/Vorlagen/Befehl, 'sudo apt-get install <@ $arguments join_with " " @>')]]
[[Vorlage(Wiki/Vorlagen/Befehl, 'sudo aptitude install <@ $arguments join_with " " @>')]]
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
<@ endif @> """,
    u'Befehl': u"""{{|<class="bash"><@ $arguments as array_of_lines join_with('[[BR]]') @>
|}}""",
    u'Tasten': u"""
<@ for $key in $arguments split_by "+" @>
<@ if ['hash','#'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/hash.png)]]
<@ elseif ['^'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/zirklumflex.png)]]
<@ elseif ['.'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/fullstop.png)]]
<@ elseif ['<'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/lt.png)]]
<@ elseif ['plus'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/plus.png)]]
<@ elseif [','] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/comma.png)]]
<@ elseif ['alt'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/alt.png)]]
<@ elseif ['fn'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/fn.png)]]
<@ elseif ['pos1','pos 1','home'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/home.png)]]
<@ elseif ['ende','end'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/end.png)]]
<@ elseif ['return','enter','eingabe'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/enter.png)]]
<@ elseif ['','space','leerschritt','leerzeichen','leer','leertaste'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/space.png)]]
<@ elseif ['up','hoch','rauf','pfeil hoch','pfeil-hoch','auf'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/up.png)]]
<@ elseif ['backspace','löschen','rückschritt'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/backspace.png)]]
<@ elseif ['down','runter','pfeil runter','pfeil-ab','ab'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/down.png)]]
<@ elseif ['left','links','pfeil links','pfeil-links'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/left.png)]]
<@ elseif ['right','rechts','pfeil rechts','pfeil-rechts'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/right.png)]]
<@ elseif ['bild auf','bild-auf','bild-rauf'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/pgup.png)]]
<@ elseif ['bild ab','bild-ab','bild-runter'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/pgdown.png)]]
<@ elseif ['strg','ctrl'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/ctrl.png)]]
<@ elseif ['alt gr','altgr'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/altgr.png)]]
<@ elseif ['umschalt','umsch','shift'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/shift.png)]]
<@ elseif ['feststell','feststelltaste','groß','caps'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/caps.png)]]
<@ elseif ['entf','delete','entfernen','del'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/del.png)]]
<@ elseif ['win','windows'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/win.png)]]
<@ elseif ['tab','tabulator'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/tab.png)]]
<@ elseif ['esc','escape'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/esc.png)]]
<@ elseif ['druck','print'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/print.png)]]
<@ elseif ['minus','-'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/dash.png)]]
<@ elseif ['apple','mac','apfel'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/apple.png)]]
<@ elseif ['einfg','ins'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/ins.png)]]
<@ elseif ['ß','s'] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/sz.png)]]
<@ elseif ['`',"'"] contains $key as lowercase @>[[Bild(Wiki/Vorlagen/Tasten/tick.png)]]
<@ elseif $key matches_regex "^[a-zA-Z0-9]{1}$" @>[[Bild(Wiki/Vorlagen/Tasten/<@ $key as lowercase @>.png)]]
<@ elseif $key as lowercase matches_regex "^f[0-9]{1,2}$" @>[[Bild(Wiki/Vorlagen/Tasten/<@ $key as lowercase @>.png)]]
<@ endif @>
<@ endfor @>""",
    u'Wissen': u"""{{|<title="Diese Anleitung setzt die Kenntnis folgender Seiten voraus:" class="box knowledge">
<@ for $arg in $arguments @>
 * [[Anker(source-<@ $loop.index @>)]]<@ $loop.index @>: <@ $arg @>
<@ endfor @>
|}}""",
    u'Warnung': simple_box(u'Achtung!', 'warning'),
    u'Hinweis': simple_box(u'Hinweis:', 'notice'),
    u'Experten': simple_box(u'Experten-Info:', 'experts'),
}

def create_page_templates():
    for name, content in templates.iteritems():
        Page.objects.create(u'Wiki/Vorlagen/%s' % name, content,
                            note=u'Vorlage automatisch erstellt')

    # attach key images to Tasten macro
    pth = os.path.join(os.path.dirname(__file__), 'keys')
    for name in os.listdir(pth):
        f = file(os.path.join(pth, name))
        name = name.replace('key-', '')
        Page.objects.create(u'Wiki/Vorlagen/Tasten/%s' % name,
                    u'', note=u'Vorlage automatisch erstellt',
                    attachment=f.read(), attachment_filename=name)
        f.close()


def create_markup_stylesheet():
    storage['markup_styles'] = u""""""


def create_smilies():
    smiley_map = {
        ':D':  'biggrin.png',
        ':)':  'happy.png',
        ':(':  'sad.png',
        ':o':  'surprised.png',
        '8-o': 'eek.png',
        ':?':  'confused.png',
        '8(':  'cool.png',
        ':lol:': 'lol.png',
        ':x': 'angry.png',
        ':P': 'razz.png',
        ':-$': 'redface.gif',
        ';-(': 'cry.png',
        ']:-(': 'evil.png',
        ']:-)': 'twisted.png',
        ':roll': 'rolleyes.gif',
        ';)': 'wink.png',
        ':|': 'neutral.png',
        ':->': 'smile.png',
        'O:-)': 'angel.png',
        ':[]': 'grin.png',
        u'§)': 'canny.png',
        ':-x': 'kiss.png',
        '8-}': 'monkey.png',
        ':!:': 'exclaim.png',
        ':?:': 'question.png',
        ':idea:': 'idea.png',
        ':arrow:': 'arrow.png',
        '<3': 'favorite.png',
    }
    text = u'''# X-Behave: Smiley-Map
{{{
%s
}}}''' % u'\n'.join(u'%s = %s' % (key, 'Wiki/Smilies/%s' % img)
                    for key, img in smiley_map.iteritems())
    Page.objects.create(u'Wiki/Smilies', text,
                        note=u'Smilies automatisch erstellt')
    pth = os.path.join(os.path.dirname(__file__), 'smilies')
    for key, img in smiley_map.iteritems():
        f = file(os.path.join(pth, img))
        Page.objects.create(u'Wiki/Smilies/%s' % img,
                    u'', note=u'Smiley automatisch erstellt',
                    attachment=f.read(), attachment_filename=img)
        f.close()


if __name__ == '__main__':
    create_page_templates()
    create_markup_stylesheet()
    create_smilies()
