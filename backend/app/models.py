from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RawJob(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    city: str = Field(min_length=1)
    url: str = Field(min_length=1)
    description: str = ""
    source: str = Field(min_length=1)
    salary_raw: str | None = None


class SalaryDetails(BaseModel):
    minimum: float | None = None
    maximum: float | None = None
    currency: Literal["PLN"] = "PLN"
    period: Literal["hour", "month"]
    display_label: str


class CleanJob(BaseModel):
    hash: str
    title: str
    company: str
    city: str
    url: str
    description: str
    summary: str
    source: str
    industries: list[str]
    tags: list[str]
    salary: SalaryDetails | None = None
