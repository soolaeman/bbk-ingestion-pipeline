from telethon.sync import TelegramClient
from config_telethon import API_ID, API_HASH, SESSION_NAME

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

client.start()

dialogs = client.get_dialogs()

for d in dialogs:
    print(f"{d.name} => {d.id}")