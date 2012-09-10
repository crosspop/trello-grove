""":mod:`trellogrove` --- Trello-Grove NotiBot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import os.path
import urlparse

from google.appengine.ext.db import Model, StringProperty, put
from jinja2 import Environment, FileSystemLoader
from webapp2 import RequestHandler, WSGIApplication


class Setting(Model):
    """Settings pair."""

    name = StringProperty(required=True, indexed=True)
    value = StringProperty(multiline=True)

def get_settings():
    """Gets the current settings as dictionary."""
    pairs = Setting.all()
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
        settings = get_settings()
        auth_url = urlparse.urljoin(self.request.url, '/trello-oauth')
        all_filled = (settings.get('trello.app_key') and
                      settings.get('trello.oauth_token') and
                      settings.get('grove.channel_token'))
        self.render_template('setting.html',
                             settings=settings,
                             auth_url=auth_url,
                             all_filled=all_filled)

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


#: (:class:`webapp2.WSGIApplication`) The WSGI callable entrypoint.
app = WSGIApplication([
    ('/', SettingPage),
    ('/trello-oauth', TrelloOAuthPage)
], debug=True)
