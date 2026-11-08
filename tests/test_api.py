from datetime import datetime


def book(client, prof, patient, when="2026-03-03T10:00:00", duration=30):
    return client.post(
        "/appointments",
        json={"professional_id": prof["id"], "patient_id": patient["id"], "starts_at": when, "duration_min": duration},
    )


def test_cpf_invalido_e_duplicado(client, patient):
    r = client.post("/patients", json={"name": "Fulano", "cpf": "123.456.789-00"})
    assert r.status_code == 422

    r = client.post("/patients", json={"name": "Outro Marcos", "cpf": "52998224725"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "cpf_taken"


def test_cpf_sai_mascarado(client, patient):
    assert patient["cpf"] == "***.***.247-25"
    assert client.get("/patients").json()[0]["cpf"] == "***.***.247-25"


def test_profissional_valida_horario(client):
    r = client.post(
        "/professionals",
        json={"name": "Dr. Teste", "specialty": "Clínica", "work_start": "18:00:00", "work_end": "08:00:00"},
    )
    assert r.status_code == 422


def test_agenda_consulta(client, prof, patient):
    r = book(client, prof, patient)
    assert r.status_code == 201
    body = r.json()
    assert body["starts_at"] == "2026-03-03T10:00:00"
    assert body["ends_at"] == "2026-03-03T10:30:00"
    assert body["status"] == "scheduled"


def test_conflito_de_profissional(client, prof, patient):
    assert book(client, prof, patient).status_code == 201

    outro = client.post("/patients", json={"name": "Paula Reis", "cpf": "111.444.777-35"}).json()
    r = book(client, prof, outro, when="2026-03-03T10:15:00")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "professional_busy"

    # encostada no fim da outra pode
    assert book(client, prof, outro, when="2026-03-03T10:30:00").status_code == 201


def test_paciente_nao_pode_estar_em_dois_lugares(client, prof, patient):
    segunda = client.post("/professionals", json={"name": "Dr. Caio Mendes", "specialty": "Ortopedia"}).json()
    assert book(client, prof, patient).status_code == 201

    r = book(client, segunda, patient, when="2026-03-03T10:00:00")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "patient_busy"


def test_fora_do_expediente_e_passado(client, prof, patient):
    r = book(client, prof, patient, when="2026-03-03T07:30:00")
    assert r.json()["detail"]["code"] == "outside_working_hours"

    r = book(client, prof, patient, when="2026-03-07T10:00:00")  # sábado
    assert r.json()["detail"]["code"] == "outside_working_hours"

    r = book(client, prof, patient, when="2026-03-02T08:30:00")  # hoje, antes de "agora" (09:00)
    assert r.json()["detail"]["code"] == "in_the_past"


def test_cancelar_libera_o_horario(client, prof, patient):
    appt = book(client, prof, patient).json()
    assert client.patch(f"/appointments/{appt['id']}/cancel").json()["status"] == "canceled"
    assert client.patch(f"/appointments/{appt['id']}/cancel").status_code == 409

    assert book(client, prof, patient).status_code == 201


def test_remarcar(client, prof, patient):
    appt = book(client, prof, patient).json()

    # remarcar para um horário que sobrepõe o atual não conflita consigo mesma
    r = client.patch(f"/appointments/{appt['id']}/reschedule", json={"starts_at": "2026-03-03T10:15:00"})
    assert r.status_code == 200
    assert r.json()["starts_at"] == "2026-03-03T10:15:00"
    assert r.json()["ends_at"] == "2026-03-03T10:45:00"

    r = client.patch(f"/appointments/{appt['id']}/reschedule", json={"starts_at": "2026-03-03T20:00:00"})
    assert r.status_code == 422


def test_disponibilidade_reflete_agendamentos(client, prof, patient):
    book(client, prof, patient, when="2026-03-03T08:00:00", duration=60)

    r = client.get(f"/professionals/{prof['id']}/availability", params={"date": "2026-03-03", "duration": 30})
    assert r.status_code == 200
    slots = [datetime.fromisoformat(s) for s in r.json()["slots"]]
    assert slots[0] == datetime(2026, 3, 3, 9, 0)
    assert datetime(2026, 3, 3, 8, 30) not in slots
    assert slots[-1] == datetime(2026, 3, 3, 17, 30)


def test_disponibilidade_nao_lista_horas_passadas_de_hoje(client, prof):
    r = client.get(f"/professionals/{prof['id']}/availability", params={"date": "2026-03-02"})
    slots = [datetime.fromisoformat(s) for s in r.json()["slots"]]
    assert slots[0] > datetime(2026, 3, 2, 9, 0)


def test_recursos_inexistentes(client, prof, patient):
    assert client.get("/professionals/999/availability", params={"date": "2026-03-03"}).status_code == 404
    assert client.patch("/appointments/999/cancel").status_code == 404
    r = client.post(
        "/appointments",
        json={"professional_id": 999, "patient_id": patient["id"], "starts_at": "2026-03-03T10:00:00"},
    )
    assert r.status_code == 404


def test_lista_filtra_por_dia_e_profissional(client, prof, patient):
    book(client, prof, patient, when="2026-03-03T10:00:00")
    book(client, prof, patient, when="2026-03-04T10:00:00")
    r = client.get("/appointments", params={"professional_id": prof["id"], "date": "2026-03-04"})
    assert [a["starts_at"] for a in r.json()] == ["2026-03-04T10:00:00"]
