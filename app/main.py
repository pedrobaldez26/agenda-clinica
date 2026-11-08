from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, schemas
from .database import SessionLocal, engine, get_db
from .scheduling import fits_working_hours, free_slots, overlaps

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def get_now() -> datetime:
    """Horário local da clínica. Existe como dependência para os testes poderem fixar o relógio."""
    return datetime.now()


@asynccontextmanager
async def lifespan(_: FastAPI):
    models.Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Agenda Clínica", version="0.1.0", lifespan=lifespan)


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise fail(404, "not_found", f"{label} não encontrado(a)")
    return obj


def ensure_bookable(
    db: Session,
    prof: models.Professional,
    patient_id: int,
    start: datetime,
    end: datetime,
    now: datetime,
    ignore_id: Optional[int] = None,
) -> None:
    if start <= now:
        raise fail(422, "in_the_past", "Não dá para agendar no passado")

    if not fits_working_hours(start, end, prof.work_start, prof.work_end, prof.work_days_list):
        raise fail(422, "outside_working_hours", "Fora do horário de atendimento do profissional")

    def conflicts(column, value) -> bool:
        stmt = select(models.Appointment).where(
            column == value,
            models.Appointment.status == "scheduled",
            models.Appointment.starts_at < end,
            models.Appointment.ends_at > start,
        )
        if ignore_id is not None:
            stmt = stmt.where(models.Appointment.id != ignore_id)
        return any(
            overlaps(start, end, a.starts_at, a.ends_at) for a in db.scalars(stmt).all()
        )

    if conflicts(models.Appointment.professional_id, prof.id):
        raise fail(409, "professional_busy", "O profissional já tem consulta nesse horário")
    if conflicts(models.Appointment.patient_id, patient_id):
        raise fail(409, "patient_busy", "O paciente já tem outra consulta nesse horário")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/professionals", response_model=schemas.ProfessionalOut, response_model_by_alias=True, status_code=201)
def create_professional(data: schemas.ProfessionalIn, db: Session = Depends(get_db)):
    prof = models.Professional(
        name=data.name,
        specialty=data.specialty,
        work_start=data.work_start,
        work_end=data.work_end,
        work_days=",".join(str(d) for d in data.work_days),
    )
    db.add(prof)
    db.commit()
    return prof


@app.get("/professionals", response_model=List[schemas.ProfessionalOut], response_model_by_alias=True)
def list_professionals(db: Session = Depends(get_db)):
    return db.scalars(select(models.Professional).order_by(models.Professional.name)).all()


@app.post("/patients", response_model=schemas.PatientOut, status_code=201)
def create_patient(data: schemas.PatientIn, db: Session = Depends(get_db)):
    patient = models.Patient(name=data.name, cpf=data.cpf, phone=data.phone)
    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise fail(409, "cpf_taken", "Já existe paciente com esse CPF")
    return patient


@app.get("/patients", response_model=List[schemas.PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return db.scalars(select(models.Patient).order_by(models.Patient.name)).all()


@app.get("/professionals/{prof_id}/availability", response_model=schemas.AvailabilityOut)
def availability(
    prof_id: int,
    day: date = Query(alias="date"),
    duration: int = Query(default=30, ge=15, le=180, multiple_of=5),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    prof = get_or_404(db, models.Professional, prof_id, "Profissional")

    start_of_day = datetime.combine(day, datetime.min.time())
    booked = db.scalars(
        select(models.Appointment).where(
            models.Appointment.professional_id == prof_id,
            models.Appointment.status == "scheduled",
            models.Appointment.starts_at >= start_of_day,
            models.Appointment.starts_at < start_of_day + timedelta(days=1),
        )
    ).all()

    slots = free_slots(
        day,
        timedelta(minutes=duration),
        prof.work_start,
        prof.work_end,
        prof.work_days_list,
        [(a.starts_at, a.ends_at) for a in booked],
        now=now,
    )
    return schemas.AvailabilityOut(professional_id=prof_id, date=day, duration_min=duration, slots=slots)


@app.post("/appointments", response_model=schemas.AppointmentOut, status_code=201)
def create_appointment(
    data: schemas.AppointmentIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    prof = get_or_404(db, models.Professional, data.professional_id, "Profissional")
    get_or_404(db, models.Patient, data.patient_id, "Paciente")

    start = data.starts_at.replace(tzinfo=None)
    end = start + timedelta(minutes=data.duration_min)
    ensure_bookable(db, prof, data.patient_id, start, end, now)

    appt = models.Appointment(
        professional_id=prof.id,
        patient_id=data.patient_id,
        starts_at=start,
        ends_at=end,
        notes=data.notes,
    )
    db.add(appt)
    db.commit()
    return appt


@app.get("/appointments", response_model=List[schemas.AppointmentOut])
def list_appointments(
    professional_id: Optional[int] = None,
    day: Optional[date] = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    stmt = select(models.Appointment).order_by(models.Appointment.starts_at)
    if professional_id is not None:
        stmt = stmt.where(models.Appointment.professional_id == professional_id)
    if day is not None:
        start_of_day = datetime.combine(day, datetime.min.time())
        stmt = stmt.where(
            models.Appointment.starts_at >= start_of_day,
            models.Appointment.starts_at < start_of_day + timedelta(days=1),
        )
    return db.scalars(stmt).all()


@app.patch("/appointments/{appt_id}/cancel", response_model=schemas.AppointmentOut)
def cancel_appointment(appt_id: int, db: Session = Depends(get_db)):
    appt = get_or_404(db, models.Appointment, appt_id, "Consulta")
    if appt.status == "canceled":
        raise fail(409, "already_canceled", "Essa consulta já foi cancelada")
    appt.status = "canceled"
    db.commit()
    return appt


@app.patch("/appointments/{appt_id}/reschedule", response_model=schemas.AppointmentOut)
def reschedule_appointment(
    appt_id: int,
    data: schemas.RescheduleIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    appt = get_or_404(db, models.Appointment, appt_id, "Consulta")
    if appt.status != "scheduled":
        raise fail(409, "not_active", "Só dá para remarcar consulta agendada")

    prof = get_or_404(db, models.Professional, appt.professional_id, "Profissional")
    duration = data.duration_min or int((appt.ends_at - appt.starts_at).total_seconds() // 60)
    start = data.starts_at.replace(tzinfo=None)
    end = start + timedelta(minutes=duration)

    # a própria consulta não pode contar como conflito consigo mesma
    ensure_bookable(db, prof, appt.patient_id, start, end, now, ignore_id=appt.id)

    appt.starts_at, appt.ends_at = start, end
    db.commit()
    return appt


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
