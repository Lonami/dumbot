import json
import urllib.request
import urllib.parse


class Obj:
    """
    Class to avoid dictionary-like access and ``None`` values.

    For instance:
        >>> lonami = Obj(name='lonami', hobby='developer')
        >>> print(lonami.name, 'is', lonami.age or 20)
        >>>
        >>> lonami.friend.name = 'kate'
        >>> print(lonami.friend)
        >>>

    If you expect a different type you should use ``or value``, as
    empty ``Obj`` instances are considered to be ``False``.

    You can convert ``Obj`` instances back to ``dict`` with ``.to_dict()``.

    If a member name is a reserved keyword, like ``from``, add a trailing
    underscore, like ``from_``.
    """
    def __init__(self, **kwargs):
        self.__dict__ = {k: Obj(**v) if isinstance(v, dict) else v
                         for k, v in kwargs.items()}

    def __getattr__(self, name):
        name = name.rstrip('_')
        obj = self.__dict__.get(name, None)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return repr(self.to_dict())

    def __bool__(self):
        return bool(self.__dict__)

    def to_dict(self):
        return {k: v.to_dict() if isinstance(v, Obj) else v
                for k, v in self.__dict__.items()}


class Bot:
    """
    Class to easily invoke Telegram API's bot methods.

    The methods are accessed as if they were functions of the class,
    and these always return an ``Obj`` instance with ``.ok`` set to
    either ``True`` or its previous value.

    Keyword arguments are used to construct an ``Obj`` instance to
    save the caller from creating it themselves.

    For instance:
        >>> bot = Bot(...)
        >>> print(bot.getMe())
        >>> message = bot.sendMessage(chat_id=10885151, text='Hi Lonami!')
        >>> if message.ok:
        ...     print(message.chat.first_name)
        ...
        >>>
    """
    def __init__(self, token, timeout=10):
        self.token = token
        self.timeout = 10

    def __getattr__(self, method_name):
        def request(**kwargs):
            obj = json.dumps(Obj(**kwargs).to_dict()).encode('utf-8')
            url = 'https://api.telegram.org/bot{}/{}'\
                  .format(self.token, method_name)
            try:
                reqs = urllib.request.urlopen(urllib.request.Request(
                    url, headers={'Content-Type': 'application/json'}
                ), data=obj, timeout=self.timeout)
            except Exception as e:
                return Obj(ok=False, cause='conn', error=e)
            try:
                resp = reqs.read()
            except Exception as e:
                return Obj(ok=False, cause='read', error=e)
            try:
                data = str(resp, encoding='utf-8')
            except Exception as e:
                return Obj(ok=False, cause='utf8', error=e)
            try:
                deco = json.loads(data)
                if deco['ok']:
                    deco = deco['result']
                    deco['ok'] = deco.get('ok', True)
            except Exception as e:
                return Obj(ok=False, cause='json', error=e)
            else:
                return Obj(**deco)
        return request
