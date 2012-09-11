""":mod:`trellogrove` --- Trello-Grove Notibot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import json
import logging
import os.path
import urllib
import urlparse

from google.appengine.api.urlfetch import fetch
from google.appengine.ext.db import Model, StringProperty, put
from google.appengine.ext.deferred import defer
from jinja2 import Environment, FileSystemLoader
from webapp2 import RequestHandler, WSGIApplication


class Setting(Model):
    """Settings pair."""

    name = StringProperty(required=True, indexed=True)
    value = StringProperty(multiline=True)


def has_settings_complete():
    """Returns ``True`` only if the all settings are completely filled."""
    settings = get_settings()
    return (settings.get('trello.app_key') and
            settings.get('trello.oauth_token') and
            settings.get('grove.channel_token'))


def get_settings(name=None):
    """Gets the current settings as dictionary."""
    pairs = Setting.all()
    if name:
        return pairs.filter('name =', name).get().value
    return dict((pair.name, pair.value) for pair in pairs if pair.name)


def update_settings(settings):
    """Updates the settings."""
    pairs = Setting.all().filter('name IN', settings.keys())
    objects = []
    for pair in pairs:
        pair.value = settings.pop(pair.name)
        objects.append(pair)
    for key, value in settings.iteritems():
        pair = Setting(name=key, value=value)
        objects.append(pair)
    put(objects)


class Action(dict):
    """The rich dictionary to represent Trello actions."""

    @classmethod
    def all(cls, since=None):
        """Polls all actions from Trello."""
        boards = fetch('https://trello.com/1/members/me/boards?' + cls.sign())
        result = []
        board_url = 'https://trello.com/1/boards/{0}/actions?{1}{2}'
        since_query = 'since=' + since + '&' if since else ''
        for board in json.loads(boards.content):
            url = board_url.format(board['id'], since_query, cls.sign())
            actions = json.loads(fetch(url).content)
            result.extend(map(cls, actions))
        result.sort(key=lambda d: d['date'])
        return result

    @staticmethod
    def sign():
        """Generates a signing query."""
        fmt = 'key={0[trello.app_key]}&token={0[trello.oauth_token]}'
        return fmt.format(get_settings())

    @property
    def id(self):
        """The action id."""
        return self['id']

    @property
    def url(self):
        """The url of the action."""
        return 'https://trello.com/1/actions/' + str(self.id)

    @property
    def data(self):
        """The data dictionary."""
        return self['data']

    @property
    def user(self):
        """The agent."""
        return self['memberCreator']['fullName']

    @property
    def card(self):
        """The card name."""
        return self.data.get('card', {}).get('name')

    @property
    def link_url(self):
        if 'card' in self.data:
            fmt = 'https://trello.com/card/-/{0.data[board][id]}/' \
                  '{0.data[card][idShort]}'.format(self)
        else:
            fmt = 'https://trello.com/board/-/{0.data[board][id]}'
        return str(fmt.format(self))

    @property
    def board(self):
        """The board name."""
        return self.data['board']['name']

    def is_change(self):
        """Returns whether the action is about change of card."""
        return self['type'] in ('changeCard', 'updateCard')

    def is_move(self):
        """Returns whether the action is about moving position of card."""
        if not self.is_change():
            return False
        return 'listBefore' in self.data.get('old', {})

    def is_create(self):
        """Returns whether the noti is about new card."""
        return self['type'] == 'createdCard'

    def is_close(self):
        """Returns whether the noti is about closing of card."""
        if not self.is_change():
            return False
        return self.data.get('old', {}).get('closed', False)

    def is_comment(self):
        """Returns whether the noti is about new comment."""
        return self['type'] == 'commentCard'

    def is_attachment(self):
        """Returns whether the action is about new attachment."""
        return self['type'] == 'addAttachmentToCard'

    def __unicode__(self):
        if self.is_close():
            msg = u'{0.user} closed card "{0.card}" in "{0.board}".'
        elif self.is_move():
            msg = u'{0.user} moved card "{0.card}" from ' \
                  u'"{0.data[listBefore][name]}" to ' \
                  u'"{0.data[listAfter][name]}" ({0.board} board).'
        elif self.is_create():
            msg = u'{0.user} created card "{0.card}" into ' \
                  u'"{0.data[list][name]}" ({0.board} board)'
        elif self.is_comment():
            msg = u'{0.user} commented to card "{0.card}" ({0.board} board)'
        elif self.is_attachment():
            msg = u'{0.user} attach a file ({0.data[attachment][url]}) to ' \
                  u'card "{0.card}" ({0.board} board)'
        else:
            msg = u'{0.user} {0[type]} {0.card} ({0.board} board)'
            logger = logging.getLogger(__name__ + '.Action.__unicode__')
            logger.warn(repr(self))
        return msg.format(self)

    def __repr__(self):
        r = super(Action, self).__repr__()
        return 'Action({0})'.format(r)


#: (:class:`jinja2.Environment`) The Jinja2 environment.
jinja_env = Environment(
    loader=FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')
    )
)


class BaseHandler(RequestHandler):
    """The common base request handler."""

    def render_template(self, template_name, **context):
        """Finds the template and renders it with the given ``context``."""
        template = jinja_env.get_template(template_name)
        self.response.out.write(template.render(**context))


class SettingPage(BaseHandler):
    """Initial settings page."""

    def get(self):
        auth_url = urlparse.urljoin(self.request.url, '/trello-oauth')
        self.render_template('setting.html',
                             settings=get_settings(),
                             auth_url=auth_url,
                             all_filled=has_settings_complete())

    def post(self):
        update_settings({
            'trello.app_key': self.request.POST['trello.app_key'],
            'grove.channel_token': self.request.POST['grove.channel_token']
        })
        return self.get()


class TrelloOAuthPage(BaseHandler):
    """Saves Trello OAuth token."""

    def get(self):
        self.render_template('trello_oauth.html')

    def post(self):
        update_settings({
            'trello.oauth_token': self.request.POST['token']
        })
        self.redirect('/')


def poll():
    """Does polling from Trello and posts messages to Grove."""
    settings = get_settings()
    latest = settings.get('trello.latest_date')
    actions = Action.all(since=latest)
    if actions:
        latest = max(action['date'] for action in actions)
        update_settings({'trello.latest_date': latest})
        token = settings['grove.channel_token']
        for noti in actions:
            post(unicode(noti), noti.link_url, token)


def post(message, link_url, token):
    """Posts a message to the Grove channel."""
    payload = {
        'service': 'Trello',
        'message': message.encode('utf-8') + ' \xe2\x80\x94 ' + link_url,
        'url': link_url,
        'icon_url': 'https://trello.com/favicon.ico'
    }
    response = fetch(
        'https://grove.io/api/notice/{0}/'.format(token),
        payload=urllib.urlencode(payload),
        method='POST'
    )
    if response.status_code != 200:
        logger = logging.getLogger(__name__ + '.post')
        logger.warn('%d: %s', response.status_code, response.content)


class PollPage(BaseHandler):
    """Does polling notifcations from Trello."""

    def get(self):
        if has_settings_complete():
            defer(poll)
        else:
            self.error(500)


#: (:class:`webapp2.WSGIApplication`) The WSGI callable entrypoint.
app = WSGIApplication([
    ('/', SettingPage),
    ('/trello-oauth', TrelloOAuthPage),
    ('/poll', PollPage)
], debug=True)
