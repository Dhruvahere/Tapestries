# you want to know what the boxes are? here they are, they are a more insignificant part of the project, but they are actually derived from leitner.


from datetime import date, datetime, timedelta, timezone

# Box 1..5. A conventional starting ladder, not an optimized one.
BOX_DAYS = (1, 3, 7, 14, 30)
HELD_STREAK = 3


def parse_day(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def interval(box):
    return BOX_DAYS[min(max(int(box), 1), 5) - 1]


def risk(due_on, box, today=None):
    """Days overdue / this box's interval. Due today is 0. Higher means more at risk."""
    today = today or date.today()
    overdue = max((today - parse_day(due_on)).days, 0)
    return overdue / interval(box)


def apply(page, result, today, last_pass_on=None):
    """Move a page after one pass or fail. last_pass_on is the previous pass date, if any."""
    today = parse_day(today)
    last = parse_day(last_pass_on) if last_pass_on else None
    box = int(page["box"])
    streak = int(page["passes_in_row"] or 0)
    if result == "pass":
        box = min(box + 1, 5)
        if last is None or last < today:
            streak += 1
        last = today
    else:
        box = 1
        streak = 0
    return {
        "box": box,
        "due_on": (today + timedelta(days=interval(box))).isoformat(),
        "passes_in_row": streak,
        "last_pass_on": last.isoformat() if last else None,
    }


def held(page):
    return int(page["passes_in_row"] or 0) >= HELD_STREAK


def due_rows(con, today=None):
    today = today or date.today()
    rows = con.execute(
        """
        SELECT p.*, u.name AS unit, u.subject_id, s.name AS subject
        FROM pages p
        JOIN units u ON u.id = p.unit_id
        JOIN subjects s ON s.id = u.subject_id
        WHERE p.due_on <= ?
        ORDER BY s.name, p.box, p.page_no
        """,
        (today.isoformat(),),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["risk"] = risk(d["due_on"], d["box"], today)
        d["held"] = held(d)
        out.append(d)
    out.sort(key=lambda p: (-p["risk"], p["subject"], p["box"], p["page_no"]))
    return out


def suggested_weights(due):
    """Defaults from how overdue each subject is. Subjects with no due pages get a 1."""
    totals = {}
    for p in due:
        totals[p["subject_id"]] = totals.get(p["subject_id"], 0.0) + p["risk"]
    return {sid: (total if total > 0 else 1.0) for sid, total in totals.items()}


def last_pass_on(con, page_id):
    row = con.execute("SELECT last_pass_on FROM pages WHERE id = ?", (page_id,)).fetchone()
    return row["last_pass_on"] if row else None


def held_counts(con):
    rows = con.execute(
        """
        SELECT s.id, s.name, SUM(CASE WHEN p.passes_in_row >= ? THEN 1 ELSE 0 END) AS n
        FROM subjects s
        LEFT JOIN units u ON u.subject_id = s.id
        LEFT JOIN pages p ON p.unit_id = u.id
        GROUP BY s.id
        ORDER BY s.name
        """,
        (HELD_STREAK,),
    ).fetchall()
    parts = [{"id": r["id"], "name": r["name"], "n": int(r["n"] or 0)} for r in rows]
    return sum(p["n"] for p in parts), parts
