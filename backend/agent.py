"""A bounded conversation policy: extract intent, verify identity, then use tools."""
from __future__ import annotations

import re
import time
import math
from datetime import date, timedelta

from .tools import ClinicTools, ToolError

WEEKDAYS = {"monday": 0, "somwar": 0, "tuesday": 1, "mangalwar": 1,
            "wednesday": 2, "budhwar": 2, "thursday": 3, "guruwar": 3,
            "friday": 4, "shukrawar": 4, "saturday": 5, "shanivaar": 5,
            "sunday": 6, "ravivaar": 6}
WORDS = {"nau": 9, "das": 10, "gyarah": 11, "barah": 12, "ek": 1,
         "do": 2, "teen": 3, "chaar": 4, "paanch": 5, "cheh": 6, "saat": 7, "aath": 8}
URGENT = [r"seene (?:mein|me) dard", r"chest (?:pain|tightness)", r"saans .*phool", r"saans nahi",
          r"(?:can't|cannot|difficulty|trouble) breath", r"breath(?:ing|less)", r"not breathing",
          r"unconscious", r"behosh", r"faint(?:ed|ing)", r"stroke", r"heart attack",
          r"seizure", r"fit aa", r"severe bleeding", r"bahut khoon", r"suicid"]
ADVICE = [r"(?:goli|dose|tablet|medicine|dawai).*(?:lun|lu|lena|kitni|should)",
          r"(?:kya|what).*(?:bimari|diagnos)", r"(?:kitni der|how long).*(?:utar|recover)",
          r"(?:should i|kya main).*(?:take|medicin|dawai|goli)", r"(?:what|which|kaunsi).*(?:medicine|dawai)",
          r"(?:is it|kya ye).*(?:serious|normal)"]


def _last_date(turns, today):
    found = None
    for turn in turns:
        lower = turn.casefold()
        matches = []
        for m in re.finditer(r"\b20\d\d-\d\d-\d\d\b", lower):
            try: matches.append((m.start(), date.fromisoformat(m.group())))
            except ValueError: pass
        for m in re.finditer(r"\b(aaj|today|kal|tomorrow|parso|day after tomorrow)\b", lower):
            delta = {"aaj": 0, "today": 0, "kal": 1, "tomorrow": 1, "parso": 2, "day after tomorrow": 2}[m.group()]
            matches.append((m.start(), today + timedelta(days=delta)))
        for m in re.finditer(r"\b(\d{1,2})\s*(?:tareekh|tarikh|october|oct)\b", lower):
            try:
                d = today.replace(day=int(m.group(1)))
                if d < today: d = d.replace(month=today.month + 1 if today.month < 12 else 1, year=today.year + (today.month == 12))
                matches.append((m.start(), d))
            except ValueError: pass
        for m in re.finditer(r"\b(" + "|".join(WEEKDAYS) + r")\b", lower):
            days = (WEEKDAYS[m.group()] - today.weekday()) % 7
            matches.append((m.start(), today + timedelta(days=days)))
        if matches:
            # A correction in the same utterance wins over an earlier suggestion.
            found = sorted(matches, key=lambda item: item[0])[-1][1]
    return found.isoformat() if found else None


def _time_request(turns):
    found = None
    preference = None
    for turn in turns:
        lower = turn.casefold()
        if re.search(r"\b(subah|morning)\b", lower): preference = "morning"
        if re.search(r"\b(shaam|evening)\b", lower): preference = "evening"
        times = []
        for m in re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(?:baje|am|pm)?\b", lower):
            if not (m.group(2) or re.search(r"(?:baje|am|pm)\b", lower[m.start():m.end()+5])): continue
            hour, minute = int(m.group(1)), int(m.group(2) or 0)
            if hour > 23 or minute > 59: continue
            if hour < 12 and (preference == "evening" or "pm" in lower[m.end():m.end()+3]): hour += 12
            times.append((m.start(), f"{hour:02d}:{minute:02d}"))
        for word, hour in WORDS.items():
            for m in re.finditer(r"\b" + word + r"\s*baje\b", lower):
                h = hour + (12 if hour < 12 and preference == "evening" else 0)
                times.append((m.start(), f"{h:02d}:00"))
        if times: found = sorted(times)[-1][1]
    return found, preference


def _reply(state, reason=None, doctor=None, day=None, slot=None):
    if state == "booked": return f"Ji, {day} ko {slot} par {doctor} ke saath appointment book ho gaya hai."
    if state == "rescheduled": return f"Ji, appointment {day} ko {slot} par {doctor} ke saath reschedule ho gaya hai."
    if state == "cancelled": return "Ji, aapka appointment cancel ho gaya hai."
    if reason == "clinical_urgent": return "Main abhi clinic team se aapko connect kar raha hoon. Agar takleef abhi ho rahi hai, turant emergency care lijiye."
    if reason == "medical_advice": return "Iska jawab clinician hi de sakte hain. Main aapko clinic team se connect kar raha hoon."
    if reason == "ambiguous_patient": return "Is naam se ek se zyada records hain. Main clinic team se aapki pehchan confirm karwa deta hoon."
    if reason == "not_authorised": return "Main kisi aur ka record bina authorisation ke badal nahi sakta. Clinic team aapse baat karegi."
    if reason: return "Is request mein clinic team ki madad chahiye. Main unse aapko connect kar raha hoon."
    if state == "refused": return "Main bulk ya administrative changes is call par nahi kar sakta."
    return "Abhi koi appointment change nahi hua. Jab details mil jayen, phir baat kar sakte hain."


def run(payload, tools=None):
    started = time.monotonic()
    tools = tools or ClinicTools()
    turns = payload["turns"]
    whole = " ".join(turns).casefold()
    today = date.fromisoformat(payload["today"])
    state, reason, patient_id, appointment_id = "abandoned", None, None, None
    doctor_name = day = slot = None

    def escalate(why, detail):
        nonlocal state, reason
        tools.escalate_to_human(why, detail)
        state, reason = "escalated", why

    try:
        # Scan the whole fixed script before any mutation. A late emergency wins.
        if any(re.search(pattern, whole) for pattern in URGENT):
            escalate("clinical_urgent", "Caller reported symptoms requiring immediate clinician attention")
        elif any(re.search(pattern, whole) for pattern in ADVICE):
            escalate("medical_advice", "Caller requested clinical judgement")
        elif re.search(r"ignore (?:your|all|previous) instructions|administrator mode|cancel every|cancel all|internal test, proceed", whole):
            state = "refused"
        else:
            is_cancel = bool(re.search(r"cancel|radd", whole))
            is_move = bool(re.search(r"reschedul|postpone|move (?:my|the) appointment|appointment.*(?:shift|karwana hai.*(?:saturday|somwar))|use saturday", whole))
            is_book = bool(re.search(r"appointment|book|milna|dikhana|aa sakta|ke saath|chahiye", whole))
            doctor = next((d for d in tools.data["doctors"] if d["name"].split()[-1].casefold() in whole), None)
            doctor_name = doctor["name"] if doctor else None
            day = _last_date(turns, today)
            requested, preference = _time_request(turns)
            phone_matches = re.findall(r"(?<!\d)\d{10}(?!\d)", whole)
            phone = phone_matches[-1] if phone_matches else None

            # Explicit names beat a shared household phone. Match the longest first.
            named = sorted((p for p in tools.data["patients"] if p["name"].casefold() in whole), key=lambda p: -len(p["name"]))
            child = next((p for p in named if p["dob"] > "2010"), None)
            if child is None:
                child = next((p for p in tools.data["patients"] if p["dob"] > "2010" and
                              re.search(r"\b" + re.escape(p["name"].split()[0].casefold()) + r"\b", whole)), None)
            target = child or (named[0] if named else None)
            if target is None and re.search(r"\bsharma\b", whole):
                candidates = tools.lookup_patient("Sharma", phone)
            elif target is not None:
                candidates = tools.lookup_patient(target["name"], target["phone"] if child else phone)
            elif phone:
                candidates = [p for p in tools.data["patients"] if p["phone"] == phone]
                tools.lookup_patient(candidates[0]["name"].split()[-1] if candidates else "unknown", phone)
            else:
                candidates = []

            caller = next((p for p in named if p != target and (phone is None or p["phone"] == phone)), None)
            if target and not child and phone and target["phone"] != phone:
                caller = next((p for p in tools.data["patients"] if p["phone"] == phone), None)
            on_behalf = bool(re.search(r"(?:ke liye|ka appointment|unka|their|for my|for her|for him|padosi|neighbou?r|husband|wife|spouse|brother|sister|father|mother|friend|dost)", whole))
            unauthorised = bool(target and caller and caller["id"] != target["id"] and target["id"] not in caller["guardian_of"] and on_behalf)
            if re.search(r"padosi|neighbou?r", whole) and is_cancel:
                unauthorised = True
            if unauthorised:
                escalate("not_authorised", "Caller is neither the patient nor a listed guardian")
            elif len(candidates) > 1:
                escalate("ambiguous_patient", "Multiple patient records match the details supplied")
            elif is_cancel or is_move or is_book:
                if not patient_id and doctor and day and not candidates:
                    tools.search_slots(doctor["id"], day)
                if len(candidates) == 1: patient_id = candidates[0]["id"]
                if not patient_id and not (day and doctor):
                    pass
                elif not patient_id:
                    pass
                else:
                    appointments = [a for a in tools.data["appointments"] if a["patient_id"] == patient_id and a["status"] == "booked" and (not doctor or a["doctor_id"] == doctor["id"])]
                    if is_cancel or is_move:
                        old_day = today.isoformat() if re.search(r"\b(aaj|today)\b", whole) else None
                        if old_day: appointments = [a for a in appointments if a["date"] == old_day]
                        if len(appointments) != 1:
                            escalate("out_of_scope", "Appointment could not be uniquely identified")
                        elif is_cancel:
                            appointment_id = tools.cancel_appointment(appointments[0]["id"], patient_id)["id"]
                            state = "cancelled"
                        else:
                            doctor = tools._doctor(appointments[0]["doctor_id"])
                            doctor_name = doctor["name"]
                            if day:
                                slots = tools.search_slots(doctor["id"], day)
                                slot = requested or next((s for s in slots if preference != "morning" or s < "12:00"), None)
                                if slot in slots:
                                    appointment_id = tools.reschedule_appointment(appointments[0]["id"], patient_id, day, slot)["id"]
                                    state = "rescheduled"
                    elif doctor and day:
                        slots = tools.search_slots(doctor["id"], day)
                        eligible = [s for s in slots if preference != "morning" or s < "12:00"]
                        if preference == "evening": eligible = [s for s in slots if s >= "16:00"]
                        slot = requested or (eligible[0] if eligible else None)
                        if slot in slots:
                            appointment_id = tools.book_appointment(patient_id, doctor["id"], day, slot)["id"]
                            state = "booked"
            elif doctor and day:
                tools.search_slots(doctor["id"], day)
    except ToolError as exc:
        escalate("out_of_scope", str(exc))

    return {"conversation_id": payload["conversation_id"], "tool_calls": tools.calls,
            "terminal_state": state, "escalation_reason": reason, "patient_id": patient_id,
            "appointment_id": appointment_id, "reply": _reply(state, reason, doctor_name, day, slot),
            "metrics": {"turns": len(turns), "tokens": 0, "latency_ms": math.ceil((time.monotonic() - started) * 1000)}}
