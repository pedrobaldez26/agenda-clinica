from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Time, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Professional(Base):
    __tablename__ = "professionals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str] = mapped_column(String(80))
    work_start: Mapped[time] = mapped_column(Time)
    work_end: Mapped[time] = mapped_column(Time)
    # dias da semana em que atende, 0 = segunda ... 6 = domingo ("0,1,2,3,4")
    work_days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4")

    @property
    def work_days_list(self) -> list[int]:
        return [int(d) for d in self.work_days.split(",") if d != ""]


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    cpf: Mapped[str] = mapped_column(String(11), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appt_prof_start", "professional_id", "starts_at"),
        Index("ix_appt_patient_start", "patient_id", "starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("professionals.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="scheduled")  # scheduled | canceled
    notes: Mapped[Optional[str]] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
