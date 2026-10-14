"""Small, deterministic clinic tool layer. No language model touches clinic state."""
from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "clinic.json"


class ToolError(ValueError):
    pass


def _time(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ToolError("start must be HH:MM in 24-hour time")
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ToolError("start must be a valid 24-hour time") from exc
    return parsed.hour * 60 + parsed.minute


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ToolError("date must be YYYY-MM-DD") from exc


class ClinicTools:
    def __init__(self, data=None):
        self.data = data if data is not None else json.loads(DATA.read_text())
        self.lock = threading.RLock()
        self.calls = []
        self.handoff = None

    def _record(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments.copy()})

    def _doctor(self, doctor_id):
        doctor = next((d for d in self.data["doctors"] if d["id"] == doctor_id), None)
        if doctor is None:
            raise ToolError(f"unknown doctor_id: {doctor_id}")
        return doctor

    def _patient(self, patient_id):
        patient = next((p for p in self.data["patients"] if p["id"] == patient_id), None)
        if patient is None:
            raise ToolError(f"unknown patient_id: {patient_id}")
        return patient

    def lookup_patient(self, query, phone=None):
        args = {"query": query, "phone": phone}
        self._record("lookup_patient", args)
        if not isinstance(query, str) or len(query.strip()) < 2:
            raise ToolError("query needs at least two characters")
        if phone is not None and (not isinstance(phone, str) or not re.fullmatch(r"\d{10}", phone)):
            raise ToolError("phone must have ten digits")
        words = query.casefold().split()
        candidates = [p.copy() for p in self.data["patients"] if all(w in p["name"].casefold() for w in words)]
        if phone:
            candidates = [p for p in candidates if p["phone"] == phone]
        return candidates

    def search_slots(self, doctor_id, date):
        args = {"doctor_id": doctor_id, "date": date}
        self._record("search_slots", args)
        return self._slots(doctor_id, date)

    def _slots(self, doctor_id, date):
        doctor = self._doctor(doctor_id)
        day = _date(date)
        if date in self.data["holidays"] or date in doctor["leave_dates"]:
            return []
        minute_step = self.data["clinic"]["slot_minutes"]
        slots = set()
        for window in doctor["windows"]:
            if window["day"] != day.strftime("%a"):
                continue
            start, end = _time(window["start"]), _time(window["end"])
            slots.update(range(start, end - minute_step + 1, minute_step))
        occupied = {a["start"] for a in self.data["appointments"] if a["doctor_id"] == doctor_id and a["date"] == date and a["status"] == "booked"}
        return [f"{minute // 60:02d}:{minute % 60:02d}" for minute in sorted(slots) if f"{minute // 60:02d}:{minute % 60:02d}" not in occupied]

    def _available(self, doctor_id, day, start):
        # A real write checks availability while holding the same lock.
        return start in self._slots(doctor_id, day)

    def book_appointment(self, patient_id, doctor_id, date, start):
        args = {"patient_id": patient_id, "doctor_id": doctor_id, "date": date, "start": start}
        self._record("book_appointment", args)
        with self.lock:
            self._patient(patient_id)
            minute = _time(start)
            if not self._available(doctor_id, date, start):
                raise ToolError("requested slot is unavailable; search another doctor/date/time")
            next_id = max(int(a["id"].split("_")[1]) for a in self.data["appointments"]) + 1
            end = minute + self.data["clinic"]["slot_minutes"]
            appt = {"id": f"ap_{next_id:04d}", "patient_id": patient_id, "doctor_id": doctor_id,
                    "date": date, "start": start, "end": f"{end // 60:02d}:{end % 60:02d}", "status": "booked"}
            self.data["appointments"].append(appt)
            return appt.copy()

    def _appointment(self, appointment_id):
        appt = next((a for a in self.data["appointments"] if a["id"] == appointment_id), None)
        if appt is None:
            raise ToolError(f"unknown appointment_id: {appointment_id}")
        if appt["status"] != "booked":
            raise ToolError(f"appointment {appointment_id} is not active")
        return appt

    def reschedule_appointment(self, appointment_id, patient_id, date, start):
        args = {"appointment_id": appointment_id, "patient_id": patient_id, "date": date, "start": start}
        self._record("reschedule_appointment", args)
        with self.lock:
            appt = self._appointment(appointment_id)
            if appt["patient_id"] != patient_id:
                raise ToolError("appointment does not belong to patient_id")
            minute = _time(start)
            if not self._available(appt["doctor_id"], date, start):
                raise ToolError("requested slot is unavailable; search another date/time")
            end = minute + self.data["clinic"]["slot_minutes"]
            appt.update(date=date, start=start, end=f"{end // 60:02d}:{end % 60:02d}")
            return appt.copy()

    def cancel_appointment(self, appointment_id, patient_id):
        args = {"appointment_id": appointment_id, "patient_id": patient_id}
        self._record("cancel_appointment", args)
        with self.lock:
            appt = self._appointment(appointment_id)
            if appt["patient_id"] != patient_id:
                raise ToolError("appointment does not belong to patient_id")
            appt["status"] = "cancelled"
            return appt.copy()

    def escalate_to_human(self, reason, detail):
        args = {"reason": reason, "detail": detail}
        self._record("escalate_to_human", args)
        allowed = {"clinical_urgent", "medical_advice", "not_authorised", "ambiguous_patient", "out_of_scope"}
        if reason not in allowed:
            raise ToolError(f"reason must be one of {', '.join(sorted(allowed))}")
        if not isinstance(detail, str) or not detail.strip():
            raise ToolError("detail is required for a handoff")
        self.handoff = args
        return args.copy()
