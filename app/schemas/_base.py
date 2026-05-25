"""Shared base for every Pydantic schema.

Why this exists:
The API speaks camelCase to the React frontend (`appliedAt`, `userId`, …) but
Python uses snake_case (`applied_at`, `user_id`). `alias_generator=to_camel`
maps fields automatically so we never write the camelCase form by hand.

`populate_by_name=True` keeps the snake_case names usable internally
(e.g. `JobCreate(title=..., applied_at=...)`).

Pair this with `CamelAPIRouter` (which defaults `response_model_by_alias=True`)
so FastAPI serializes responses with the camelCase aliases.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,        # build from ORM objects (.id not ['id'])
        populate_by_name=True,       # accept either snake_case or camelCase on input
        alias_generator=to_camel,    # field 'applied_at' ⇄ JSON 'appliedAt'
    )
