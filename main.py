import yaml
import json
import asyncio
import requests
import subprocess

from loguru import logger
from argparse import Namespace
from dataclasses import dataclass, asdict

from telethon.tl import functions
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
from telethon.tl.functions.channels import GetFullChannelRequest


def get_settings():
    try:
        with open("settings.json", "r") as f:
            return json.loads(f.read())
    except:
        return {}

def set_settings(data):
    with open("settings.json", "w") as f:
        f.write(json.dumps(data))


settings = get_settings()


def register_user():
    print("Связываемся с сервером...")
    current_machine_id = (
        str(subprocess.check_output("wmic csproduct get uuid"), "utf-8")
        .split("\n")[1]
        .strip()
    )

    admin_username = settings.get("ADMIN_USERNAME")
    script_name = settings.get("SCRIPTNAME")
    BASE_API_URL = settings.get("BASE_API_URL", "http://142.93.105.98:8000")

    db_id = requests.get(
        f"{BASE_API_URL}/api/{script_name}/{current_machine_id}/{admin_username}"
    )
    db_id = db_id.json()
    if db_id.get("message"):
        print("Неправильный логин")
        sys.exit()
    file_key = settings.get("ACCESS_KEY")
    print(f"Ваш ID в системе: {db_id['id']}")
    if file_key:
        key = file_key
    else:
        key = input("Введите ваш ключ доступа: ")
    while True:
        is_correct = requests.post(
            f"{BASE_API_URL}/api/{script_name}/check/",
            data={"pk": current_machine_id, "key": key},
        ).json()["message"]
        if is_correct:
            print("Вход успешно выполнен!")
            settings["ACCESS_KEY"] = key
            set_settings(settings)
            return
        else:
            print("Неправильный ключ!")
            key = input("Введите ваш ключ доступа: ")


# register_user()


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as file:
        return Namespace(**yaml.load(file, Loader=yaml.SafeLoader))


@dataclass
class Channel:
    username: str
    members: int


def create_channel(username, *args, **kwargs):
    logger.info(f"Channel: {username}. FOUND!")
    return Channel(username, *args, **kwargs)


async def search_channels_globally(
    client: TelegramClient,
    search: str,
    min_participants_count: int = 0,
    is_comments: bool = True,
):
    result = await client(functions.contacts.SearchRequest(q=search, limit=100))

    channels = []

    for peer in result.results:
        if type(peer) != PeerChannel:
            continue

        entity = await client.get_entity(peer.channel_id)

        if entity.megagroup is True:
            continue

        channel_full_info = await client(GetFullChannelRequest(peer.channel_id))

        if min_participants_count > channel_full_info.full_chat.participants_count:
            logger.error(
                f"Channel: {entity.username!r}. "
                f"Participants count: "
                f"{channel_full_info.full_chat.participants_count}"
                f" < {min_participants_count}"
            )
            continue

        if not is_comments:
            channels.append(
                create_channel(
                    entity.username, channel_full_info.full_chat.participants_count
                )
            )
            continue

        async for message in client.iter_messages(peer.channel_id, limit=10):
            if message.replies:
                channels.append(
                    create_channel(
                        entity.username, channel_full_info.full_chat.participants_count
                    )
                )
                break
        else:
            logger.error(f"Channel: {entity.username!r}. " f"Comments are closed.")
    return channels


def dump_to_yaml(channels):
    dict_channels = [asdict(channel) for channel in channels]
    dict_channels = sorted(
        dict_channels, key=lambda channel: channel["members"], reverse=True
    )
    with open("result.yaml", "w") as file:
        yaml.dump(dict_channels, file)


async def main():
    config = load_config()

    async with TelegramClient(
        config.session, api_id=config.api_id, api_hash=config.api_hash
    ) as client:
        channels = []
        for name in config.names:
            for ending in config.endings:
                search = f"{name}{ending}"
                logger.info(f"Search by {search!r}.")
                found_channels = await search_channels_globally(
                    client,
                    search,
                    min_participants_count=config.min_participants_count,
                    is_comments=True,
                )
                channels.extend(found_channels)
        dump_to_yaml(channels)


if __name__ == "__main__":
    asyncio.run(main())

