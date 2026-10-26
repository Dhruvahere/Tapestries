#dummy data 



import random
from datetime import date, datetime, timedelta, timezone

import recall
from db import get_db, get_setting, init_db, set_setting

SUBJECTS = {
    "Advanced Biology": [
        ("3", "Mitosis", "14", "Mitosis"),
        ("3", "Meiosis", "15", "Meiosis"),
        ("3", "DNA replication", "18", "Helicase"),
        ("4", "Photosynthesis", "22", "Calvin"),
        ("4", "Respiration", "24", "Krebs"),
        ("5", "Mendel", "30", "Allele"),
        ("5", "Hardy-Weinberg", "31", "p²"),
        ("6", "Action potential", "40", "Sodium"),
        ("6", "Synapse", "41", "Vesicle"),
        ("7", "Kidney", "48", "Nephron"),
    ],
    "Physics": [
        ("2", "Thermodynamics", "8", "Q=mcΔT"),
        ("2", "Sound", "12", "v=fλ"),
        ("3", "Circuits", "20", "Kirchhoff"),
        ("3", "Magnetism", "24", "Flux"),
        ("4", "Waves", "30", "Interference"),
        ("5", "Photoelectric", "36", "hf"),
    ],
    "History": [
        ("1", "Meluha", "4", "Indus Valley Civilization"),
        ("1", "Sumerian Language", "6", "Dingir"),
        ("2", "Innana", "12", "Epic of Gilgamesh"),
        ("2", "Assyrian Empire", "15", "Cuneiform"),
        ("3", "Cylinder Seal", "22", "Naram-Sin"),
    ],
}

TYPICAL = {"Advanced Biology": (70, 20), "Physics": (95, 25), "History": (80, 18)}

FORCE = {
    ("Advanced Biology", "14"): (1, 4, 0),
    ("Advanced Biology", "15"): (1, 1, 0),
    ("Advanced Biology", "22"): (2, 0, 1),
    ("Advanced Biology", "24"): (1, 2, 0),
    ("Physics", "8"): (1, 3, 0),
    ("Physics", "20"): (2, 0, 1),
    ("Physics", "24"): (1, 5, 0),
    ("History", "4"): (1, 2, 0),
    ("History", "12"): (2, 1, 1),
}


def _utc(day, seconds_into=10 * 3600):
    dt = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(seconds=seconds_into)
    return dt.replace(microsecond=0)


def seed(path=None, seed=11):
    init_db(path)
    g = random.Random(seed)
    today = date.today()
    with get_db(path) as con:
        if get_setting(con, "demo") == "1":
            return False
        if con.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]:
            return None
        ids = {}
        for subject, pages in SUBJECTS.items():
            sid = con.execute("INSERT INTO subjects (name) VALUES (?)", (subject,)).lastrowid
            units = {}
            for unit, topic, page_no, head in pages:
                if unit not in units:
                    units[unit] = con.execute(
                        "INSERT INTO units (subject_id, name) VALUES (?, ?)", (sid, unit)
                    ).lastrowid
                pid = con.execute(
                    "INSERT INTO pages (unit_id, topic, page_no, head_word, created_on, box, due_on, "
                    "passes_in_row, last_pass_on) VALUES (?,?,?,?,?,?,?,?,?)",
                    (units[unit], topic, page_no, head, (today - timedelta(days=40)).isoformat(),
                     1, (today - timedelta(days=40)).isoformat(), 0, None),
                ).lastrowid
                ids[pid] = {"subject": subject, "sid": sid}
        set_setting(con, "demo", "1")

        pages = [dict(r) for r in con.execute("SELECT * FROM pages")]
        last_pass = {}
        slot = 0
        for ago in range(28, -1, -1):
            day = today - timedelta(days=ago)
            due = [p for p in pages if recall.parse_day(p["due_on"]) <= day]
            g.shuffle(due)
            take = due[: g.randint(3, 6)]
            for p in take:
                mu, sd = TYPICAL[ids[p["id"]]["subject"]]
                seconds = max(25, int(g.gauss(mu, sd)))
                if g.random() < 0.04:
                    seconds = 20 * 60
                opened = _utc(day, 9 * 3600 + 90 * slot)
                tapped = opened + timedelta(seconds=seconds)
                slot += 1
                result = "fail" if g.random() < 0.22 else "pass"
                fields = recall.apply(p, result, day, last_pass.get(p["id"]))
                p.update(fields)
                if result == "pass":
                    last_pass[p["id"]] = day
                else:
                    last_pass.pop(p["id"], None)
                con.execute(
                    "INSERT INTO recalls (page_id, opened_at, tapped_at, result, seconds) VALUES (?,?,?,?,?)",
                    (p["id"], opened.strftime("%Y-%m-%d %H:%M:%S"),
                     tapped.strftime("%Y-%m-%d %H:%M:%S"), result, seconds),
                )

        for p in pages:
            key = (ids[p["id"]]["subject"], p["page_no"])
            if key in FORCE:
                box, overdue, streak = FORCE[key]
                p["box"] = box
                p["due_on"] = (today - timedelta(days=overdue)).isoformat()
                p["passes_in_row"] = streak
            con.execute(
                "UPDATE pages SET box=?, due_on=?, passes_in_row=?, last_pass_on=? WHERE id=?",
                (p["box"], p["due_on"], p["passes_in_row"], p.get("last_pass_on"), p["id"]),
            )
    return True


def wipe_demo(path=None):
    init_db(path)
    with get_db(path) as con:
        if get_setting(con, "demo") != "1":
            return False
        con.execute("DELETE FROM recalls WHERE page_id IN (SELECT id FROM pages)")
        con.execute("DELETE FROM pages")
        con.execute("DELETE FROM day_weights")
        con.execute("DELETE FROM days")
        con.execute("DELETE FROM units")
        con.execute("DELETE FROM subjects")
        set_setting(con, "demo", "0")
    return True


if __name__ == "__main__":
    print("seeded" if seed() else "index already has pages; left it alone")
