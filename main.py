import re
import yaml
import json
import asyncio
import requests
import subprocess

from typing import List
from pathlib import Path
from argparse import Namespace
from dataclasses import dataclass, asdict

from telethon.tl import functions
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
from telethon.tl.functions.channels import GetFullChannelRequest

from console import console
from basethon.base_thon import BaseThon
from basethon.base_session import BaseSession
from basethon.json_converter import JsonConverter

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


@dataclass
class Channel:
    username: str
    members: int

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as file:
        return Namespace(**yaml.load(file, Loader=yaml.SafeLoader))

class TelegramSearch(BaseThon):
    def __init__(self, item: str, json_data: dict, config: Namespace):
        if not item:
            raise ValueError("Переданный параметр 'item' пустой или None.")
        if not isinstance(json_data, dict):
            raise ValueError("Переданный параметр 'json_data' должен быть словарем.")
        super().__init__(item, json_data)

        self.output_file = Path("result.yaml")
        self.config = config

    def create_channel(self, username, *args, **kwargs):
        console.log(f"Channel: {username}. FOUND!", style="green")
        return Channel(username, *args, **kwargs)

    def dump_to_yaml(self, channels):
        dict_channels = [asdict(channel) for channel in channels]
        dict_channels = sorted(
            dict_channels, key=lambda channel: channel["members"], reverse=True
        )
        with open("result.yaml", "w") as file:
            yaml.dump(dict_channels, file)

    def detect_language(self, text: str) -> str:
        try:
            if re.search(r'[а-яА-Я]', text):
                return 'sng'
            elif re.search(r'[a-zA-Z]', text):
                return 'other'
        except Exception:
            pass
        return 'unknown'

    async def main(self, config):
        r = await self.check()
        if "OK" not in r:
            console.log("Аккаунт разлогинен или забанен", style="red")
            return
        await self.start_search(config)

    async def start_search(self, config):
        channels = []
        for name in config.names:
            for ending in config.endings:
                search = f"{name}{ending}"
                console.log(f"Search by {search!r}.")
                found_channels = await self.search_channels_globally(
                    search,
                    min_participants_count=config.min_participants_count,
                    is_comments=True,
                )
                channels.extend(found_channels)
        self.dump_to_yaml(channels)

    async def search_channels_globally(
        self,
        search: str,
        min_participants_count: int = 0,
        is_comments: bool = True,
    ) -> List[Channel]:
        
        try:
            result = await self.client(functions.contacts.SearchRequest(q=search, limit=100))
        except Exception as e:
            console.log(f"Ошибка поиска по запросу {search!r}: {e}", style="red")
            return []
        channels = []

        for peer in result.results:
            if type(peer) != PeerChannel:
                continue

            entity = await self.client.get_entity(peer.channel_id)

            if entity.megagroup is True:
                continue

            channel_full_info = await self.client(GetFullChannelRequest(peer.channel_id))

            if min_participants_count > channel_full_info.full_chat.participants_count:
                console.log(
                    f"Channel: {entity.username!r}. "
                    f"Participants count: "
                    f"{channel_full_info.full_chat.participants_count}"
                    f" < {min_participants_count}"
                )
                continue

            last_post_text = None
            async for message in self.client.iter_messages(peer.channel_id, limit=2):
                if message.text:
                    last_post_text = message.text

            if last_post_text:
                detected_language = self.detect_language(last_post_text)
                language_filter = self.config.language_filter

                if language_filter == "sng" and detected_language != "sng":
                    continue
                elif language_filter == "other" and detected_language != "other":
                    continue
                
            if not is_comments:
                if entity.username is None:
                    continue
                channels.append(
                    self.create_channel(
                        entity.username, channel_full_info.full_chat.participants_count
                    )
                )
                continue

            async for message in self.client.iter_messages(peer.channel_id, limit=10):
                if message.replies:
                    if entity.username is None:
                        break
                    channels.append(
                        self.create_channel(
                            entity.username, channel_full_info.full_chat.participants_count
                        )
                    )
                    break
            else:
                if entity.username is None:
                    continue
                console.log(f"Channel: {entity.username!r}. " f"Comments are closed.")
        return channels


async def main():
    config = load_config()
    session_file = f'{config.session}.session'
    json_file = f'{config.session}.json'

    basethon_session = Path(session_file)
    if not basethon_session.exists():
        console.log(f"Файл {config.session}.session не найден.", style='yellow')
        return
    sessions_count = JsonConverter().main()
    if not sessions_count:
        console.log("Нет аккаунтов в папке с сессиями!", style="yellow")
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except FileNotFoundError:
        console.log(f"Файл {json_file} не найден!", style="red")
        json_data = {}
    except json.JSONDecodeError:
        console.log(f"Ошибка чтения {json_file}! Убедитесь, что файл содержит корректный JSON.", style="red")
        json_data = {}

    try:
        telegram_search = TelegramSearch(session_file, json_data, config)
        await telegram_search.main(config)
    except Exception as e:
        console.log(f"Ошибка запуска: {e}", style="red")




if __name__ == "__main__":
    asyncio.run(main())

