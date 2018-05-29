import aiohttp
from collections import UserList


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
    empty `Obj` instances are considered to be ``False``.

    You can convert `Obj` instances back to ``dict`` with `.to_dict()`.

    If a member name is a reserved keyword, like ``from``, add a trailing
    underscore, like ``from_``.
    """
    def __init__(self, **kwargs):
        self.__dict__ = {k: Obj(**v) if isinstance(v, dict) else (
            Lst(v) if isinstance(v, list) else v) for k, v in kwargs.items()}

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


class Lst(Obj, UserList):
    """
    Like `Obj` but for lists.
    """
    def __init__(self, original):
        Obj.__init__(self)
        UserList.__init__(self, (Obj(**x) if isinstance(x, dict) else (
            Lst(x) if isinstance(x, list) else x) for x in original))


class Bot:
    """
    Class to easily invoke Telegram API's bot methods.

    The methods are accessed as if they were functions of the class,
    and these always return an `Obj` or `Lst` instance with ``.ok``
    set to either ``True`` or its previous value.

    Keyword arguments are used to construct an `Obj` instance to
    save the caller from creating it themselves.

    For instance:
        >>> import asyncio
        >>> rc = asyncio.get_event_loop().run_until_complete
        >>> bot = Bot(...)
        >>> print(bot.getMe())
        >>> message = rc(bot.sendMessage(chat_id=10885151, text='Hi Lonami!'))
        >>> if message.ok:
        ...     print(message.chat.first_name)
        ...
        >>>
    """
    def __init__(self, token, timeout=10):
        self.token = token
        self.timeout = timeout

    def __getattr__(self, method_name):
        async def request(**kwargs):
            url = 'https://api.telegram.org/bot{}/{}'\
                  .format(self.token, method_name)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                            url, json=kwargs, timeout=self.timeout) as r:
                        deco = await r.json()
                        if deco['ok']:
                            deco = deco['result']
            except Exception as e:
                return Obj(ok=False, error_code=-1,
                           description=str(e), error=e)
            else:
                if isinstance(deco, dict):
                    deco['ok'] = deco.get('ok', True)
                    obj = Obj(**deco)
                elif isinstance(deco, list):
                    obj = Lst(deco)
                    obj.ok = True
                else:
                    obj = deco
                return obj
        return request


__all__ = ['Obj', 'Lst', 'Bot']
