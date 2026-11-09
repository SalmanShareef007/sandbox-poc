
import json
import time
from pathlib import Path
from threading import RLock
from typing import Any


DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"

_file_lock = RLock()


class JSONStorageService:

    @staticmethod
    def lock() -> RLock:
        """Hold this around read-modify-write sequences so they stay atomic."""
        return _file_lock

    @staticmethod
    def _get_file_path(filename: str) -> Path:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise ValueError("Invalid JSON storage filename.")

        return DATA_DIRECTORY / filename

    @classmethod
    def read(cls, filename: str) -> list[dict[str, Any]]:
        file_path = cls._get_file_path(filename)

        with _file_lock:
            if not file_path.exists():
                return []

            with file_path.open("r", encoding="utf-8-sig") as file:
                content = file.read().strip()

            return json.loads(content) if content else []

    @classmethod
    def write(
        cls,
        filename: str,
        data: list[dict[str, Any]],
    ) -> None:
        file_path = cls._get_file_path(filename)

        DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

        with _file_lock:
            temporary_path = file_path.with_suffix(".tmp")

            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)

            # OneDrive or antivirus can briefly lock the target file on Windows.
            for attempt in range(10):
                try:
                    temporary_path.replace(file_path)
                    return
                except PermissionError:
                    if attempt == 9:
                        raise
                    time.sleep(0.2)