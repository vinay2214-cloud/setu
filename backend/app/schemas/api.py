from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class NoteRequest(BaseModel):
    note: str = ""


class SnoozeRequest(BaseModel):
    minutes: int = Field(gt=0, le=10080)
    note: str = ""


class ApproveCallRequest(BaseModel):
    assignee: str = "dr.anitha"
    note: str = ""


class PatientCreate(BaseModel):
    name: str
    age: int = Field(ge=18, le=120)
    sex: Literal["M", "F", "O"]
    language: Literal["te", "hi", "en"]
    phone: str | None = None
    location: str | None = None
    conditions: list[str]
    discharge_date: str
    consent: dict


class DemoSeedRequest(BaseModel):
    scenario: str = "default"


class EvaluateRequest(BaseModel):
    facts: dict
