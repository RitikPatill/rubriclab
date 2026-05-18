from __future__ import annotations
from pathlib import Path
from typing import Annotated, Literal, Union
import yaml
from pydantic import BaseModel, Field, model_validator

class ScaleRange(BaseModel):
    min: int
    max: int

    @model_validator(mode="after")
    def _min_lt_max(self):
        if self.min >= self.max:
            raise ValueError("scale min must be less than max")
        return self

class ScaleCriterion(BaseModel):
    id: str
    type: Literal["scale"]
    scale: ScaleRange
    description: str
    weight: float = 1.0

class BoolCriterion(BaseModel):
    id: str
    type: Literal["bool"]
    description: str
    weight: float = 1.0
    invert: bool = False

Criterion = Annotated[
    Union[ScaleCriterion, BoolCriterion],
    Field(discriminator="type"),
]

class Rubric(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"
    criteria: list[Criterion] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [c.id for c in self.criteria]
        dupes = [id_ for id_ in set(ids) if ids.count(id_) > 1]
        if dupes:
            raise ValueError("Duplicate criterion ids: " + str(dupes))
        return self

def load_rubric(path) -> Rubric:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Rubric.model_validate(data)
