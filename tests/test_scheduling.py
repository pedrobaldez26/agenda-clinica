from datetime import date, datetime, time, timedelta

from app.scheduling import fits_working_hours, free_slots, overlaps

SEG = date(2026, 3, 2)  # segunda
DOM = date(2026, 3, 8)
DIAS_UTEIS = [0, 1, 2, 3, 4]


def dt(h, m=0, day=SEG):
    return datetime.combine(day, time(h, m))


def test_consultas_encostadas_nao_conflitam():
    assert not overlaps(dt(9), dt(10), dt(10), dt(11))
    assert not overlaps(dt(10), dt(11), dt(9), dt(10))


def test_sobreposicao_parcial_e_total():
    assert overlaps(dt(9), dt(10), dt(9, 30), dt(10, 30))
    assert overlaps(dt(9), dt(12), dt(10), dt(11))
    assert overlaps(dt(10), dt(11), dt(9), dt(12))


def test_horario_de_trabalho():
    assert fits_working_hours(dt(8), dt(8, 30), time(8), time(18), DIAS_UTEIS)
    assert fits_working_hours(dt(17, 30), dt(18), time(8), time(18), DIAS_UTEIS)
    assert not fits_working_hours(dt(7, 45), dt(8, 15), time(8), time(18), DIAS_UTEIS)
    assert not fits_working_hours(dt(17, 45), dt(18, 15), time(8), time(18), DIAS_UTEIS)
    assert not fits_working_hours(dt(9, day=DOM), dt(9, 30, day=DOM), time(8), time(18), DIAS_UTEIS)


def test_nao_aceita_consulta_que_vira_a_noite():
    assert not fits_working_hours(dt(23, 45), dt(0, 15, day=SEG + timedelta(days=1)), time(0), time(23, 59), range(7))


def test_slots_do_dia_inteiro():
    slots = free_slots(SEG, timedelta(minutes=30), time(8), time(10), DIAS_UTEIS, [])
    assert [s.strftime("%H:%M") for s in slots] == ["08:00", "08:15", "08:30", "08:45", "09:00", "09:15", "09:30"]


def test_slots_pulam_horario_ocupado():
    busy = [(dt(9), dt(9, 30))]
    slots = free_slots(SEG, timedelta(minutes=30), time(8), time(10), DIAS_UTEIS, busy)
    horas = [s.strftime("%H:%M") for s in slots]
    assert "08:45" not in horas  # 08:45-09:15 bate com a consulta das 09:00
    assert "09:00" not in horas and "09:15" not in horas
    assert "08:30" in horas and "09:30" in horas


def test_slots_ignoram_passado_e_dia_sem_expediente():
    agora = dt(8, 50)
    slots = free_slots(SEG, timedelta(minutes=30), time(8), time(10), DIAS_UTEIS, [], now=agora)
    assert slots[0] == dt(9)
    assert free_slots(DOM, timedelta(minutes=30), time(8), time(10), DIAS_UTEIS, []) == []
