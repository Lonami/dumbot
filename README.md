# dumbot
dumb telegram bot for python.

# usage
```python
from dumbot import Bot

bot = Bot(token)
print(bot.getMe())

msg = bot.sendMessage(chat_id=10885151, text='Hi Lonami!')
if msg.ok:
    print('msg sent', msg)
else:
    print('something went wrong!', msg)

bot.sendDocument(chat_id=10885151, file=dict(
    type='document',
    file='/home/lonami/holiday',
    # These are optional and will be inferred from file if unspecified
    name='My Favourite Photo.jpg',
    mime='image/jpeg'
))
```

# asyncio
no async http stdlib for python, `pip install aiohttp [cchardet aiodns]`.

# faq
* why is code duplicated? so you can just pull the file you need.
