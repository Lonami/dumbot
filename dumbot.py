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
        await self.init()

    def run(self):
        if self._loop.is_running():
            return self._run()
        else:
            return self._loop.run_until_complete(self._run())

    async def _run(self):
        try:
            await self._init()
            while self._running:
                updates = await self.getUpdates(
                    offset=self._last_update + 1, timeout=self._timeout)
                if not updates.ok:
                    if not isinstance(updates.error, asyncio.TimeoutError):
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

        except KeyboardInterrupt:
            pass
        finally:
            await self.disconnect()

    @property
    def _running(self):
        return self._session and not self._session.closed

    async def _on_update(self, update):
        try:
            await self.on_update(update)
        except Exception:
            self._log.exception('unhandled exception handling %s', update)

    async def on_update(self, update):
        pass

    async def disconnect(self):
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


__all__ = ['Obj', 'Lst', 'Bot']
