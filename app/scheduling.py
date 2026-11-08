"""Regras de agenda sem dependência de banco, para testar sem montar nada."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

SLOT_STEP = timedelta(minutes=15)

Interval = Tuple[datetime, datetime]


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    # intervalos semiabertos: uma consulta que termina às 10:00 não conflita com a das 10:00
    return a_start < b_end and b_start < a_end


def fits_working_hours(
    start: datetime, end: datetime, work_start: time, work_end: time, work_days: Iterable[int]
) -> bool:
    if start.date() != end.date():
        return False
    if start.weekday() not in set(work_days):
        return False
    return work_start <= start.time() and end.time() <= work_end


def free_slots(
    day: date,
    duration: timedelta,
    work_start: time,
    work_end: time,
    work_days: Iterable[int],
    busy: Sequence[Interval],
    now: Optional[datetime] = None,
) -> List[datetime]:
    if day.weekday() not in set(work_days):
        return []

    slots: List[datetime] = []
    cursor = datetime.combine(day, work_start)
    close = datetime.combine(day, work_end)

    while cursor + duration <= close:
        end = cursor + duration
        in_future = now is None or cursor > now
        if in_future and not any(overlaps(cursor, end, b_start, b_end) for b_start, b_end in busy):
            slots.append(cursor)
        cursor += SLOT_STEP

    return slots
