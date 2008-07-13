# -*- coding: utf-8 -*-
"""
    ligator.main
    ~~~~~~~~~~~~

    Ligator is a bridge between jabber and irc channels.

    :copyright: Copyright 2008 by Benjamin Wiegand, Florian Apolloner.
    :license: GNU GPL.
"""
import xmpp
import irclib
from md5 import md5
from time import sleep


class Channel(object):
    #: a list of the users belonging to the bot
    managed_users = []
    #: a list of the users not belonging to the bot
    unmanaged_users = []

    @property
    def users(self):
        return self.managed_users + self.unmanaged_users

    def connect(self, control):
        """
        Join the channel with the main user.
        """

    def disconnect(self):
        """
        Leave the channel with all users.
        """

    def join(self, username):
        """
        Join the channel with a special user.
        """

    def leave(self, username):
        """
        Leave the channel with a special user.
        """

    def send_message(self, username, message):
        """
        Write a message of a user into the channel
        """

    def process(self):
        """
        This function is called periodically to get the new events.
        """


class Client(xmpp.client.Client):
    def __init__(self, jid, password, channel):
        self.jid = xmpp.protocol.JID(jid)
        self.password = password
        self.channel = channel
        xmpp.client.Client.__init__(self, self.jid.getDomain(), debug=[])

    def connect(self):
        """
        Connect Handler
        """
        xmpp.client.Client.connect(self)
        self.auth(self.jid.getNode(), self.password,
                  resource=self.jid.getResource())
        self.p = xmpp.protocol.Presence(to=self.channel)
        self.p.setTag('x', namespace=xmpp.NS_MUC).setTagData('password','')
        self.p.getTag('x').addChild('history',
            {'maxchars': '0','maxstanzas': '0'})
        self.send(self.p)


class JabberChannel(Channel):
    unmanaged_users = []
    managed_users = []
    clients = {}

    def __init__(self, account, password, channel, main_user_name):
        self.account = account
        self.password = password
        self.channel = channel
        self.main_user_name = main_user_name

    def connect(self, control):
        self.control = control
        client = self._join(self.main_user_name)
        client.RegisterHandler("message", self.recieve_message)
        client.RegisterHandler("presence", self.handle_presence)
        self.main_client = client

    def disconnect(self):
        self.main_client.disconnect()
        for username in self.clients.keys():
            self.leave(username)

    def _join(self, username):
        resource = 'user_%s' % username
        channel = '%s/%s' % (self.channel, username)
        client = Client('%s/%s' % (self.account, resource),
                        self.password, channel)
        client.connect()
        return client

    def join(self, username):
        self.clients[username] = self._join(username)
        self.managed_users.append(username)

    def leave(self, username):
        self.clients[username].disconnect()
        del self.clients[username]
        self.managed_users.remove(username)

    def send_message(self, username, message):
        self.clients[username].send(xmpp.protocol.Message(self.channel,
                                    message, typ="groupchat"))

    def process(self):
        self.main_client.Process()

    def recieve_message(self, session, message):
        username = xmpp.protocol.JID(message.getFrom()).getResource()
        if username not in self.managed_users:
            text = message.getBody()
            print "jabber:", username, text
            self.control.send_message(username, text)

    def handle_presence(self, dispatcher, event):
        username = xmpp.protocol.JID(event.getFrom()).getResource()
        if event.getStatus() == "offline":
            self.unmanaged_users.remove(username)
            self.control.leave(username)
        else:
            if username not in self.users:
                self.unmanaged_users.append(username)
                self.control.join(username)


def filter_duplicates(f):
    """
    Since we are in one channel with a few users at the same time, irclib
    sends duplicate events. This decorator filters them out and sends every
    event only once.
    """
    def decorator(self, connection, event, *args, **kwargs):
        key = md5('|'.join([event.source() or '', event.target() or '']
                           + event.arguments() or '')).hexdigest()
        if self.msgs.setdefault(key, 0) == 0:
            f(self, connection, event, *args, **kwargs)
        self.msgs[key] += 1
        if self.msgs[key] == len(self.managed_users) + 1:
            del self.msgs[key]
    return decorator


class IRCChannel(Channel):
    #: contains a user --> server mapping
    servers = {}
    msgs = {}
    unmanaged_users = []
    managed_users = []

    def __init__(self, server, port, channel, main_user_name,
                 main_user_password=None, channel_password=None):
        self.server = server
        self.port = port
        self.channel = channel
        self.channel_password = channel_password
        self.main_user_name = main_user_name
        self.main_user_password = main_user_password

    def connect(self, control):
        self.control = control
        self.irc = irclib.IRC()
        self.main_server = self._join(self.main_user_name,
                                      self.main_user_password)
        self.main_server.add_global_handler('pubmsg', self.recieve_message)
        self.main_server.add_global_handler('join', self.handle_join)
        self.main_server.add_global_handler('namreply', self.handle_names)
        quit = lambda key: lambda c, e: self.handle_quit(c, e, key)
        for key in ['quit', 'part', 'kick']:
            self.main_server.add_global_handler(key, quit(key))

        self.main_server.send_raw('NAMES %s' % self.channel)

    def disconnect(self):
        self.irc.disconnect_all()

    def _join(self, username, password=None):
        server = self.irc.server()
        server.connect(self.server, self.port, username, password)
        server.join(self.channel)
        return server

    def join(self, username):
        print 'do join', username
        self.managed_users.append(username)
        server = self._join(username)
        self.servers[username] = server

    def leave(self, username):
        print 'do leave', username
        server = self.servers[username]
        del self.servers[username]
        self.managed_users.remove(username)
        server.disconnect('weg')
        server.close()

    def send_message(self, username, message):
        self.servers[username].privmsg(self.channel, message.encode('utf8'))

    def process(self):
        self.irc.process_once()

    @filter_duplicates
    def recieve_message(self, connection, event):
        print 'recieve message'
        username = event.source().split('!')[0]
        if username not in self.managed_users:
            text = event.arguments()[0]
            self.control.send_message(username, text)

    @filter_duplicates
    def handle_quit(self, connection, event, how):
        print 'recieve', how, event.source()
        if how in ['part', 'quit']:
            username = event.source().split('!')[0]
        else:
            username = event.arguments()[0]
        if username in self.unmanaged_users:
            self.unmanaged_users.remove(username)
            self.control.leave(username)

    @filter_duplicates
    def handle_join(self, connection, event):
        print 'recieve join', event.source()
        username = event.source().split('!')[0]
        if username != self.main_user_name and username not in \
                                            self.managed_users:
            self.unmanaged_users.append(username)
            self.control.join(username)

    @filter_duplicates
    def handle_names(self, connection, event):
        print 'recieve names', event.arguments()
        users = event.arguments()[-1].split()
        for user in users:
            if user not in self.users:
                self.unmanaged_users.append(user)
                self.control.join(user)

class Control(object):
    """
    The `Control` instance provides functions to perform actions in all joined
    channels.
    """
    users = []

    def __init__(self, channels=[]):
        self.channels = channels
        self.usernames = set()
        for channel in channels:
            channel.connect(self)

    def process_forever(self):
        while True:
            for channel in self.channels:
                channel.process()
            sleep(2)

    def send_message(self, username, message):
        for channel in self.channels:
            if username in channel.managed_users:
                channel.send_message(username, message)

    def join(self, username):
        print 'main join', username
        for channel in self.channels:
            if username not in channel.users:
                channel.join(username)
        print 'end main join'

    def leave(self, username):
        for channel in self.channels:
            if username in channel.managed_users:
                channel.leave(username)
        print 'end leave'


if __name__ == '__main__':
    c = Control(channels=[
        JabberChannel('ubuntuusers@jabber.ccc.de', '5b5nt5',
                      'test@conference.ubuntu-jabber.de', 'ligator'),
        IRCChannel('brown.freenode.net', 8000, '#blabla', 'ligator')
    ])
    c.process_forever()
