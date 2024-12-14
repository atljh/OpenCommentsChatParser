import asyncio
from pathlib import Path

from jsoner import json_write_sync
from telethon import TelegramClient
from telethon.sessions import StringSession

from basethon.base_session import BaseSession

class JsonConverter(BaseSession):
    def __init__(self):
        super().__init__()
        self.__api_id, self.__api_hash = 2040, "b18441a1ff607e10a989891a5462e627"

    def _main(self, item: Path, json_file: Path, json_data: dict):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = TelegramClient(str(item), self.__api_id, self.__api_hash)
        ss = StringSession()
        ss._server_address = client.session.server_address  # type: ignore
        ss._takeout_id = client.session.takeout_id  # type: ignore
        ss._auth_key = client.session.auth_key  # type: ignore
        ss._dc_id = client.session.dc_id  # type: ignore
        ss._port = client.session.port  # type: ignore
        string_session = ss.save()
        del ss, client
        # json_data["proxy"] = self.__proxy
        json_data["string_session"] = string_session
        json_write_sync(json_file, json_data)

    def main(self) -> int:
        count = 0
        for item, json_file, json_data in self.find_sessions():
            self._main(item, json_file, json_data)
            count += 1
        return count
