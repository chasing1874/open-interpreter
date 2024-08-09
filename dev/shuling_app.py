from typing import Any
from fastapi import FastAPI


class ShulingApp(FastAPI):
    config: dict[str, Any]