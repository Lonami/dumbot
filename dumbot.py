"""
MIT License

Copyright (c) 2018 Lonami

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import asyncio
import io
import logging
import re

import aiohttp

try:
    import ujson as json_mod
except ImportError:
    import json as json_mod


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
        obj = self.__dict__.get(name)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __getitem__(self, name):
        obj = self.__dict__.get(name)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __iter__(self):
        return iter(())

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return repr(self.to_dict())

    def __bool__(self):
        return bool(self.__dict__)

    def __contains__(self, item):
        return item in self.__dict__

    def __call__(self, *a, **kw):
        return Obj()

    def to_dict(self):
        return {k: v.to_dict() if isinstance(v, (Obj, Lst)) else v
                for k, v in self.__dict__.items()}


class Lst(list):
    """
    Like `Obj` but for lists.
    """
    def __init__(self, iterable=()):
        list.__init__(self, (Obj(**x) if isinstance(x, dict) else (
            Lst(x) if isinstance(x, list) else x) for x in iterable))

    def __getattr__(self, name):
        name = name.rstrip('_')
        obj = self.__dict__.get(name)
        if obj is None:
            obj = Obj()
            self.__dict__[name] = obj
        return obj

    def __repr__(self):
        return super().__repr__() + repr(self.to_dict())

    def to_dict(self):
        return [v.to_dict() if isinstance(v, (Obj, Lst)) else v
                for v in self]


_cmd_attr_name = 'dumbot.cmd'
_inb_attr_name = 'dumbot.inb'


def command(item=None):
    """
    Marks the decorated function as a command callback.
    If no text is given, the function's name is used as `/name`.

    >>> import dumbot
    >>>
    >>> class Bot(dumbot.Bot):
    >>>     @dumbot.command('start')
    >>>     async def start(self, update):
    >>>         await self.sendMessage(chat_id=update.message.chat.id, text='Hey!')
    >>>
    >>>     @dumbot.command
    >>>     async def help(self, update):
    >>>         await self.sendMessage(chat_id=update.message.chat.id, text='No help')
    """
    def decorator(func):
        setattr(func, _cmd_attr_name, (
            item if isinstance(item, str) else func.__name__).lower())
        return func

    return decorator(item) if callable(item) else decorator


def inline_button(pattern):
    """
    Marks the decorated function as an inline button's data callback.
    Unlike `command` the pattern must always be given because it's a regex.

    >>> import dumbot
    >>>
    >>> class Bot(dumbot.Bot):
    >>>     @dumbot.inline_button(r'day(\\d+)')
    >>>     async def select_day(self, update, match):
    >>>         await self.sendMessage(chat_id=update.message.chat.id,
    >>>                                text=f'Selected day {match.group(1)}')
    """
    def decorator(func):
        setattr(func, _inb_attr_name, re.compile(pattern + '$').match)
        return func

    return decorator


class UnauthorizedError(ValueError):
    """Invalid bot token."""


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
    def __init__(self, token, *, timeout=10, loop=None, sequential=False):
        self._token = token
        self._timeout = timeout
        self._last_update = 0
        self._sequential = sequential
        self._loop = loop or asyncio.get_event_loop()
        self._me = None
        self._session = None
        self._cmd_triggers = {}
        self._inb_triggers = []
        self._log = logging.getLogger(
            'dumbot{}'.format(token[:token.index(':')]))

    def __getattr__(self, method_name):
        if not any(c.isupper() for c in method_name):
            # All method calls are dynamic names. It's very easy to
            # accidentally try to access a member (snake_case) that doesn't
            # exist, but this method would swallow the error. All methods in
            # the API have at least one upper-case letter in their name, so
            # if the method name doesn't have one, the user probably accessed
            # an attribute that doesn't exist yet. Let it raise.
            return super().__getattribute__(method_name)

        async def request(**kwargs):
            fp = None
            file = kwargs.pop('file', None)
            if not file:
                json = kwargs
                data = None
            else:
                json = None
                data = aiohttp.FormData()
                for k, v in kwargs.items():
                    data.add_field(k, str(v) if isinstance(v, int) else v)

                if not isinstance(file['file'], (
                        io.IOBase, bytes, bytearray, memoryview)):
                    file['file'] = fp = open(file['file'], 'rb')

                data.add_field(
                    file['type'],
                    file['file'],
                    filename=file.get('name'),
                    content_type=file.get('mime')
                )

            url = 'https://api.telegram.org/bot{}/{}'\
                  .format(self._token, method_name)
            try:
                async with self._session.post(url,
                                              json=json,
                                              data=data,
                                              timeout=self._timeout) as r:
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
            finally:
                if fp:
                    fp.close()

        return request

    async def init(self):
        pass

    async def _init(self):
        self._session = aiohttp.ClientSession(
            loop=self._loop,
            json_serialize=json_mod.dumps
        )
        self._me = await self.getMe()
        self._cmd_triggers.clear()
        self._inb_triggers.clear()
        self._add_commands(self, self)
        await self.init()

    def _add_commands(self, *items):
        """
        Registers all the functions in the given instance or modules.
        """
        def add_cmd(to):
            trigger = getattr(to, _cmd_attr_name, None)
            if trigger:
                self._cmd_triggers[trigger] = to
            else:
                trigger = getattr(to, _inb_attr_name, None)
                if trigger:
                    self._inb_triggers.append((trigger, to))

        for item in items:
            if not add_cmd(item):
                for name in dir(item):
                    add_cmd(getattr(item, name))

    def run(self):
        if self._loop.is_running():
            return self._run()
        try:
            return self._loop.run_until_complete(self._run())
        except KeyboardInterrupt:
            return self._loop.run_until_complete(self._disconnect())

    async def _run(self):
        try:
            await self._init()
            while self._running:
                updates = await self.getUpdates(
                    offset=self._last_update + 1, timeout=self._timeout)
                if not updates.ok:
                    if not isinstance(updates.error, asyncio.TimeoutError):
                        if updates.error_code == 401:
                            raise UnauthorizedError

                        self._log.warning('update result was not ok %s',
                                          updates)
                    continue
                if not updates:
                    continue

                self._last_update = updates[-1].update_id
                if self._sequential:
                    for update in updates:
                        await self._on_update(update)
                else:
                    for update in updates:
                        self._loop.create_task(self._on_update(update))
        finally:
            await self._disconnect()

    @property
    def _running(self):
        return self._session and not self._session.closed

    async def _on_update(self, update):
        try:
            cq = update.callback_query
            if cq:
                cb, match = self._get_inb(cq.data)
                if cb:
                    await cb(update, match)
                else:
                    await self.on_update(update)

                # Always answer callback queries *after* user's callback
                # to stop the spinning progress bar. This will do nothing
                # if the user already answered it themselves with another
                # parameters, so it's good practice and very convenient.
                await self.answerCallbackQuery(callback_query_id=cq.id)
                return

            cb = self._get_cmd(update.message) or self.on_update
            await cb(update)
        except Exception:
            self._log.exception('unhandled exception handling %s', update)

    async def on_update(self, update):
        pass

    def _get_cmd(self, msg):
        if not self._cmd_triggers or msg.forward_date:
            return

        ent = (msg.entities or msg.caption_entities)[0]
        txt = (msg.text or msg.caption) or ''
        if ent.offset == 0 and ent.type == 'bot_command':
            cmd = txt[1:ent.length].casefold()
            usr = cmd.find('@')
            if usr == -1:
                return self._cmd_triggers.get(cmd)
            elif cmd[usr + 1:] == self._me.username.casefold():
                return self._cmd_triggers.get(cmd[:usr])

    def _get_inb(self, data):
        for trigger, func in self._inb_triggers:
            match = trigger(data)
            if match:
                return func, match

        return None, None

    async def disconnect(self):
        pass

    async def _disconnect(self):
        try:
            await self.disconnect()
        except Exception:
            self._log.exception('unexpected error in subclassed disconnect')

        await self._session.close()
        self._session = None

    def __del__(self):
        try:
            if self._session and not self._session.closed:
                if self._session._connector_owner:
                    self._session._connector.close()
                self._session._connector = None
        except Exception:
            self._log.exception('failed to close connector')

    async def __aenter__(self):
        await self._init()

    async def __aexit__(self, *args):
        await self._disconnect()


__all__ = ['Obj', 'Lst', 'Bot']
