from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .cpf import is_valid_cpf, mask_cpf, only_digits


class ProfessionalIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    specialty: str = Field(min_length=2, max_length=80)
    work_start: time = time(8, 0)
    work_end: time = time(18, 0)
    work_days: List[int] = [0, 1, 2, 3, 4]

    @field_validator("work_days")
    @classmethod
    def valid_days(cls, days: List[int]) -> List[int]:
        if not days or any(d < 0 or d > 6 for d in days):
            raise ValueError("work_days deve ter valores de 0 (segunda) a 6 (domingo)")
        return sorted(set(days))

    @model_validator(mode="after")
    def end_after_start(self):
        if self.work_end <= self.work_start:
            raise ValueError("work_end deve ser depois de work_start")
        return self


class ProfessionalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialty: str
    work_start: time
    work_end: time
    work_days_list: List[int] = Field(serialization_alias="work_days")


class PatientIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    cpf: str
    phone: Optional[str] = Field(default=None, max_length=20)

    @field_validator("cpf")
    @classmethod
    def valid_cpf(cls, value: str) -> str:
        if not is_valid_cpf(value):
            raise ValueError("CPF inválido")
        return only_digits(value)


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: Optional[str]
    cpf: str

    @field_validator("cpf")
    @classmethod
    def masked(cls, value: str) -> str:
        return mask_cpf(value)


class AppointmentIn(BaseModel):
    professional_id: int
    patient_id: int
    starts_at: datetime
    duration_min: int = Field(default=30, ge=15, le=180, multiple_of=5)
    notes: Optional[str] = Field(default=None, max_length=300)


class RescheduleIn(BaseModel):
    starts_at: datetime
    duration_min: Optional[int] = Field(default=None, ge=15, le=180, multiple_of=5)


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    professional_id: int
    patient_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    notes: Optional[str]


class AvailabilityOut(BaseModel):
    professional_id: int
    date: date
    duration_min: int
    slots: List[datetime]
