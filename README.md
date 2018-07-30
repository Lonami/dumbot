# dumbot
dumb async telegram bot for python 3.


# installation
install dependencies:
```sh
pip install aiohttp
```

then simply add `dumbot.py` to your project.


# usage

### basic
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

### files
```python

async def main():
    ...
    await bot.sendDocument(chat_id=10885151, file=dict(
        type='document',
        file='/home/lonami/holiday.jpg'
    ))
```

### updates
```python
async def on_update(bot, update):
    await self.sendMessage(
        chat_id=update.message.chat.id,
        text=update.message.text[::-1]
    )


...
bot.on_update = on_update
bot.run()
```

### subclassing
```python
class Subbot(Bot):
    async def init(self):
        self.me = await self.getMe()

    async def on_update(self, update):
        await self.sendMessage(
            chat_id=update.message.chat.id,
            text='i am alive'
        )

Subbot(token).run()
```

# extra
if you're concerned about speed you can `pip install cchardet aiodns`
as suggested in https://docs.aiohttp.org/en/stable/index.html.

# faq

### what methods are available?
https://core.telegram.org/bots/api.

### can i send opened files or bytes directly?
yes.

### can i change a document's filename or mime?
yes, with `name` or `mime` fields in the `dict`.

### how can i handle exceptions?
there aren't, simply check the `.ok` property.

### what's the return value?
a magic object, accessing unknown properties returns a false-y magic object:

```python
from dumbot import Obj

lonami = Obj(name='lonami', hobby='developer')
print(lonami.name, 'is', lonami.age or 20)

lonami.friend.name = 'kate'
print(lonami.friend)
```

### what do you have against uppercase?

scary. there would be less upper case if it weren't for
python's naming conventions or telegram's for that matter.
