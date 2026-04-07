import os
import asyncio
from telethon import TelegramClient


API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")


async def main():
    if API_ID <= 0 or not API_HASH:
        print("Eksik env: API_ID ve API_HASH tanimli olmali.")
        return

    client = TelegramClient("session", API_ID, API_HASH)
    await client.start()

    print("\n--- GROUPS / CHANNELS ---")
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            username = (
                "@" + dialog.entity.username
                if getattr(dialog.entity, "username", None)
                else "(username yok)"
            )
            safe_name = (dialog.name or "").encode("cp1254", errors="replace").decode("cp1254")
            print(f"{dialog.id} | {username} | {safe_name}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
