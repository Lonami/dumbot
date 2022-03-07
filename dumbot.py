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
import base64
import itertools
import logging
import mimetypes
import collections
import re
import sys
import uuid

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


def _encode_multipart(data, file):
    # We love micro-optimization! Concatenating to b'bytes' is the
    # second fastest behind b''.join(tuple), so we return a list that
    # we can b''.join() once at the end.
    #
    # Unfortunately, a lot of inputs are str and not bytes,
    # so we might as well use f-strings and a single encode step.
    # To make it worse, users may use characters only utf-8 can encode.
    boundary = base64.b64encode(uuid.uuid4().bytes)[:-2].decode('ascii')
    buffer = [
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="{key}"\r\n'
        f'\r\n'
        f'{value}\r\n'.encode('utf-8')
        for key, value in data.items()
    ]

    file_type = file['type']
    name = file.get('name') or getattr(file['file'], 'name', None) or 'unnamed'
    mime = file.get('mime') or mimetypes.guess_type(name)[0] or 'application/octet-stream'

    data = file['file']
    if callable(getattr(data, 'read', None)):
        data = data.read()
    if isinstance(data, str):
        data = data.encode('utf-8')

    buffer.extend((
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="{file_type}"; filename="{name}"\r\n'
        f'Content-Type: {mime}\r\n'
        f'\r\n'.encode('utf-8'),
        data,
        f'\r\n--{boundary}--'.encode('ascii')
    ))

    return (
        f'Content-Type: multipart/form-data; boundary={boundary}\r\n'
        f'Content-Length: {sum(len(x) for x in buffer)}\r\n'
    ), buffer


def _encode_json(data):
    if not data:
        return '', b''

    body = json_mod.dumps(data, ensure_ascii=True).encode('ascii')
    return (
        'Content-Type: application/json\r\n'
        f'Content-Length: {len(body)}\r\n'
    ), [body]


class UnauthorizedError(ValueError):
    """Invalid bot token."""


class _Stream:
    def __init__(self, pair):
        self.rd, self.wr = pair

    @classmethod
    async def new(cls):
        return cls(await asyncio.open_connection(
            'api.telegram.org', 443, ssl=True))

    async def send(self, data):
        # Member look-up is expensive
        wr = self.wr
        rd = self.rd

        wr.write(data)
        await wr.drain()

        headers = await rd.readuntil(b'\r\n\r\n')
        if headers[-4:] != b'\r\n\r\n':
            raise ConnectionError('Connection closed')

        index = headers.index(b'Content-Length:') + 16
        return await rd.readexactly(int(headers[index:headers.index(b'\r', index)]))

    async def close(self):
        self.wr.close()
        if sys.version_info >= (3, 7):
            # TODO This takes forever (until we're done reading)
            await self.wr.wait_closed()


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
        >>> bot = Bot(...)
        >>> print(bot.getMe())
        >>> message = asyncio.run(bot.sendMessage(chat_id=10885151, text='Hi Lonami!'))
        >>> if message.ok:
        ...     print(message.chat.first_name)
        ...
        >>>

    Arguments:

        token (`str`):
            The bot token to use.

        timeout (`int`):
            The timeout, in seconds, to use when fetching updates.

        sequential (`bool`, optional):
            Whether you want to process updates in sequential order
            or not. The default is to spawn a task for each update.

        max_connections (`int`, optional):
            How many connections can be opened to Telegram servers.
            `aiohttp` has a default of 100 maximum connections, but
            the default value of 4 is reasonable too.
    """
    def __init__(self, token, *, timeout=10,
                 sequential=False, max_connections=4):
        self._post = f'POST /bot{token}/'.encode('ascii')
        self._timeout = timeout
        self._last_update = 0
        self._sequential = sequential
        self._me = None
        self._streams = collections.deque([None] * max_connections)
        self._busy_streams = set()
        self._semaphore = asyncio.Semaphore(max_connections)
        self._running = False
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
            if file:
                # TODO Albums may need multipart/mixed
                # See https://www.w3.org/TR/html401/interact/forms.html#h-17.13.4.2
                headers, body = _encode_multipart(kwargs, file)
            else:
                headers, body = _encode_json(kwargs)

            try:
                # asyncio's writelines is just b''.join().
                # We might as well just do that ourselves.
                payload = await self._request(b''.join((
                    self._post,
                    method_name.encode('ascii'),
                    b' HTTP/1.1\r\n'
                    b'Host: api.telegram.org\r\n',
                    headers.encode('ascii'),
                    b'\r\n',
                    *body
                )))
            except Exception as e:
                return Obj(ok=False, error_code=-1,
                           description=str(e), error=e, payload=None)

            try:
                deco = json_mod.loads(payload)
                if deco['ok']:
                    deco = deco['result']
            except Exception as e:
                return Obj(ok=False, error_code=-1,
                           description=str(e), error=e, payload=payload)
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

    async def _request(self, data):
        # Streams are stored in a deque, to make sure we
        # constantly cycle through and use all connections.
        await self._semaphore.acquire()
        stream = self._streams.popleft()
        self._busy_streams.add(stream)
        try:
            if stream is None:
                stream = await _Stream.new()

            return await stream.send(data)
        finally:
            self._busy_streams.discard(stream)
            self._streams.append(stream)
            self._semaphore.release()

    async def init(self):
        pass

    async def _init(self):
        self._running = True
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
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            return self._run()

        try:
            return asyncio.run(self._run())
        except KeyboardInterrupt:
            asyncio.run(self._disconnect())

    async def _run(self):
        try:
            await self._init()
            while self._running:
                updates = await self.getUpdates(
                    offset=self._last_update + 1, timeout=self._timeout)
                if not updates.ok:
                    if isinstance(updates.error, (
                            asyncio.CancelledError, asyncio.IncompleteReadError, OSError)):
                        # OSError seen:
                        # * ConnectionError
                        # * socket.gaierror
                        if self._running:
                            e = updates.error
                            self._log.warning(
                                    'connection error when fetching updates (%s): %s',
                                    e.__class__.__name__, e)
                        return

                    if updates.error_code == 401:
                        raise UnauthorizedError

                    self._log.warning('update result was not ok %s', updates)
                    continue
                if not updates:
                    continue

                self._last_update = updates[-1].update_id
                if self._sequential:
                    for update in updates:
                        await self._on_update(update)
                else:
                    for update in updates:
                        asyncio.create_task(self._on_update(update))
        except asyncio.CancelledError:
            pass
        finally:
            await self._disconnect()

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
        if not self._cmd_triggers or (msg.forward_date and msg.chat.type != 'private'):
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
        if not self._running:
            return

        try:
            await self.disconnect()
        except Exception:
            self._log.exception('unexpected error in subclassed disconnect')

        self._running = False
        await asyncio.gather(*(stream.close() for stream in itertools.chain(
            self._streams, self._busy_streams) if stream))

        self._streams = collections.deque([None] * len(self._streams))
        self._busy_streams.clear()

    async def __aenter__(self):
        await self._init()

    async def __aexit__(self, *args):
        await self._disconnect()


__all__ = ['Obj', 'Lst', 'Bot']
