# dumbot

dumb async telegram bot for python 3.

# installation

add `dumbot.py` to your project or `pip install dumbot`.

# usage

## basic

```python
import asyncio
from dumbot import Bot

async def main():
    bot = Bot(token)
    print(await bot.getMe())
    msg = await bot.sendMessage(chat_id=10885151, text='hi lonami')
    if msg.ok:
        print('message sent', msg)
    else:
        print('something went wrong!', msg)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

## files

```python

async def main():
    ...
    await bot.sendDocument(chat_id=10885151, file=dict(
        type='document',
        file='/home/lonami/holiday.jpg'
    ))
```

## updates

```python
async def on_update(update):
    await bot.sendMessage(
        chat_id=update.message.chat.id,
        text=update.message.text[::-1]
    )

...
bot.on_update = on_update
bot.run()
```

## subclassing

```python
class Subbot(Bot):
    async def init(self):
        self.me = await self.getMe()

    async def on_update(self, update):
        await self.sendMessage(
            chat_id=update.message.chat.id,
            text='i am {}'.format(self.me.username)
        )

Subbot(token).run()
```

# faq

## what methods are available?

https://core.telegram.org/bots/api.

## can i send opened files or bytes directly?

yes.

## can i change a document's filename or mime?

yes, with `name` or `mime` fields in the `dict`.

## how can i handle exceptions?

there aren't, simply check the `.ok` property.

## what's the return value?

a magic object, accessing unknown properties returns a false-y magic object:

```python
from dumbot import Obj

lonami = Obj(name='lonami', hobby='developer')
print(lonami.name, 'is', lonami.age or 20)

lonami.friend.name = 'kate'
print(lonami.friend)
```

## no dependencies?

python alone is enough dependencies.

## how does this work without urllib or aiohttp?

it's simple, we construct http requests manually.

## why would you reimplement http?

it's a fun good learning experience, and avoids bloat dependencies.

## what do you have against uppercase?

scary. there would be less upper case if it weren't for
python's naming conventions or telegram's for that matter.
