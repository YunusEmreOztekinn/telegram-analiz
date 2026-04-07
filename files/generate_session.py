import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession


API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")


async def main():
    if API_ID <= 0 or not API_HASH:
        print("Eksik env: API_ID ve API_HASH tanimli olmali.")
        return

    client = TelegramClient("session", API_ID, API_HASH)
    await client.start()

    if not await client.is_user_authorized():
        print("Hata: Oturum yetkili degil. Once localde main.py ile giris yap.")
        await client.disconnect()
        return

    session_string = StringSession.save(client.session)
    print("\nTELEGRAM_SESSION (Railway Variables icin):\n")
    print(session_string)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
