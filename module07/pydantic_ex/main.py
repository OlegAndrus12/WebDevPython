from pydantic import BaseModel, field_validator, ValidationError, IPvAnyAddress, ConfigDict
from datetime import date

from pydantic.alias_generators import to_camel, to_snake, to_pascal
from pydantic.aliases import AliasGenerator

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    model_config = ConfigDict(strict=False)

    x: bool
    y: float


p1 = Coordinates(x="fasd", y=2.2)
print(p1)