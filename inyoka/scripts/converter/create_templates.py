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
<@ if $arguments contain 'gutsy' @>
  * [:Gutsy_Gibbon:Ubuntu Gutsy Gibbon 7.10]
<@ endif @><@ if $arguments contain 'feisty' @>
  * [:Feisty_Fawn:Ubuntu Feisty Fawn 7.04]
<@ endif @><@ if $arguments contain 'edgy' @>
  * [:Edgy_Eft:Ubuntu Edgy Eft 6.10]
<@ endif @><@ if $arguments contain 'dapper' @>
  * [:Dapper_Drake:Ubuntu Dapper Drake 6.06]
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
    u'InArbeit': u"""{{|<class="box workinprogress" title="Artikel in Arbeit">Dieser Artikel wird momentan <@if $arguments.1 @>von [user:<@ $arguments.1 @>:]<@ endif @> überarbeitet.
<@ if $arguments.0 matches_regex "(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})" @>
Als Fertigstellungsdatum wurde der <@ $arguments.0 @> angegeben.
<@ else @>
Solltest du dir nicht sicher sein, ob an dieser Anleitung noch gearbeitet wird, kontrolliere das Datum der letzten Änderung und entscheide, wie du weiter vorgehst.
<@ endif @>
----
'''Achtung''': Insbesondere heißt das, dass dieser Artikel noch nicht fertig ist und dass wichtige Teile fehlen oder sogar falsch sein können. Bitte diesen Artikel nicht als Anleitung für Problemlösungen benutzen!|}}""",
    u'Befehl': u"""{{|<class="bash">{{{<@ $arguments @> }}}|}}""",
    u'Tasten': u"""<@ for $key in $arguments split_by "+" @>
<@ if $loop.first @><@ else @> + <@ endif @>
[[SPAN("<@ if $key matches_regex '^[a-zA-Z0-9]{1}$' @><@ $key as uppercase @>
<@ elseif $key as lowercase matches_regex '^f[0-9]{1,2}$' @><@ $key as uppercase @>
<@ elseif ['hash','#'] contains $key as lowercase @>#
<@ elseif ['^', '.', '<', ',', 'alt', 'fn'] contains $key as lowercase @><@ $key as title @>
<@ elseif $key == 'plus' @>+
<@ elseif ['pos1','pos 1','home'] contains $key as lowercase @>Pos 1
<@ elseif ['ende','end'] contains $key as lowercase @>Ende
<@ elseif ['return','enter','eingabe'] contains $key as lowercase @>⏎
<@ elseif ['space','leerschritt','leerzeichen','leer','leertaste'] contains $key as lowercase @>
<@ elseif ['up','hoch','rauf','pfeil hoch','pfeil-hoch','auf'] contains $key as lowercase @>↑
<@ elseif ['backspace','löschen','rückschritt'] contains $key as lowercase @>⌫
<@ elseif ['down','runter','pfeil runter','pfeil-ab','ab'] contains $key as lowercase @>↓
<@ elseif ['left','links','pfeil links','pfeil-links'] contains $key as lowercase @>←
<@ elseif ['right','rechts','pfeil rechts','pfeil-rechts'] contains $key as lowercase @>→
<@ elseif ['bild auf','bild-auf','bild-rauf'] contains $key as lowercase @>Bild ↑
<@ elseif ['bild ab','bild-ab','bild-runter'] contains $key as lowercase @>Bild ↓
<@ elseif ['strg','ctrl'] contains $key as lowercase @>Strg
<@ elseif ['alt gr','altgr'] contains $key as lowercase @>Alt Gr
<@ elseif ['umschalt','umsch','shift'] contains $key as lowercase @>⇧
<@ elseif ['feststell','feststelltaste','groß','caps'] contains $key as lowercase @>⇩
<@ elseif ['entf','delete','entfernen','del'] contains $key as lowercase @>Entf
<@ elseif ['win','windows'] contains $key as lowercase @>Windows
<@ elseif ['tab','tabulator'] contains $key as lowercase @>Tab ⇆
<@ elseif ['esc','escape'] contains $key as lowercase @>Esc
<@ elseif ['druck','print'] contains $key as lowercase @>Druck
<@ elseif ['minus','-'] contains $key as lowercase @>-
<@ elseif ['apple','mac','apfel'] contains $key as lowercase @>⌘
<@ elseif ['einfg','ins'] contains $key as lowercase @>Einfg
<@ elseif ['ß','ss'] contains $key as lowercase @>ß
<@ elseif ['`','\''] contains $key @>\`
<@ endif @>", class_='key')]]
<@ endfor @>""",
    u'Wissen': u"""{{|<title="Diese Anleitung setzt die Kenntnis folgender Seiten voraus:" class="box knowledge">
<@ for $arg in $arguments join_with '\n' split_by '\n' @>
 1. [[Anker(source-<@ $loop.index @>)]] <@ $arg @>
<@ endfor @>
|}}""",
    u'Warnung': simple_box(u'Achtung!', 'warning'),
    u'Hinweis': simple_box(u'Hinweis:', 'notice'),
    u'Experten': simple_box(u'Experten-Info:', 'experts'),
}

interwikis = u'''
# X-Behave: Interwiki-Map
{{{
isbn = http://bookzilla.de/shop/action/advancedSearch?action=search&isbn=
ubuntu = https://wiki.ubuntu.com/
google = http://www.google.de/search?q=
googlelinux = http://www.google.de/linux?q=
wikipedia = http://de.wikipedia.org/wiki/
wikipedia_en = http://en.wikipedia.org/wiki/
moinmoin = http://moinmoin.wikiwikiweb.de/
bug = https://bugs.launchpad.net/bugs/
}}}
'''

def create_page_templates():
    for name, content in templates.iteritems():
        Page.objects.create(u'Wiki/Vorlagen/%s' % name, content,
                            note=u'Vorlage automatisch erstellt')

    # attach key images to Tasten macro
    #pth = os.path.join(os.path.dirname(__file__), 'keys')
    #for name in os.listdir(pth):
    #    f = file(os.path.join(pth, name))
    #    name = name.replace('key-', '')
    #    Page.objects.create(u'Wiki/Vorlagen/Tasten/%s' % name,
    #                u'', note=u'Vorlage automatisch erstellt',
    #                attachment=f.read(), attachment_filename=name)
    #    f.close()


def create_markup_stylesheet():
    storage['markup_styles'] = u"""tr.titel {
    font-weight: bold;
    background: #E2C890;
    color: #000000;
    text-align: center;
}

tr.kopf {
    font-weight: bold;
    background: #F9EAAF;
    color: #000000;
}

tr.trennzeile {
    background: #DDDDDD;
    color: #000000;
}

tr.highlight {
    background: #EEEEEE;
    color: #000000;
}

tr.verlauf {
    font-weight: bold;
    color: #000000;
    background-image: url(http://static.ubuntuusers.de/img/wiki/heading.png);
    text-align: center;
}

/* Tabellen Deko KDE ---- */
tr.kde-titel {
    font-weight: bold;
    background: #013397;
    color: white;
    text-align: center;
}

tr.kde-kopf {
    font-weight: bold;
    background: #0169C9;
    color: white;
}

tr.kde-highlight {
    background: #AACCEE;
    color: #000000;
}

/* Tabellen Deko Xfce ---- */
tr.xfce-titel {
    font-weight: bold;
    background: #B3DEFD;
    color:#000000;
    text-align: center;
}

tr.xfce-kopf {
    font-weight: bold;
    background: #EFEFEF;
    color: #000000;
}

tr.xfce-highlight {
    background: #EFEFEF;
    color: #000000;
}

/* Tabellen Deko Edubuntu ---- */
tr.edu-titel {
    font-weight: bold;
    background: #d41308;
    color: white;
    text-align: center;
}

tr.edu-kopf {
    font-weight: bold;
    background: #f1480e;
    color: white;
}

tr.edu-highlight {
    background: #f68b11;
    color: #000000;
}

/* Tabellen Deko ubuntustudio ---- */
tr.studio-titel {
    font-weight: bold;
    background: #171717;
    color:#009bf9;
    text-align: center;
}

tr.studio-kopf {
    font-weight: bold;
    background: #525252;
    color:#009bf9;
}

tr.studio-highlight {
    background: #171717;
    color:#FFFFFF;
}

"""


def create_smilies():
    smiley_map = {
         '8)': 'cool.png',
         '8-)': 'cool.png',
         ':cool:': 'cool.png',
         ':(': 'sad.png',
         ':-(': 'sad.png',
         ':sad:': 'sad.png',
         ':)': 'happy.png',
         ':-)': 'happy.png',
         ':smile:': 'happy.png',
         ':?': 'confused.png',
         ':-?': 'confused.png',
         ':???:': 'confused.png',
         u'§)': 'canny.png',
         '<3': 'favorite.png',
         '8-o': 'eek.png',
         ':shock:': 'eek.png',
         '8-}': 'monkey.png',
         ':-x': 'kiss.png',
         ':roll': 'rolleyes.gif',
         ';-(': 'cry.png',
         ':cry:': 'cry.png',
         '{dl}': 'download.png',
         ':[]': 'grin.png',
         ':o': 'surprised.png',
         ':-o': 'surprised.png',
         ':eek:': 'surprised.png',
         ':?:': 'question.png',
         ':arrow:': 'arrow.png',
         ':|': 'neutral.png',
         ':-|': 'neutral.png',
         ':neutral:': 'neutral.png',
         ']:-(': 'evil.png',
         ']:-)': 'twisted.png',
         ':x': 'angry.png',
         ':-x': 'angry.png',
         ':mad:': 'angry.png',
         'O:-)': 'angel.png',
         ';)': 'wink.png',
         ';-)': 'wink.png',
         ':wink:': 'wink.png',
         ':D': 'biggrin.png',
         ':-D': 'biggrin.png',
         ':grin:': 'biggrin.png',
         ':mrgreen:': 'biggrin.png',
         ':-$': 'redface.gif',
         ':oops:': 'redface.gif',
         '{*}': 'ubuntu.png',
         ':->': 'smile.png',
         ':idea:': 'idea.png',
         ':!:': 'exclaim.png',
         ':lol:': 'lol.png',
         ':P': 'razz.png',
         ':-P': 'razz.png',
         ':razz:': 'razz.png',
    }

    pth = os.path.join(os.path.dirname(__file__), 'smilies')
    for img in set(smiley_map.values()):
        f = file(os.path.join(pth, img))
        Page.objects.create(u'Wiki/Smilies/%s' % img,
                    u'', note=u'Smiley automatisch erstellt',
                    attachment=f.read(), attachment_filename=img)
        f.close()

    # create flags
    pth = os.path.join(os.path.dirname(__file__), 'flags')
    flags = {}
    for name in os.listdir(pth):
        f = file(os.path.join(pth, name))
        name = name.replace('flag-', '')
        Page.objects.create(u'Wiki/Flaggen/%s' % name,
                    u'', note=u'Flagge automatisch erstellt',
                    attachment=f.read(), attachment_filename=name)
        f.close()
        flags[name.split('.')[0]] = u'Wiki/Flaggen/%s' % name

    smiley_text = u'''# X-Behave: Smiley-Map
{{{
%s
}}}''' % u'\n'.join(u'%s = %s' % (key, 'Wiki/Smilies/%s' % img)
                    for key, img in smiley_map.iteritems())
    flag_text = u'''# X-Behave: Smiley-Map
{{{
%s
}}}''' % u'\n'.join(u'{%s} = %s' % (flag, img)
                    for flag, img in flags.iteritems())
    Page.objects.create(u'Wiki/Smilies', smiley_text,
                        note=u'Smilies automatisch erstellt')
    Page.objects.create(u'Wiki/Flaggen', flag_text,
                        note=u'Flaggen automatisch erstellt')


def create_interwiki_map():
    Page.objects.create(u'Wiki/InterwikiMap', interwikis,
                        note=u'Interwikimap automatisch erstellt')

def create():
    create_page_templates()
    create_markup_stylesheet()
    create_smilies()
    create_interwiki_map()


if __name__ == '__main__':
    create()
