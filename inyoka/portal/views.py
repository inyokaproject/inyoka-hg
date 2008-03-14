# -*- coding: utf-8 -*-
"""
    inyoka.portal.views
    ~~~~~~~~~~~~~~~~~~~

    All views for the portal including the user control panel,
    private messages, static pages and the login/register and search
    dialogs.

    :copyright: Copyright 2007 by Benjamin Wiegand, Christopher Grebs,
                                  Christoph Hack, Marian Sigler.
    :license: GNU GPL.
"""
from werkzeug import parse_accept_header
from pytz import country_timezones
from datetime import datetime, date
from django.newforms.models import model_to_dict
from django import newforms as forms
from inyoka.conf import settings
from inyoka.utils.text import get_random_password, human_number
from inyoka.utils.dates import MONTHS, WEEKDAYS, get_user_timezone
from inyoka.utils.http import templated, TemplateResponse, HttpResponse, \
     PageNotFound, does_not_exist_is_404, HttpResponseRedirect
from inyoka.utils.sessions import get_sessions, set_session_info, \
     make_permanent, get_user_record, test_session_cookie
from inyoka.utils.urls import href, url_for, is_safe_domain
from inyoka.utils.search import search as search_system
from inyoka.utils.html import escape
from inyoka.utils.flashing import flash
from inyoka.utils.sortable import Sortable
from inyoka.utils.templating import render_template
from inyoka.utils.pagination import Pagination
from inyoka.utils.notification import send_notification
from inyoka.utils.cache import cache
from inyoka.portal.utils import check_activation_key, send_activation_mail, \
                                send_new_user_password
from inyoka.wiki.models import Page as WikiPage
from inyoka.wiki.utils import normalize_pagename, quote_text
from inyoka.ikhaya.models import Article, Category
from inyoka.forum.models import Forum
from inyoka.portal.forms import LoginForm, SearchForm, RegisterForm, \
     UserCPSettingsForm, PrivateMessageForm, DeactivateUserForm, \
     LostPasswordForm, ChangePasswordForm, SubscriptionForm, \
     UserCPProfileForm, SetNewPasswordForm, UserErrorReportForm, \
     NOTIFICATION_CHOICES
from inyoka.portal.models import StaticPage, PrivateMessage, Subscription, \
     PrivateMessageEntry, PRIVMSG_FOLDERS, Event, UserErrorReport
from inyoka.portal.user import User, Group, deactivate_user, UserBanned
from inyoka.portal.utils import check_login, calendar_entries_for_month
from inyoka.utils.storage import storage
from inyoka.utils.tracreporter import Trac


@templated('errors/404.html')
def not_found(request, err_message=None):
    return {
        'err_message': err_message,
    }


@templated('portal/index.html')
def index(request):
    """
    Startpage that shows the latest ikhaya articles
    and some records of ubuntuusers.de
    """
    ikhaya_latest = Article.published.all()[:10]
    set_session_info(request, u'ist am Portal', 'Portal')
    record, record_time = get_user_record()
    return {
        'ikhaya_latest':    list(ikhaya_latest),
        'sessions':         get_sessions(order_by='subject_text'),
        'record':           record,
        'record_time':      record_time
    }


def markup_styles(request):
    """
    This function returns a CSS file that's used for formatting wiki markup.
    It's content is editable in the admin panel.
    """
    from django.utils.cache import patch_response_headers
    response = HttpResponse(storage['markup_styles'], mimetype='text/css')
    patch_response_headers(response, 60 * 15)
    return response


@templated('portal/whoisonline.html')
def whoisonline(request):
    """Shows who is online and a link to the page the user views."""
    set_session_info(request, u'schaut sich an, wer online ist',
                     u'Wer ist online')
    record, record_time = get_user_record()
    return {
        'sessions':         get_sessions(),
        'record':           record,
        'record_time':      record_time
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
            timezone = 'UTC'
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
            if timezone != 'UTC':
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
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        flash(u'Der Benutzer „%s“ existiert nicht!' % escape(username), False)
        return HttpResponseRedirect(href('portal'))

    if not action in ('delete', 'activate'):
        raise PageNotFound()

    if action == 'delete':
        if check_activation_key(user, activation_key):
            if not user.is_active:
                user.delete()
                flash(u'Der Benutzer „%s“ wurde gelöscht.' %
                      escape(username), True)
            else:
                flash(u'Der Benutzer „%s“ wurde schon aktiviert.' %
                      escape(username), False)
        else:
            flash(u'Dein Aktivierungskey stimmt nicht überein!', False)
        return HttpResponseRedirect(href('portal'))
    else:
        if check_activation_key(user, activation_key):
            user.is_active = True
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
    user = User.objects.get(username=username)
    if user.is_active:
        flash(u'Das Benutzerkonto von „%s“ ist schon aktiviert worden!' %
              escape(user.username), False)
        return HttpResponseRedirect(href('portal'))
    send_activation_mail(user)
    flash(u'Es wurde eine E-Mail an „%s“ gesendet, in der du dein '
          u'Benutzerkonto aktivieren kannst.' % escape(user.email), True)
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
            return HttpResponseRedirect(href('portal'))
    else:
        form = LostPasswordForm()

    return {
        'form': form
    }
    #TODO: maybe we should limit that to some days


@templated('portal/set_new_password.html')
def set_new_password(request, username, new_password_key):
    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            data['user'].set_password(data['password'])
            data['user'].new_password_key = ''
            data['user'].save()
            flash('Es wurde ein neues Passwort gesetzt. Du kannst dich nun '
                  'einloggen.', True)
            return HttpResponseRedirect(href('portal', 'login'))
    else:
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
            else:
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
    set_session_info(request, u'sucht gerade nach etwas.', 'Suche')
    f = SearchForm(request.REQUEST)
    if f.is_valid():
        d = f.cleaned_data
        show_all = request.GET.get('show_all') == 'true'
        area = {
            'wiki': 'w',
            'forum': 'f',
            'ikhaya': 'i',
            'planet': 'p'
        }.get(d['area'])
        results = search_system.query(request.user,
            d['query'],
            page=d['page'] or 1, per_page=d['per_page'] or 20,
            date_begin=d['date_begin'], date_end=d['date_end'],
            component=area,
            exclude=not show_all and settings.SEARCH_DEFAULT_EXCLUDE or []
        )
        if len(results.results ) > 0:
            return TemplateResponse('portal/search_results.html', {
                'query':            d['query'],
                'highlight':        results.highlight_string,
                'area':             d['area'],
                'results':          results,
                'show_all':         show_all
            })
        else:
            flash(u'Die Suche nach „%s“ lieferte keine Ergebnisse.' %
                escape(d['query']))

    return {
        'searchform': f
    }


@check_login(message=u'Du musst eingeloggt sein um ein Benutzerprofil zu '
                     u'sehen')
@templated('portal/profile.html')
def profile(request, username):
    """Shows the user profile if the user is logged in."""
    try:
        user = User.objects.get(username=username)
        key = 'Benutzer/' + normalize_pagename(user.username)
        wikipage = WikiPage.objects.get_by_name(key)
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
        'wikipage': content
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
    if request.method == 'POST':
        form = UserCPProfileForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            for key in ('jabber', 'icq', 'msn', 'aim', 'yim',
                        'skype', 'wengophone', 'sip',
                        'signature', 'location', 'occupation',
                        'interests', 'website', 'email', 'gpgkey'):
                setattr(request.user, key, data[key])
            if data['delete_avatar']:
                request.user.delete_avatar()
            if data['avatar']:
                request.user.save_avatar(data['avatar'])
            for key in ('show_email', 'show_jabber'):
                request.user.settings[key] = data[key]
            request.user.save()
            flash(u'Deine Profilinformationen wurden erfolgreich '
                  u'aktualisiert.', True)
            return HttpResponseRedirect(href('portal', 'usercp', 'profile'))
        else:
            flash(u'Es traten Fehler bei der Bearbeitung des Formulars '
                  u'auf. Bitte behebe sie.')
    else:
        values = model_to_dict(request.user)
        values.update(dict(
            ((k, v) for k, v in request.user.settings.iteritems()
             if k.startswith('show_'))
        ))
        settings = request.user.settings
        form = UserCPProfileForm(values)
    return {
        'form': form,
        'user': request.user
    }


@check_login(message=u'Du musst eingeloggt sein, um deine Einstellungen zu '
                     u'ändern')
@templated('portal/usercp/settings.html')
def usercp_settings(request):
    """User control panel view for changing various user settings"""
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
            'hide_profile': settings.get('hide_profile', False)
        }
        form = UserCPSettingsForm(values)
    return {
        'form': form,
        'user': request.user
    }


@check_login(message=u'Du musst eingeloggt sein, um dein Benutzerpasswort '
                     u'ändern zu können')
@templated('portal/usercp/change_password.html')
def usercp_password(request):
    """User control panel view for changing the password."""
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
            form = ChangePasswordForm({'new_password': get_random_password()})
        else:
            form = ChangePasswordForm()

    return {
        'form': form
    }


@check_login(message=u'Du musst eingeloggt sein, um deine Benachrichtigungen '
                     u'sehen bzw. ändern zu können')
@templated('portal/usercp/subscriptions.html')
def usercp_subscriptions(request):
    """
    This page shows all subscriptions of the current user and allows him
    to delete them.
    """
    sub = list(request.user.subscription_set.all())

    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        form.fields['delete'].choices = [(s.id, u'') for s in sub]
        if form.is_valid():
            d = form.cleaned_data
            Subscription.objects.delete_list(d['delete'])
            if len(d['delete']) == 1:
                flash(u'Es wurde ein Abonnement gelöscht.', success=True)
            else:
                flash(u'Es wurden %s Abonnements gelöscht.'
                      % human_number(len(d['delete'])), success=True)
            sub = filter(lambda s: str(s.id) not in d['delete'], sub)

    return {
        'subscriptions': sub
    }


@check_login(message=u'Du musst eingeloggt sein, um deinen Benutzer '
                     u'deaktivieren zu können')
@templated('portal/usercp/deactivate.html')
def usercp_deactivate(request):
    """
    This page allows the user to deactivate his account.
    """
    #TODO: we should additionally send an email with a link etc
    if request.method == 'POST':
        form = DeactivateUserForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if request.user.check_password(data['password_confirmation']):
                deactivate_user(request.user)
                User.objects.logout(request)
                return HttpResponseRedirect(href('portal'))
            else:
                form.errors['password_confirmation'] = [u'Das eingegebene'
                                                     u' Passwort war falsch.']
    else:
        form = DeactivateUserForm()
    return {
        'form': form
    }


@templated('portal/privmsg/index.html')
@check_login(message=u'Du musst eingeloggt sein, um deine privaten '
                     u'Nachrichten anzusehen')
def privmsg(request, folder=None, entry_id=None):
    if folder is None:
        return HttpResponseRedirect(href('portal', 'privmsg',
                                         PRIVMSG_FOLDERS['inbox'][1]))
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
        elif action == 'revert':
            if entry.revert():
                flash(u'Die Nachricht wurde wiederhergestellt.', True)
                message = None
    else:
        message = None
    entries = PrivateMessageEntry.objects.filter(
        user=request.user,
        folder=PRIVMSG_FOLDERS[folder][0]
    )
    return {
        'entries': list(entries),
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
    form = PrivateMessageForm()
    if request.method == 'POST':
        form = PrivateMessageForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                recipient_names = set(r.strip() for r in \
                                      d['recipient'].split(';') if r)
                recipients = []
                for recipient in recipient_names:
                    user = User.objects.get(username__exact=recipient)
                    if user.id == request.user.id:
                        flash(u'Du kannst dir selber keine Nachrichten '
                              u'schicken.', False)
                        recipient_names = []
                    recipients.append(user)
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
                msg.send(recipients)
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
                        send_notification(recipient, u'Neue private Nachricht'
                                   u' von %s' % (request.user.username), text)
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
            pass
        else:
            try:
                entry = PrivateMessageEntry.objects.get(user=request.user,
                    message=int(reply_to or forward))
                msg = entry.message
                data['subject'] = msg.subject.lower().startswith(u're: ') and \
                                  msg.subject or u'Re: %s' % msg.subject
                if reply_to:
                    data['recipient'] = msg.author.username
                data['text'] = quote_text(msg.text, msg.author)
                form = PrivateMessageForm(initial=data)
            except (PrivateMessageEntry.DoesNotExist):
                pass
        if username:
            form = PrivateMessageForm(initial={'recipient': username})
    return {
        'form': form
    }


@templated('portal/memberlist.html')
def memberlist(request, page=1):
    """
    Shows the memberlist.

    `page` represents the current page in the pagination.
    """
    table = Sortable(User.objects.all(), request.GET, 'id')
    pagination = Pagination(request, table.get_objects(), page, 15,
        href('portal', 'users'))
    set_session_info(request, u'schaut sich die Mitgliederliste an.',
                     'Mitgliederliste')
    return {
        'users':        pagination.objects,
        'pagination':   pagination,
        'table':        table
    }


@templated('portal/grouplist.html')
def grouplist(request, page=1):
    """
    Shows the group list.

    `page` represents the current page in the pagination.
    """
    table = Sortable(Group.objects.all(), request.GET, 'name')
    pagination = Pagination(request, table.get_objects(), page, 15)
    set_session_info(request, u'schaut sich die Gruppenliste an.',
                     'Gruppenliste')
    return {
        'groups':      pagination.objects,
        'group_count': Group.objects.count(),
        'user_groups': request.user.groups.count(),
        'pagination':  pagination,
        'table':       table
    }


@templated('portal/group.html')
def group(request, name, page=1):
    """Shows the informations about the group named `name`."""
    group = Group.objects.get(name=name)
    users = group.user_set

    table = Sortable(users, request.GET, 'id')
    pagination = Pagination(request, table.get_objects(), page, 15)
    set_session_info(request, u'schaut sich die Gruppe '
                     u'„<a href="%s">%s</a>“ an.' % (
        href('portal', 'groups', escape(name)),
        escape(name)
    ))
    return {
        'group':      group,
        'users':      pagination.objects,
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
    r = {'app': app}

    if app == 'forum':
        if request.method == 'POST':
            errors = {}
            data = dict(request.POST.items()) # request.POST.* is a list

            if not data.get('count', '').isdigit():
                errors['count'] ='Bitte eine Zahl zwischen 5 und 100 eingeben!'
                data['count'] = None
            else:
                data['count'] = _feed_count_cleanup(int(data['count']))
            if data.get('component') not in ('*', 'forum', 'topic'):
                errors['component'] = u'Ungültige Auswahl!'
                data['component'] = None
            if data.get('component') == 'forum':
                try:
                    Forum.objects.get(slug=data.get('forum'))
                except:
                    errors['forum'] = u'Bitte ein Forum auswählen!'
                    data['forum'] = None
            if data.get('mode') not in ('full', 'short', 'title'):
                errors['mode'] = u'Bitte eine Art auswählen!'
                data['mode'] = None

            if not errors:
                if data.get('component') == '*':
                    return HttpResponseRedirect(href('forum', 'feeds',
                           data['mode'], data['count']))
                if data.get('component') == 'forum':
                    return HttpResponseRedirect(href('forum', 'feeds', 'forum',
                           data['forum'], data['mode'], data['count']))

            r['form'] = data
            r['errors'] = errors

    if app == 'ikhaya':
        if request.method == 'POST':
            errors = {}
            data = dict(request.POST.items()) # request.POST uses lists
            data.setdefault('category', '*')
            if not data.get('count', '').isdigit():
                errors['count'] ='Bitte eine Zahl zwischen 5 und 100 eingeben!'
                data['count'] = None
            else:
                data['count'] = _feed_count_cleanup(int(data['count']))
            if data.get('mode') not in ('full', 'short', 'title'):
                errors['mode'] = u'Bitte eine Art auswählen!'
                data['mode'] = None
            if data.get('category') != '*':
                try:
                    Category.objects.get(slug=data.get('category'))
                except:
                    errors['category'] = u'Bitte eine Kategorie auswählen!'
                    data['category'] = None

            if not errors:
                if data['category'] == '*':
                    return HttpResponseRedirect(href('ikhaya', 'feeds',
                           data['mode'], data['count']))
                else:
                    return HttpResponseRedirect(href('ikhaya', 'feeds',
                           data['category'], data['mode'], data['count']))
            r['form'] = data
            r['errors'] = errors

    if app == 'planet':
        if request.method == 'POST':
            errors = {}
            data = dict(request.POST.items()) # request.POST uses lists
            if not data.get('count', '').isdigit():
                errors['count'] ='Bitte eine Zahl zwischen 5 und 100 eingeben!'
                data['count'] = None
            else:
                data['count'] = _feed_count_cleanup(int(data['count']))
            if data.get('mode') not in ('full', 'short', 'title'):
                errors['mode'] = u'Bitte eine Art auswählen!'
                data['mode'] = None

            if not errors:
                return HttpResponseRedirect(href('planet', 'feeds',
                       data['mode'], data['count']))
            r['form'] = data
            r['errors'] = errors


    r['forums'] = Forum.objects.all()
    r['ikhaya_categories'] = Category.objects.all()
    return r


def _feed_count_cleanup(n):
    COUNTS = (5, 10, 15, 20, 25, 50, 75, 100)
    if n in COUNTS:
        return n
    if n < COUNTS[0]:
        return COUNTS[0]
    for i in range(len(COUNTS)):
        if n < COUNTS[i]:
            return n - COUNTS[i-1] < COUNTS[i] - n and COUNTS[i-1] or COUNTS[i]
    return COUNTS[-1]


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
    days = calendar_entries_for_month(year, month)
    days = [(date(year, month, day), events) for day, events in days.items()]

    return {
        'days': days,
        'year': year,
        'month': month,
        'today': datetime.utcnow().date(),
        'MONTHS': dict(list(enumerate([''] + MONTHS))[1:]),
        'WEEKDAYS': dict(enumerate(WEEKDAYS)),
    }


@templated('portal/calendar_overview.html')
def calendar_overview(self):
    events = Event.objects.order_by('date').filter(date__gt=datetime.utcnow())[:10]
    return {
        'events': events,
        'year': datetime.utcnow().year,
        'month': datetime.utcnow().month,
        'MONTHS': dict(list(enumerate([''] + MONTHS))[1:]),
        'WEEKDAYS': dict(enumerate(WEEKDAYS)),
    }


@templated('portal/calendar_detail.html')
def calendar_detail(self, slug):
    try:
        event = Event.objects.get(slug=slug)
    except Event.DoesNotExist:
        raise PageNotFound
    return {
        'event': event,
        'MONTHS': dict(list(enumerate([''] + MONTHS))[1:]),
        'WEEKDAYS': dict(enumerate(WEEKDAYS)),
    }


@templated('portal/open_search.xml', content_type='text/xml; charset=utf-8')
def open_search(self, app):
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
            text =u"'''URL:''' %s" % data['url']
            if request.user.id != 1:
                text += (u" [[BR]]\n'''Benutzer:''' [%s %s]" % (
                    request.user.get_absolute_url(),
                    escape(request.user.username)
                ))
            text += u'\n\n%s' % data['text']
            trac = Trac()
            trac.submit_new_ticket(
                keywords='userreport',
                summary=data['title'],
                description = text,
                component = '-',
                ticket_type = 'userreport',
            )

#             uer = UserErrorReport()
#             uer.title = data['title']
#             uer.text = data['text']
#             uer.url = data['url']
#             uer.date = datetime.utcnow()
#             if request.user.username != 'anonymous':
#                 uer.reporter = request.user
#             uer.save()
            flash(u'Vielen Dank, deine Fehlermeldung wurde gespeichert! '\
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
