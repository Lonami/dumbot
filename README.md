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
```
