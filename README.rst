Trello-Grove Notibot
====================

.. image:: https://raw.github.com/crosspop/trello-grove/master/screenshot.png

This is a small bot which relays Trello_ notifications to the Grove_ channel.
It uses `Google App Engine <GAE>`_.

.. _Trello: http://trello.com/
.. _Grove: http://grove.io/
.. _GAE: https://developers.google.com/appengine/


Installtion
-----------

1. Download and install `Google App Engine`_ Python SDK.
2. Change the ``name`` field of ``app.yaml``.
3. Deploy__ the bot using ``appcfg.py``.
4. Go to ``http://<app-name>.appspot.com/``.
   It will requires you to authenticate.
5. Fill Trello app key (you can make it here__) and Grove channel token.
6. Authenticate Trello account using OAuth.
7. Done.  Notibot will post notification messages to the channel soon
   (less than 2 minutes).

.. image:: https://raw.github.com/crosspop/trello-grove/master/settings.png

__ https://developers.google.com/appengine/docs/python/tools/uploadinganapp#Uploading_the_App
__ https://trello.com/1/appKey/generate


Open source
-----------

It's initially made for private use by Crosspop_, written by `Hong Minhee`_,
and distributed under `MIT license`__.  The source code can be found
the following GitHub repository:

https://github.com/crosspop/trello-grove

.. _Crosspop: http://crosspop.in/
.. _Hong Minhee: http://dahlia.kr/
__ http://crosspop.mit-license.org/
