"""Small API-layer helpers."""

from typing import Any

from fastapi import APIRouter


class CamelAPIRouter(APIRouter):
    """APIRouter that defaults `response_model_by_alias=True`.

    Pair with schemas extending `CamelModel` (alias_generator=to_camel) so
    every response auto-serializes snake_case fields as camelCase JSON,
    without sprinkling `response_model_by_alias=True` on every route.
    """

    def add_api_route(self, path: str, endpoint: Any, **kwargs: Any) -> None:
        kwargs.setdefault("response_model_by_alias", True)
        return super().add_api_route(path, endpoint, **kwargs)
