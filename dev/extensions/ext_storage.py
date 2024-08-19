from collections.abc import Generator
from typing import Any, Union

from dev.extensions.storage.aliyun_storage import AliyunStorage
from dev.extensions.storage.local_storage import LocalStorage


class Storage:
    def __init__(self):
        self.storage_runner = None

    def init_app(self, config: dict[str, Any]):
        storage_type = config.get('STORAGE_TYPE')
        if storage_type == 'aliyun-oss':
            self.storage_runner = AliyunStorage(
                config=config
            )     
        else:
            self.storage_runner = LocalStorage(config=config)

    def save(self, filename, data):
        self.storage_runner.save(filename, data)

    def load(self, filename: str, stream: bool = False) -> Union[bytes, Generator]:
        if stream:
            return self.load_stream(filename)
        else:
            return self.load_once(filename)

    def load_once(self, filename: str) -> bytes:
        return self.storage_runner.load_once(filename)

    def load_stream(self, filename: str) -> Generator:
        return self.storage_runner.load_stream(filename)

    def download(self, filename, target_filepath):
        self.storage_runner.download(filename, target_filepath)

    def exists(self, filename):
        return self.storage_runner.exists(filename)

    def delete(self, filename):
        return self.storage_runner.delete(filename)


storage = Storage()


def init_app(config: dict[str, Any]):
    storage.init_app(config)
