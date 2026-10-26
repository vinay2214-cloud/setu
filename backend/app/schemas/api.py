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


class SimSessionRequest(BaseModel):
    patient_id: str


class SimMessageRequest(BaseModel):
    patient_id: str
    client_msg_id: str = Field(min_length=1, max_length=100)
    text: str | None = Field(default=None, max_length=1000)
    language: Literal["te", "hi", "en"] | None = None
    quick_reply: Literal["yes_taken", "not_taken", "no_symptoms", "have_symptom", "skip"] | None = (
        None
    )


class TimeTravelRequest(BaseModel):
    days: int = Field(default=0, ge=0, le=30)
    hours: int = Field(default=0, ge=0, le=23)
