from pathlib import Path
from typing import Generator

from jsoner import json_read_sync

class BaseSession:
    def __init__(self):
        self.base_dir = Path("сессии")
        self.errors_dir = self.base_dir / "ошибки"
        self.banned_dir = self.base_dir / "забаненные"

    def find_sessions(self) -> Generator:
        parent_dir = self.base_dir.parent
        for item in parent_dir.glob("*.session"):
            json_file = item.with_suffix(".json")
            if not json_file.is_file():
                print(f"{item.name} | Не найден json файл!")
                continue
            if not (json_data := json_read_sync(json_file)):
                print(f"{item.name} | Ошибка чтения json")
                continue
            yield item, json_file, json_data

