from dataclasses import dataclass, field
from typing import Literal
import math
from pydantic import BaseModel, Field, model_validator
from shapely.geometry import Polygon


class Settings(BaseModel):
    width: float = Field(default=600, ge=20, le=3000)
    height: float = Field(default=400, ge=20, le=3000)
    thickness: float = Field(default=3, ge=0.1, le=50)
    kerf: float = Field(default=0.15, ge=0, le=3)
    gap: float = Field(default=3, ge=0.1, le=50)
    margin: float = Field(default=5, ge=0, le=100)
    units: Literal['mm', 'cm', 'm', 'in'] = 'mm'
    rotate: bool = True

    @model_validator(mode='after')
    def validate_sheet(self):
        if not all(math.isfinite(v) for v in [self.width, self.height, self.thickness, self.kerf, self.gap, self.margin]):
            raise ValueError('Los parámetros deben ser números finitos.')
        if self.margin * 2 >= min(self.width, self.height):
            raise ValueError('El margen consume toda la lámina.')
        return self

    @property
    def unit_factor(self):
        return {'mm': 1, 'cm': 10, 'm': 1000, 'in': 25.4}[self.units]


@dataclass
class Piece:
    id: str
    polygon: Polygon
    nominal_area: float


@dataclass
class Placement:
    piece: Piece
    polygon: Polygon
    angle: int


@dataclass
class Job:
    id: str
    filename: str
    settings: Settings
    sheets: list[list[Placement]]
    preview: dict
    warnings: list[str] = field(default_factory=list)
