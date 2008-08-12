# -*- coding: utf-8 -*-
"""
    inyoka.portal.views
    ~~~~~~~~~~~~~~~~~~~

    All views for the portal including the user control panel,
    private messages, static pages and the login/register and search
    dialogs.

    :copyright: Copyright 2007-2008 by Benjamin Wiegand, Christopher Grebs,
                                       Christoph Hack, Marian Sigler.
    :license: GNU GPL.
"""
from werkzeug import parse_accept_header
from pytz import country_timezones
from datetime import datetime, date
from django.forms.models import model_to_dict
from django import forms
from inyoka.conf import settings
from inyoka.utils import decode_confirm_data
from inyoka.utils.text import get_random_password, human_number, normalize_pagename
from inyoka.utils.dates import MONTHS, WEEKDAYS, get_user_timezone
from inyoka.utils.http import templated, TemplateResponse, HttpResponse, \
     PageNotFound, does_not_exist_is_404, HttpResponseRedirect
from inyoka.utils.sessions import get_sessions, set_session_info, \
     make_permanent, get_user_record, test_session_cookie
from inyoka.utils.urls import href, url_for, is_safe_domain, global_not_found
from inyoka.utils.search import search as search_system
from inyoka.utils.html import escape
from inyoka.utils.flashing import flash
from inyoka.utils.sortable import Sortable, Filterable
from inyoka.utils.templating import render_template
from inyoka.utils.pagination import Pagination
from inyoka.utils.notification import send_notification
from inyoka.utils.cache import cache
from inyoka.utils.dates import datetime_to_timezone, DEFAULT_TIMEZONE
from inyoka.utils.storage import storage
from inyoka.utils.tracreporter import Trac
from inyoka.utils.user import deactivate_user, reactivate_user, \
     normalize_username
from inyoka.wiki.utils import quote_text
from inyoka.wiki.parser import parse, RenderContext
from inyoka.wiki.models import Page as WikiPage
from inyoka.ikhaya.models import Article, Category, Suggestion
from inyoka.forum.models import Forum, SAUser, Topic, Post
from inyoka.portal.forms import LoginForm, SearchForm, RegisterForm, \
     UserCPSettingsForm, PrivateMessageForm, DeactivateUserForm, \
     LostPasswordForm, ChangePasswordForm, SubscriptionForm, \
     UserCPProfileForm, SetNewPasswordForm, UserErrorReportForm, \
     NOTIFICATION_CHOICES, ForumFeedSelectorForm, IkhayaFeedSelectorForm, \
     PlanetFeedSelectorForm, WikiFeedSelectorForm
from inyoka.portal.models import StaticPage, PrivateMessage, Subscription, \
     PrivateMessageEntry, PRIVMSG_FOLDERS, Event
from inyoka.portal.user import User, Group, UserBanned
from inyoka.portal.utils import check_login, calendar_entries_for_month, \
    check_activation_key, send_activation_mail, send_new_user_password
from inyoka.utils.antispam import is_spam



def not_found(request, err_message=None):
    """
    This is called if no URL matches or a view returned a `PageNotFound`.
    """
    from inyoka.portal.legacyurls import test_legacy_url
    response = test_legacy_url(request)
    if response is not None:
        return response
    return global_not_found(request, 'portal', err_message)


@templated('portal/index.html')
def index(request):
    """
    Startpage that shows the latest ikhaya articles
    and some records of ubuntuusers.de
    """
    ikhaya_latest = Article.published.all()[:10]
    events = Event.objects.order_by('date').filter(
        date__gt=datetime.utcnow())[:4]
    set_session_info(request, u'ist am Portal', 'Portal')
    record, record_time = get_user_record()
    storage_keys = storage.get_many(('get_ubuntu_link',
        'get_ubuntu_description'))
    return {
        'ikhaya_latest':            list(ikhaya_latest),
        'sessions':                 get_sessions(),
        'record':                   record,
        'record_time':              record_time,
        'get_ubuntu_link':          storage_keys.get('get_ubuntu_link', '') or '',
        'get_ubuntu_description':   storage_keys.get('get_ubuntu_description', '') or '',
        'calendar_events':          events,
    }


def markup_styles(request):
    """
    This function returns a CSS file that's used for formatting wiki markup.
    Its content is editable in the admin panel.
    """
    from django.utils.cache import patch_response_headers
    response = HttpResponse(storage['markup_styles'], mimetype='text/css')
    patch_response_headers(response, 60 * 15)
    return response


@templated('portal/whoisonline.html')
def whoisonline(request):
    """Shows who is online and a link to the page the user views."""
    registered_users = cache.get('portal/registered_users')
    if registered_users is None:
        registered_users = int(User.objects.count())
        cache.set('portal/registered_users', registered_users, 1000)
    set_session_info(request, u'schaut sich an, wer online ist',
                     u'Wer ist online')
    record, record_time = get_user_record()
    return {
        'sessions':                 get_sessions(),
        'record':                   record,
        'record_time':              record_time,
        'global_registered_users':  registered_users
    }


@templated('portal/register.html')
def register(request):
    """Register a new user."""
    redirect = request.GET.get('next') or href('portal')
    if request.user.is_authenticated:
        flash(u'Du bist bereits angemeldet.', False)
        return HttpResponseRedirect(redirect)

    cookie_error_link = test_session_cookie(request)

    form = RegisterForm()
    if request.method == 'POST' and cookie_error_link is None and \
       'renew_captcha' not in request.POST:
        form = RegisterForm(request.POST)
        form.captcha_solution = request.session.get('captcha_solution')
        if form.is_valid():
            data = form.cleaned_data
            user = User.objects.register_user(
                username=data['username'],
                email=data['email'],
                password=data['password'])

            # set timezone based on browser language.  This is not the
            # best way to do that, but good enough for the moment.

            # Why don't we just use the DEFAULT_TIMEZONE and let the user
            # choose some more details. -- entequak
            timezone = DEFAULT_TIMEZONE
            language_header = request.META.get('HTTP_ACCEPT_LANGUAGES')
            if language_header:
                languages = parse_accept_header(language_header)
                try:
                    timezones = country_timezones(languages.best)
                    if not timezones:
                        raise LookupError()
                except LookupError:
                    pass
                else:
                    timezone = timezones[0]

            # utc is default, no need for another update statement
            if timezone != DEFAULT_TIMEZONE:
                user.settings['timezone'] = timezone
                user.save()

            flash(u'Der Benutzer „%s“ wurde erfolgreich registriert. '
                  u'Es wurde eine E-Mail an „%s“ gesendet, in der du deinen '
                  u'Account aktivieren kannst.' % (
                        escape(data['username']), escape(data['email'])), True)

            # clean up request.session
            request.session.pop('captcha_solution', None)
            return HttpResponseRedirect(redirect)

    set_session_info(request, u'registriert sich',
                     'registriere dich auch')
    return {
        'form':         form,
        'cookie_error': cookie_error_link is not None,
        'retry_link':   cookie_error_link
    }


def activate(request, action='', username='', activation_key=''):
    """Activate a user with the activation key send via email."""
    redirect = is_safe_domain(request.GET.get('next', ''))
    if not redirect:
        redirect = href('portal', 'login', username=username)
    try:
        user = User.objects.get(username)
    except User.DoesNotExist:
        flash(u'Der Benutzer „%s“ existiert nicht!' % escape(username), False)
        return HttpResponseRedirect(href('portal'))

    if not action in ('delete', 'activate'):
        raise PageNotFound()

    if action == 'delete':
        if check_activation_key(user, activation_key):
            if not user.is_active:
                # Is it save to delete an inactive user?
                #user.delete()
                #flash(u'Der Benutzer „%s“ wurde gelöscht.' %
                #      escape(username), True)
                flash(u'Benutzer löschen derzeit inaktiv', False)
            else:
                flash(u'Der Benutzer „%s“ wurde schon aktiviert.' %
                      escape(username), False)
        else:
            flash(u'Dein Aktivierungskey stimmt nicht überein!', False)
        return HttpResponseRedirect(href('portal'))
    else:
        if check_activation_key(user, activation_key):
            user.status = 1
            user.save()
            flash(u'Du wurdest erfolgreich aktiviert und kannst dich nun '
                  u'einloggen.', True)
            return HttpResponseRedirect(redirect)
        else:
            flash(u'Dein Aktivierungskey stimmt nicht überein!', False)
            return HttpResponseRedirect(href('portal'))


@does_not_exist_is_404
def resend_activation_mail(request, username):
    """Resend the activation mail if the user is not already activated."""
    user = User.objects.get(username)

    if request.GET.get('legacy', False):
        flash(u'Da wir kürzlich auf eine neue Portalsoftware umgestellt '
              u'haben, sind die alten Aktivierungslink nicht mehr gültig, '
              u'du erhältst deshalb eine weitere Mail mit einem neuen Link.')

    if user.status > 0:
        flash(u'Das Benutzerkonto von „%s“ ist schon aktiviert worden!' %
              escape(user.username), False)
        return HttpResponseRedirect(href('portal'))
    send_activation_mail(user)
    flash(u'Es wurde eine E-Mail gesendet, mit der du dein '
          u'Benutzerkonto aktivieren kannst.', True)
    return HttpResponseRedirect(href('portal'))


@templated('portal/lost_password.html')
def lost_password(request):
    """
    View for the lost password dialog.
    It generates a new random password and sends it via mail.
    """
    if request.user.is_authenticated:
        flash(u'Du bist bereits angemeldet!', False)
        return HttpResponseRedirect(href('portal'))

    if request.method == 'POST':
        form = LostPasswordForm(request.POST)
        form.captcha_solution = request.session.get('captcha_solution')
        if form.is_valid():
            data = form.cleaned_data
            send_new_user_password(form.user)
            flash(u'Es wurde eine E-Mail mit weiteren Anweisungen an deine '
                  u'E-Mail-Adresse gesendet!', True)

            # clean up request.session
            return HttpResponseRedirect(href('portal', 'login'))
    else:
        form = LostPasswordForm()

    return {
        'form': form
    }


@templated('portal/set_new_password.html')
def set_new_password(request, username, new_password_key):
    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            data['user'].set_password(data['password'])
            data['user'].new_password_key = ''
            data['user'].save()
            flash(u'Es wurde ein neues Passwort gesetzt. Du kannst dich nun '
                  u'einloggen.', True)
            return HttpResponseRedirect(href('portal', 'login'))
    else:
        try:
            user = User.objects.get(username)
        except User.DoesNotExist:
            flash(u'Diesen Benutzer gibt es nicht', False)
            return HttpResponseRedirect(href())
        if user.new_password_key != new_password_key:
            flash(u'Ungültiger Bestätigungskey!', False)
            return HttpResponseRedirect(href())
        form = SetNewPasswordForm(initial={
            'username': username,
            'new_password_key': new_password_key,
        })
    return {
        'form': form,
        'username': username,
    }


@templated('portal/login.html')
def login(request):
    """Login dialog that supports permanent logins"""
    redirect = is_safe_domain(request.GET.get('next', '')) and \
               request.GET['next'] or href('portal')
    if request.user.is_authenticated:
        flash(u'Du bist bereits angemeldet!', False)
        return HttpResponseRedirect(redirect)

    # enforce an existing session
    cookie_error_link = test_session_cookie(request)

    failed = inactive = banned = False
    if request.method == 'POST' and cookie_error_link is None:
        form = LoginForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                user = User.objects.authenticate(
                    username=data['username'],
                    password=data['password'])
            except User.DoesNotExist:
                failed = True
                user = None
            except UserBanned:
                failed = banned = True
                user = None

            if user is not None:
                if user.is_active:
                    if data['permanent']:
                        make_permanent(request)
                    # username matches password and user is active
                    flash(u'Du hast dich erfolgreich angemeldet.', True)
                    user.login(request)
                    return HttpResponseRedirect(redirect)
                inactive = True
            failed = True
    else:
        if 'username' in request.GET:
            form = LoginForm(initial={'username':request.GET['username']})
        else:
            form = LoginForm()

    d = {
        'form':         form,
        'failed':       failed,
        'inactive':     inactive,
        'banned':       banned,
        'cookie_error': cookie_error_link is not None,
        'retry_link':   cookie_error_link
    }
    if failed:
        d['username'] = data['username']
    return d


def logout(request):
    """Simple logout view that flashes if the process was done
    successfull or not (e.g if the user wasn't logged in)."""
    if request.user.is_authenticated:
        User.objects.logout(request)
        flash(u'Du hast dich erfolgreich abgemeldet.', True)
    else:
        flash(u'Du warst nicht eingeloggt', False)
    return HttpResponseRedirect(request.GET.get('next') or
                                href('portal'))


@templated('portal/search.html')
def search(request):
    """Search dialog for the Xapian search engine."""
    def _add_field_choices():
        """Add dynamic field choices to the reported topic formular"""
        f.fields['forums'].choices = [('all', u'Alle Foren'),
            ('support', u'Alle Support-Foren')
        ] + [(o.slug, o.name) for o in Forum.query.all()]

    set_session_info(request, u'sucht gerade nach etwas.', 'Suche')
    if 'query' in request.REQUEST:
        f = SearchForm(request.REQUEST)
    else:
        f = SearchForm()
    _add_field_choices()
    if f.is_valid():
        d = f.cleaned_data
        show_all = request.GET.get('show_all') == 'true'
        area = {
            'wiki': 'w',
            'forum': 'f',
            'ikhaya': 'i',
            'planet': 'p'
        }.get(d['area'])
        query = d['query']

        if d['area'] == 'topic':
            query += ' topic:"%s"' % request.GET['topic_id']
        elif d['area'] == 'current_forum':
            query += ' forum:"%s"' % request.GET['forum_id']

        if d['forums'] and d['forums'] not in ('support', 'all'):
            query += ' category:"%s"' % d['forums']

        results = search_system.query(request.user,
            query,
            page=d['page'] or 1, per_page=d['per_page'] or 20,
            date_begin=datetime_to_timezone(d['date_begin'], enforce_utc=True),
            date_end=datetime_to_timezone(d['date_end'], enforce_utc=True),
            component=area,
            exclude=d['forums'] == 'support' and settings.SEARCH_DEFAULT_EXCLUDE or [],
            sort=d['sort']
        )
        if len(results.results ) > -1:
            normal = u'<a href="%(href)s" class="pageselect">%(text)s</a>'
            disabled = u'<span class="disabled next">%(text)s</span>'
            active = u'<span class="pageselect active">%(text)s</span>'
            pagination = [u'<div class="pagination pagination_right">']
            add = pagination.append

            def _link(page):
                return href('portal', 'search', page=page, query=d['query'],
                            area=d['area'], per_page=results.per_page,
                            sort=d['sort'])

            add(((results.page == 1) and disabled or normal) % {
                'href': _link(results.page - 1),
                'text': u'« Zurück',
            })
            add(active % {
                'text': u'Seite %d von ungefähr %d' % (results.page, results.page_count)
            })
            add(((results.page < results.page_count) and normal or disabled) % {
                'href': _link(results.page + 1),
                'text': u'Weiter »'
            })
            add(u'<div style="clear: both"></div></div>')

            return TemplateResponse('portal/search_results.html', {
                'query':            d['query'],
                'highlight':        results.highlight_string,
                'area':             d['area'],
                'results':          results,
                'pagination':       u''.join(pagination),
                'sort':             d['sort']
            })
        else:
            flash(u'Die Suche nach „%s“ lieferte keine Ergebnisse.' %
                escape(d['query']))

    return {
        'area': request.GET.get('area') or 'all',
        'searchform': f
    }


@check_login(message=u'Du musst eingeloggt sein, um ein Benutzerprofil zu '
                     u'sehen.')
@templated('portal/profile.html')
def profile(request, username):
    """Show the user profile if the user is logged in."""

    user = User.objects.get(username)

    try:
        if username != user.username.replace(' ', '_'):
            return HttpResponseRedirect(user.get_absolute_url())
    except ValueError:
        raise PageNotFound()

    try:
        key = 'Benutzer/' + normalize_pagename(user.username)
        wikipage = WikiPage.objects.get_by_name(key, raise_on_deleted=True)
        content = wikipage.rev.rendered_text
    except WikiPage.DoesNotExist:
        content = u''
    set_session_info(request, u'schaut sich das Benutzerprofil von '
                     u'„<a href="%s">%s</a>“ an.' % (
        escape(url_for(user)),
        escape(user.username),
    ))
    return {
        'user':     user,
        'groups':   user.groups.all(),
        'wikipage': content,
        'User':     User,
    }


@check_login(message=u'Du musst eingeloggt sein, um dein Verwaltungscenter '
                     u'zu sehen')
@templated('portal/usercp/index.html')
def usercp(request):
    """User control panel index page"""
    set_session_info(request, 'schaut sich sein Verwaltungscenter an')
    user = request.user
    return {
        'user': user,
    }


@check_login(message=u'Du musst eingeloggt sein, um dein Profil zu ändern')
@templated('portal/usercp/profile.html')
def usercp_profile(request):
    """User control panel view for changing the user's profile"""
    set_session_info(request, 'verändert sein Profil')
    user = request.user
    if request.method == 'POST':
        form = UserCPProfileForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            for key in ('jabber', 'icq', 'msn', 'aim', 'yim',
                        'skype', 'wengophone', 'sip',
                        'signature', 'location', 'occupation',
                        'interests', 'website', 'email', 'gpgkey',
                        'launchpad'):
                setattr(user, key, data[key] or '')
            if data['coordinates']:
                user.coordinates_lat, user.coordinates_long = \
                    data['coordinates']
            if data['delete_avatar']:
                user.delete_avatar()
            if data['avatar']:
                avatar_resized = user.save_avatar(data['avatar'])
                if avatar_resized:
                    ava_mh, ava_mw = storage.get_many(('max_avatar_height',
                        'max_avatar_width')).itervalues()
                    flash(u'Der von dir hochgeladene Avatar wurde auf '
                          u'%sx%s Pixel skaliert. Dadurch könnten '
                          u'Qualitätseinbußen aufgetreten sein. '
                          u'Bitte beachte dies.'
                          % (ava_mh, ava_mw))
            for key in ('show_email', 'show_jabber'):
                user.settings[key] = data[key]
            user.save()
            flash(u'Deine Profilinformationen wurden erfolgreich '
                  u'aktualisiert.', True)
            return HttpResponseRedirect(href('portal', 'usercp', 'profile'))
        else:
            flash(u'Es traten Fehler bei der Bearbeitung des Formulars '
                  u'auf. Bitte behebe sie.', False)
    else:
        values = model_to_dict(user)
        lat = values.pop('coordinates_lat')
        long = values.pop('coordinates_long')
        if lat is not None and long is not None:
            values['coordinates'] = '%s, %s' % (lat, long)
        else:
            values['coordinates'] = ''
        values.update(dict(
            ((k, v) for k, v in user.settings.iteritems()
             if k.startswith('show_'))
        ))
        form = UserCPProfileForm(initial=values)

    storage_keys = storage.get_many(('max_avatar_width',
        'max_avatar_height', 'max_signature_length'))

    return {
        'form':                 form,
        'user':                 request.user,
        'gmaps_apikey':         settings.GOOGLE_MAPS_APIKEY,
        'max_avatar_width':     storage_keys.get('max_avatar_width', -1),
        'max_avatar_height':    storage_keys.get('max_avatar_height', -1),
        'max_sig_length':       storage_keys.get('max_signature_length'),
    }


@check_login(message=u'Du musst eingeloggt sein, um deine Einstellungen zu '
                     u'ändern')
@templated('portal/usercp/settings.html')
def usercp_settings(request):
    """User control panel view for changing various user settings"""
    set_session_info(request, u'Ändert die Benutzereinstellungen')
    if request.method == 'POST':
        form = UserCPSettingsForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            for key, value in data.iteritems():
                request.user.settings[key] = data[key]
            request.user.save()
            flash(u'Deine Benutzereinstellungen wurden erfolgreich '
                  u'aktualisiert.', True)
        else:
            flash(u'Es traten Fehler bei der Bearbeitung des Formulars '
                  u'auf. Bitte behebe sie.')
    else:
        settings = request.user.settings
        values = {
            'notify': settings.get('notify', ['mail']),
            'notifications': settings.get('notifications', [c[0] for c in
                                                    NOTIFICATION_CHOICES]),
            'timezone': get_user_timezone(),
            'hide_avatars': settings.get('hide_avatars', False),
            'hide_signatures': settings.get('hide_signatures', False),
            'hide_profile': settings.get('hide_profile', False),
            'autosubscribe': settings.get('autosubscribe', False),
            'show_preview': settings.get('show_preview', False),
            'show_thumbnails': settings.get('show_thumbnails', False)
        }
        form = UserCPSettingsForm(values)
    return {
        'form': form,
        'user': request.user,
    }


@check_login(message=u'Du musst eingeloggt sein, um dein Benutzerpasswort '
                     u'ändern zu können')
@templated('portal/usercp/change_password.html')
def usercp_password(request):
    """User control panel view for changing the password."""
    random_pw = None
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = request.user
            if user.check_password(data['old_password']):
                user.set_password(data['new_password'])
                user.save()
                flash(u'Dein Passwort wurde erfolgreich geändert',
                      success=True)
                return HttpResponseRedirect(href('portal', 'usercp'))
            else:
                form.errors['old_password'] = [u'Das eingegebene Passwort '
                                    u'stimmt nicht mit deinem Alten überein']
    else:
        if 'random' in request.GET:
            random_pw = get_random_password()
            form = ChangePasswordForm(initial={'new_password': random_pw,
                                        'new_password_confirm': random_pw})
        else:
            form = ChangePasswordForm()

    return {
        'form': form,
        'random_pw': random_pw,
    }


@check_login(message=u'Du musst eingeloggt sein, um deine Benachrichtigungen '
                     u'sehen bzw. ändern zu können')
@templated('portal/usercp/subscriptions.html')
def usercp_subscriptions(request, page=1, all=False):
    """
    This page shows all subscriptions of the current user and allows him
    to delete them.
    """
    subscriptions = request.user.subscription_set.all()
    pagination = Pagination(request, subscriptions, page, all and
        len(subscriptions) or 25, href('portal', 'usercp', 'subscriptions'))

    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        form.fields['delete'].choices = [(s.id, u'') for s in pagination.objects]
        if form.is_valid():
            d = form.cleaned_data
            Subscription.objects.delete_list(d['delete'])
            if len(d['delete']) == 1:
                flash(u'Es wurde ein Abonnement gelöscht.', success=True)
            else:
                flash(u'Es wurden %s Abonnements gelöscht.'
                      % human_number(len(d['delete'])), success=True)
            pagination.objects = filter(lambda s: str(s.id) not in d['delete'], pagination.objects)

    return {
        'subscriptions': pagination.objects,
        'pagination': pagination.generate()
    }


@check_login(message=u'Du musst eingeloggt sein, um deinen Benutzer '
                     u'deaktivieren zu können')
@templated('portal/usercp/deactivate.html')
def usercp_deactivate(request):
    """
    This page allows the user to deactivate his account.
    """
    #XXX: this is "banned safe", so we could allow banned users to also delete 
    #     their accounts, eg by prompting for the username here
    if request.method == 'POST':
        form = DeactivateUserForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if request.user.check_password(data['password_confirmation']):
                deactivate_user(request.user)
                User.objects.logout(request)
                flash('Dein Account wurde deaktiviert.', True)
                return HttpResponseRedirect(href('portal'))
            else:
                form.errors['password_confirmation'] = [u'Das eingegebene'
                                                     u' Passwort war falsch.']
    else:
        form = DeactivateUserForm()
    return {
        'form': form
    }


@check_login(message=u'Du musst ein geloggt sein, um deine Benutzerseite '
                     u'zu editieren')
def usercp_userpage(request):
    """
    Redirect page that shows a small flash message that
    the user was redirected
    """
    flash(u'Du wurdest in unser Wiki umgeleitet um deine Benutzerseite zu editieren. '
          u'Klicke <a href="%s" title="Kontrollzentrum">hier</a> um wieder zurück '
          u'ins Kontrollzentrum zu gelangen'
          % escape(href('portal', 'usercp')))
    return HttpResponseRedirect(href('wiki', 'Benutzer',
        request.user.username, action='edit'))


@templated('portal/privmsg/index.html')
@check_login(message=u'Du musst eingeloggt sein, um deine privaten '
                     u'Nachrichten anzusehen')
def privmsg(request, folder=None, entry_id=None, page=1):
    set_session_info(request, u'sieht sich seine privaten Nachrichten an')
    if folder is None:
        if entry_id is None:
            return HttpResponseRedirect(href('portal', 'privmsg',
                                             PRIVMSG_FOLDERS['inbox'][1]))
        else:
            entry = PrivateMessageEntry.objects.get(user=request.user,
                                                    id=entry_id)
            try:
                return HttpResponseRedirect(href('portal', 'privmsg',
                                                 PRIVMSG_FOLDERS[entry.folder][1],
                                                 entry.id))
            except KeyError:
                raise PageNotFound
    message = None
    if entry_id is not None:
        entry = PrivateMessageEntry.objects.get(user=request.user,
            folder=PRIVMSG_FOLDERS[folder][0], id=entry_id)
        message = entry.message
        if not entry.read:
            entry.read = True
            entry.save()
            cache.delete('portal/pm_count/%s' % request.user.id)
        action = request.GET.get('action')
        if action == 'delete':
            folder = entry.folder
            entry.delete()
            if not entry.read:
                cache.delete('portal/pm_count/%s' % request.user_id)
            flash(u'Die Nachricht wurde erfolgreich gelöscht.', True)
            return HttpResponseRedirect(href('portal', 'privmsg',
                                             PRIVMSG_FOLDERS[folder][1]))
        elif action == 'archive':
            if entry.archive():
                flash(u'Die Nachricht wurde in dein Archiv verschoben.', True)
                message = None
        elif action == 'restore':
            if entry.restore():
                flash(u'Die Nachricht wurde wiederhergestellt.', True)
                message = None
    else:
        message = None
    entries = PrivateMessageEntry.objects.filter(
        user=request.user,
        folder=PRIVMSG_FOLDERS[folder][0]
    ).order_by('-id')
    link = href('portal', 'privmsg', folder, 'page')
    pagination = Pagination(request, entries, page, 10, link)
    return {
        'entries': list(pagination.objects),
        'pagination': pagination.generate(),
        'folder': {
            'name': PRIVMSG_FOLDERS[folder][2],
            'id': PRIVMSG_FOLDERS[folder][1]
        },
        'message': message
    }


@templated('portal/privmsg/new.html')
@check_login(message=u'Du musst eingeloggt sein, um deine privaten '
                     u'Nachrichten anzusehen')
def privmsg_new(request, username=None):
    set_session_info(request, u'schreibt eine neue private Nachricht')
    preview = None
    form = PrivateMessageForm()
    if request.method == 'POST':
        form = PrivateMessageForm(request.POST)
        if 'preview' in request.POST:
            ctx = RenderContext(request)
            preview = parse(request.POST.get('text','')).render(ctx, 'html')
        elif form.is_valid():
            d = form.cleaned_data
            recipient_names = set(r.strip() for r in \
                                  d['recipient'].split(';') if r)
            group_recipient_names = set(r.strip() for r in \
                                  d['group_recipient'].split(';') if r)

            recipients = set()

            if d.get('group_recipient', None) and not request.user.can('send_group_pm'):
                flash(u'Du darfst keine Nachrichten an'
                      u'Gruppen schicken.', False)
                return HttpResponseRedirect(href('portal', 'privmsg'))

            for group in group_recipient_names:
                try:
                    users = Group.objects.get(name__iexact=group).user_set.\
                        all().exclude(pk=request.user.id)
                    recipients.update(users)
                except Group.DoesNotExist:
                    flash(u'Die Gruppe „%s“ wurde nicht gefunden'
                          % escape(group), False)
                    return HttpResponseRedirect(href('portal', 'privmsg'))

            try:
                for recipient in recipient_names:
                    user = User.objects.get(recipient)
                    if user.id == request.user.id:
                        recipients = None
                        flash(u'Du kannst dir selber keine Nachrichten '
                              u'schicken.', False)
                        break
                    elif user in (User.objects.get_system_user(),
                                  User.objects.get_anonymous_user()):
                        recipients = None
                        flash(u'Diesem Systemuser kannst du keine Nachrichten'
                              u' schicken!', False)
                        break
                    else:
                        recipients.add(user)
            except User.DoesNotExist:
                recipients = None
                flash(u'Der Benutzer „%s“ wurde nicht gefunden'
                      % escape(recipient), False)

            if recipients:
                msg = PrivateMessage()
                msg.author = request.user
                msg.subject = d['subject']
                msg.text = d['text']
                msg.pub_date = datetime.utcnow()
                msg.send(list(recipients))
                # send notification
                for recipient in recipients:
                    entry = PrivateMessageEntry.objects.get(message=msg,
                                                            user=recipient)
                    if 'pm_new' in recipient.settings.get('notifications',
                                                          ('pm_new',)):
                        text = render_template('mails/new_pm.txt', {
                            'user':     recipient,
                            'sender':   request.user,
                            'subject':  d['subject'],
                            'entry':    entry,
                       })
                        send_notification(recipient, 'new_pm', u'Neue private '
                                          u'Nachricht von %s: %s' %
                                          (request.user.username, d['subject']), {
                                              'user':     recipient,
                                              'sender':   request.user,
                                              'subject':  d['subject'],
                                              'entry':    entry,
                                          })
                flash(u'Die persönliche Nachricht wurde erfolgreich '
                      u'versandt.', True)

            return HttpResponseRedirect(href('portal', 'privmsg'))
    else:
        data = {}
        reply_to = request.GET.get('reply_to', '')
        forward = request.GET.get('forward', '')
        try:
            int(reply_to or forward)
        except ValueError:
            if ':' in (reply_to or forward):
                x = reply_to or forward
                REPLIABLES = {
                    'suggestion': (
                        lambda id: Suggestion.objects.get(id=int(id)),
                        lambda x: x.title,
                        lambda x: x.author,
                        lambda x: u'\n\n'.join((x.intro, x.text)),
                    ),
                    'reportedtopic': (
                        lambda id: Topic.query.filter_by(slug=id).one(),
                        lambda x: x.title,
                        lambda x: User.objects.get(id=x.reporter_id),
                        lambda x: x.reported,
                    ),
                    'post': (
                        lambda id: Post.query.filter_by(id=int(id)).one(),
                        lambda x: x.topic.title,
                        lambda x: User.objects.get(id=x.author_id),
                        lambda x: x.text,
                    ),
                }
                for repliable, params in REPLIABLES.items():
                    if x[:len(repliable) + 1] != repliable + ':':
                        continue
                    try:
                        obj = params[0](x[len(repliable) + 1:])
                    except:
                        break
                    data['subject'] = params[1](obj)
                    if not data['subject'].lower().startswith(u're: '):
                        data['subject'] = u'Re: %s' % data['subject']
                    author = params[2](obj)
                    if reply_to:
                        data['recipient'] = author
                    data['text'] = quote_text(params[3](obj), author) + '\n'
                    form = PrivateMessageForm(initial=data)
        else:
            try:
                entry = PrivateMessageEntry.objects.get(user=request.user,
                    message=int(reply_to or forward))
                msg = entry.message
                data['subject'] = msg.subject.lower().startswith(u're: ') and \
                                  msg.subject or u'Re: %s' % msg.subject
                if reply_to:
                    data['recipient'] = msg.author.username
                data['text'] = quote_text(msg.text, msg.author) + '\n'
                form = PrivateMessageForm(initial=data)
            except (PrivateMessageEntry.DoesNotExist):
                pass
        if username:
            form = PrivateMessageForm(initial={'recipient': username})
    return {
        'form': form,
        'preview': preview
    }


@templated('portal/memberlist.html')
def memberlist(request, page=1):
    """
    Shows the memberlist.

    `page` represents the current page in the pagination.
    """
    sortable = Sortable(SAUser.query, request.GET, 'id', sqlalchemy=True,
                        sa_column=SAUser.id,
                        columns=['id', 'username', 'location', 'date_joined',
                                 'post_count'])
    filterable = Filterable(SAUser, sortable.get_objects(), {
        'id':           (u'Nummer', 'int'),
        'username':     (u'Benutzername', 'str'),
        'date_joined':  (u'Anmeldungsdatum', 'date'),
        'post_count':   (u'Beiträge', 'int'),
        'location':     (u'Wohnort', 'str'),
    }, request.GET)
    pagination = Pagination(request, filterable.get_objects(), page, 15,
        href('portal', 'users'))
    set_session_info(request, u'schaut sich die Mitgliederliste an.',
                     'Mitgliederliste')
    return {
        'users':        list(pagination.objects),
        'pagination':   pagination,
        'table':        sortable,
        'filterable':   filterable,
    }


@templated('portal/grouplist.html')
def grouplist(request, page=1):
    """
    Shows the group list.

    `page` represents the current page in the pagination.
    """
    table = Sortable(Group.objects.all(), request.GET, 'name',
                     columns=['id', 'name'])
    pagination = Pagination(request, table.get_objects(), page, 15)
    set_session_info(request, u'schaut sich die Gruppenliste an.',
                     'Gruppenliste')
    return {
        'groups':      list(pagination.objects),
        'group_count': Group.objects.count(),
        'user_groups': request.user.groups.count(),
        'pagination':  pagination,
        'table':       table
    }


@templated('portal/group.html')
def group(request, name, page=1):
    """Shows the informations about the group named `name`."""
    group = Group.objects.get(name__iexact=name)
    users = group.user_set

    table = Sortable(users, request.GET, 'id',
        columns=['id', 'username', 'location', 'date_joined', 'post_count'])
    pagination = Pagination(request, table.get_objects(), page, 15)
    set_session_info(request, u'schaut sich die Gruppe '
                     u'„<a href="%s">%s</a>“ an.' % (
        href('portal', 'group', escape(name)),
        escape(name)
    ))
    return {
        'group':      group,
        'users':      list(pagination.objects),
        'user_count': group.user_set.count(),
        'pagination': pagination,
        'table':      table,
    }


@templated('portal/usermap.html')
def usermap(request):
    set_session_info(request, u'schaut sich die Benutzerkarte an.',
                     'Benutzerkarte')
    return {
        'apikey':       settings.GOOGLE_MAPS_APIKEY,
    }


@templated('portal/feedselector.html')
def feedselector(request, app=None):
    for fapp in ('forum', 'ikhaya', 'planet', 'wiki'):
        if app in (fapp, None):
            globals()['%s_form' % fapp] = request.POST \
                and globals()['%sFeedSelectorForm' % fapp.capitalize()] \
                    (request.POST, auto_id='id_%s_%%s' % fapp)\
                or globals()['%sFeedSelectorForm' % fapp.capitalize()] \
                    (auto_id='id_%s_%%s' % fapp)
        else:
            globals()['%s_form' % fapp] = None
    if forum_form:
        #TODO: filter those readable by anonymous
        forum_form.fields['forum'].choices = [('', u'Bitte auswählen')] + \
            [(f.slug, f.name) for f in Forum.query.all()]
    if ikhaya_form:
        ikhaya_form.fields['category'].choices = [('*', u'Alle')] + \
            [(c.slug, c.name) for c in Category.objects.all()]
    if wiki_form:
        wiki_pages = cache.get('feedselector/wiki/pages')
        if not wiki_pages:
            wiki_pages = WikiPage.objects.all()
            cache.set('feedselector/wiki/pages', wiki_pages)
        wiki_form.fields['page'].choices = [('*', u'Alle')] + \
            [(p.name, p.name) for p in wiki_pages]

    if request.method == 'POST':
        form = globals()['%s_form' % app]
        if form.is_valid():
            data = form.cleaned_data
            if app == 'forum':
                if data['component'] == '*':
                    return HttpResponseRedirect(href('forum', 'feeds',
                           data['mode'], data['count']))
                if data['component'] == 'forum':
                    return HttpResponseRedirect(href('forum', 'feeds', 'forum',
                           data['forum'], data['mode'], data['count']))

            elif app == 'ikhaya':
                if data['category'] == '*':
                    return HttpResponseRedirect(href('ikhaya', 'feeds',
                           data['mode'], data['count']))
                else:
                    return HttpResponseRedirect(href('ikhaya', 'feeds',
                           data['category'], data['mode'], data['count']))

            elif app == 'planet':
                return HttpResponseRedirect(href('planet', 'feeds',
                       data['mode'], data['count']))

            elif app == 'wiki':
                if data['page'] == '*':
                    return HttpResponseRedirect(href('wiki', '_feed',
                           data['count']))
                else:
                    return HttpResponseRedirect(href('wiki', '_feed',
                           data['page'], data['count']))

    return {
        'app':         app,
        'forum_form':  forum_form,
        'ikhaya_form': ikhaya_form,
        'planet_form': planet_form,
        'wiki_form':   wiki_form,
    }


@templated('portal/static_page.html')
def static_page(request, page):
    """Renders static pages"""
    try:
        q = StaticPage.objects.get(key=page)
    except StaticPage.DoesNotExist:
        raise PageNotFound
    return {
        'title': q.title,
        'content': q.content,
        'key': q.key,
    }


@templated('portal/about_inyoka.html')
def about_inyoka(request):
    """Render a inyoka information page."""
    set_session_info(request, u'informiert sich über <a href="%s">'
                     u'Inyoka</a>' % href('portal', 'inyoka'))


@templated('portal/calendar_month.html')
def calendar_month(request, year, month):
    year = int(year)
    month = int(month)
    if year < 1900 or month < 1 or month > 12:
        raise PageNotFound
    days = calendar_entries_for_month(year, month)
    days = [(date(year, month, day), events) for day, events in days.items()]
    set_session_info(request, u'sieht sich den Kalender an')

    return {
        'days': days,
        'year': year,
        'month': month,
        'today': datetime.utcnow().date(),
        'MONTHS': dict(list(enumerate([''] + MONTHS))[1:]),
        'WEEKDAYS': dict(enumerate(WEEKDAYS)),
    }


@templated('portal/calendar_overview.html')
def calendar_overview(request):
    events = Event.objects.order_by('date').filter(date__gt=datetime.utcnow())[:10]
    set_session_info(request, u'sieht sich den Kalender an')
    return {
        'events': events,
        'year': datetime.utcnow().year,
        'month': datetime.utcnow().month,
        'MONTHS': dict(list(enumerate([''] + MONTHS))[1:]),
        'WEEKDAYS': dict(enumerate(WEEKDAYS)),
    }


@templated('portal/calendar_detail.html')
def calendar_detail(request, slug):
    try:
        event = Event.objects.get(slug=slug)
    except Event.DoesNotExist:
        raise PageNotFound
    set_session_info(request, u'sieht sich den Kalender an')
    return {
        'event': event,
        'MONTHS': dict(list(enumerate([''] + MONTHS))[1:]),
        'WEEKDAYS': dict(enumerate(WEEKDAYS)),
    }


@templated('portal/open_search.xml', content_type='text/xml; charset=utf-8')
def open_search(request, app):
    if app not in ('wiki', 'forum', 'planet', 'ikhaya'):
        app='portal'
    return {
        'app': app
    }


@templated('portal/user_error_report.html')
def user_error_report(request):
    if request.method == 'POST':
        form = UserErrorReportForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if not request.user.is_authenticated:
                spam_test = data['title'].lower() + data['text'].lower()
                spam_words = ('porn', 'eroti', 'sex', 'casino', 'poker',
                              '<a href=', 'gay', 'female', 'nude', 'teen',
                              'wwrkckjbWRKcKjbtrama', 'rolex', 'viagra')
                for w in spam_words:
                    if w in spam_test:
                        return {'spam': True}
                if is_spam(spam_test):
                    return {'spam': True}
            text =u"'''URL:''' %s" % data['url']
            if request.user.id != 1:
                text += (u" [[BR]]\n'''Benutzer:''' [%s %s] ([%s PN])" % (
                    request.user.get_absolute_url(),
                    escape(request.user.username),
                    request.user.get_absolute_url('privmsg'),
                ))
            try:
                text += u" [[BR]]\n'''User-Agent:''' {{{%s}}}" % request.META['HTTP_USER_AGENT']
            except KeyError:
                pass
            reporter = request.user.id == 1 and '' or request.user.username
            text += u'\n\n%s' % data['text']
            trac = Trac()
            trac.submit_new_ticket(
                keywords='userreport',
                summary=data['title'],
                description = text,
                component = '-',
                ticket_type = 'userreport',
                reporter = reporter,
            )

            flash(u'Vielen Dank, dein Ticket wurde gespeichert! '\
                  u'Wir werden uns so schnell wie möglich darum kümmern.',
                  True)
            return HttpResponseRedirect(data['url'])
    else:
        if 'url' in request.GET:
            form = UserErrorReportForm(initial={'url':request.GET['url']})
        else:
            form = UserErrorReportForm()

    if 'url' in request.GET:
        show_url_field = False
    else:
        show_url_field = True
        form.fields['url'].widget = forms.TextInput(attrs={'size':50})

    return {
        'form': form,
        'show_url_field': show_url_field,
    }

@templated('portal/confirm.html')
def confirm(request, action=None):

    ACTIONS = {
        'reactivate_user': reactivate_user,
    }

    data = request.REQUEST.get('data')
    if not data:
        # print the form
        return {'action': action}

    try:
        data = decode_confirm_data(data)
    except ValueError:
        return {
            'failed': u'Die eingebenen Daten sind ungültig!',
            'action': action
        }

    if 'action' not in data:
        # legacy support, can be removed after september 15th
        data['action'] = 'reactivate_user'

    return ACTIONS[data.pop('action')](**data)
