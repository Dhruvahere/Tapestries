import seed_data
from db import get_db, get_setting, init_db

from datetime import date, datetime, timezone

from flask import Flask, render_template, request, redirect, url_for, abort

import montecarlo
import plain
import recall

app = Flask(__name__)


def subjects(con):
    return con.execute("SELECT * FROM subjects ORDER BY name").fetchall()


def get_or_create_subject(con, name):
    name = name.strip()
    row = con.execute("SELECT id FROM subjects WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    return con.execute("INSERT INTO subjects (name) VALUES (?)", (name,)).lastrowid


def get_or_create_unit(con, subject_id, name):
    name = name.strip()
    row = con.execute("SELECT id FROM units WHERE subject_id = ? AND name = ?", (subject_id, name)).fetchone()
    if row:
        return row["id"]
    return con.execute("INSERT INTO units (subject_id, name) VALUES (?, ?)", (subject_id, name)).lastrowid


def get_page(con, page_id):
    page = con.execute(
        """
        SELECT p.*, u.name AS unit, u.subject_id, s.name AS subject
        FROM pages p
        JOIN units u ON u.id = p.unit_id
        JOIN subjects s ON s.id = u.subject_id
        WHERE p.id = ?
        """,
        (page_id,),
    ).fetchone()
    if page is None:
        abort(404)
    return page


def todays_row(con, today):
    return con.execute("SELECT * FROM days WHERE date = ?", (today.isoformat(),)).fetchone()


def load_weights(con, today, due):
    saved = {r["subject_id"]: r["weight"] for r in con.execute(
        "SELECT subject_id, weight FROM day_weights WHERE date = ?", (today.isoformat(),)
    )}
    sugg = recall.suggested_weights(due)
    out = {}
    for s in subjects(con):
        if s["id"] in saved:
            out[s["id"]] = saved[s["id"]]
        elif s["id"] in sugg:
            out[s["id"]] = sugg[s["id"]]
        else:
            out[s["id"]] = 1.0
    return out


def pick_pages(due, split, fits):
    chosen, by_id = [], {}
    groups = montecarlo.group_due(due)
    for sid, pages in groups.items():
        budget, used = split.get(sid, 0) * 60, 0.0
        typical = montecarlo.median_seconds(fits.get(sid) or montecarlo.fit_subject([]))
        for i, p in enumerate(pages):
            if budget <= 0:
                break
            if used + typical > budget:
                if i == 0:
                    chosen.append(p)
                    by_id[p["id"]] = p
                break
            used += typical
            chosen.append(p)
            by_id[p["id"]] = p
    return chosen, by_id


def build_plan(con, today, minutes, weights):
    due = recall.due_rows(con, today)
    prior = montecarlo.seconds_by_subject(con)
    planned = montecarlo.plan(due, weights, minutes, prior, seed=today.toordinal())
    chosen, _ = pick_pages(due, planned["split"], planned["fits"])
    planned["page_ids"] = [p["id"] for p in chosen]
    planned["typical"] = {
        sid: montecarlo.median_seconds(planned["fits"].get(sid) or montecarlo.fit_subject([]))
        for sid in planned["split"]
    }
    con.execute("INSERT OR REPLACE INTO days (date, minutes, plan_json) VALUES (?, ?, ?)",
                (today.isoformat(), minutes, montecarlo.encode_plan(planned)))
    con.execute("DELETE FROM day_weights WHERE date = ?", (today.isoformat(),))
    for sid, w in weights.items():
        con.execute("INSERT INTO day_weights (date, subject_id, weight) VALUES (?, ?, ?)",
                    (today.isoformat(), sid, w))
    return planned


def todays_list(con, today):
    row = todays_row(con, today)
    if not row or not row["plan_json"]:
        return None, []
    planned = montecarlo.decode_plan(row["plan_json"])
    done = {r["page_id"] for r in con.execute(
        "SELECT page_id FROM recalls WHERE date(tapped_at) = ?", (today.isoformat(),)
    )}
    remaining = []
    for pid in planned["page_ids"]:
        if pid in done:
            continue
        page = con.execute(
            """
            SELECT p.*, u.name AS unit, u.subject_id, s.name AS subject
            FROM pages p
            JOIN units u ON u.id = p.unit_id
            JOIN subjects s ON s.id = u.subject_id
            WHERE p.id = ?
            """,
            (pid,),
        ).fetchone()
        if page:
            remaining.append(dict(page))
    return planned, remaining


def group_by_subject(pages):
    groups = []
    by_name = {}
    for p in pages:
        if p["subject"] not in by_name:
            by_name[p["subject"]] = []
            groups.append((p["subject"], by_name[p["subject"]]))
        by_name[p["subject"]].append(p)
    return groups


@app.get("/")
def home():
    today = date.today()
    just = request.args.get("just")
    due_on = request.args.get("due")
    with get_db() as con:
        demo_on = get_setting(con, "demo") == "1"
        page_count = con.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]
        due = recall.due_rows(con, today)
        planned, remaining = todays_list(con, today)
        held_total, held_parts = recall.held_counts(con)
        day = todays_row(con, today)
        minutes = day["minutes"] if day else 30
        weights = load_weights(con, today, due)
        names = {s["id"]: s["name"] for s in subjects(con)}
    weight_rows = [{"id": sid, "name": names[sid], "weight": weights[sid]} for sid in weights]
    groups = []
    if planned:
        split = planned.get("split") or {}
        typical = planned.get("typical") or {}
        for name, pages in group_by_subject(remaining):
            sid = pages[0]["subject_id"]
            groups.append({
                "name": name,
                "minutes_label": plain.minutes_phrase(split.get(sid, 0)),
                "page_time": plain.page_time_phrase(typical.get(sid, montecarlo.PRIOR_SECONDS)),
                "pages": pages,
            })
    kind = planned["kind"] if planned else None
    return render_template(
        "home.html",
        demo_on=demo_on,
        empty=page_count == 0,
        planned=planned,
        groups=groups,
        remaining=remaining,
        minutes=minutes,
        weight_rows=weight_rows,
        today_line=plain.today_line(len(remaining), minutes, kind or "proportional") if planned else None,
        chance=plain.chance_line(planned["p_top"]) if planned else None,
        week=plain.weekly_line(held_total, held_parts),
        just=plain.after_tap(just, due_on) if just and due_on else None,
        first_open=plain.first_open(),
    )

@app.post("/plan")
def plan_save():
    today = date.today()
    try:
        minutes = int(request.form["minutes"])
    except (KeyError, ValueError):
        abort(400, "Minutes required")
    minutes = max(0, min(minutes, 720))
    with get_db() as con:
        weights = {}
        for s in subjects(con):
            raw = request.form.get(f"weight_{s['id']}", "1")
            try:
                weights[s["id"]] = max(0.0, float(raw))
            except ValueError:
                weights[s["id"]] = 1.0
        if not weights:
            abort(400, "Add a page first")
        if sum(weights.values()) <= 0:
            for sid in weights:
                weights[sid] = 1.0
        build_plan(con, today, minutes, weights)
    return redirect(url_for("home"))


@app.get("/index")
def index():
    with get_db() as con:
        pages = con.execute(
            """
            SELECT p.*, u.name AS unit, s.name AS subject
            FROM pages p
            JOIN units u ON u.id = p.unit_id
            JOIN subjects s ON s.id = u.subject_id
            ORDER BY s.name, u.name, p.page_no
            """
        ).fetchall()
    return render_template("index.html", pages=pages)


@app.get("/page/new")
def page_new():
    with get_db() as con:
        return render_template("page_new.html", subjects=subjects(con))


@app.post("/page")
def page_create():
    subject = (request.form.get("subject_new") or request.form.get("subject") or "").strip()
    unit = request.form.get("unit", "").strip()
    topic = request.form.get("topic", "").strip()
    page_no = request.form.get("page_no", "").strip()
    head = request.form.get("head_word", "").strip()
    if not (subject and unit and topic and page_no and head):
        abort(400, "Every field is required")
    today = date.today().isoformat()
    with get_db() as con:
        sid = get_or_create_subject(con, subject)
        uid = get_or_create_unit(con, sid, unit)
        con.execute(
            "INSERT INTO pages (unit_id, topic, page_no, head_word, created_on, box, due_on, "
            "passes_in_row, last_pass_on) VALUES (?,?,?,?,?,?,?,?,?)",
            (uid, topic, page_no, head, today, 1, today, 0, None),
        )
    return redirect(url_for("index"))


@app.get("/page/<int:page_id>")
def page_open(page_id):
    with get_db() as con:
        page = get_page(con, page_id)
    return render_template(
        "page.html",
        page=page,
        opened_at=recall.now_utc(),
        prompt=plain.open_prompt(page),
    )


@app.post("/page/<int:page_id>/recall")
def page_recall(page_id):
    result = request.form.get("result")
    opened_at = request.form.get("opened_at", "")
    if result not in ("pass", "fail"):
        abort(400, "Tap got it or missed it")
    tapped = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        opened = datetime.strptime(opened_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        opened = tapped
    seconds = max(int((tapped - opened).total_seconds()), 1)
    today = date.today()
    with get_db() as con:
        page = get_page(con, page_id)
        fields = recall.apply(page, result, today, page["last_pass_on"])
        con.execute(
            "INSERT INTO recalls (page_id, opened_at, tapped_at, result, seconds) VALUES (?,?,?,?,?)",
            (page_id, opened_at or recall.now_utc(), tapped.strftime("%Y-%m-%d %H:%M:%S"), result, seconds),
        )
        con.execute(
            "UPDATE pages SET box=?, due_on=?, passes_in_row=?, last_pass_on=? WHERE id=?",
            (fields["box"], fields["due_on"], fields["passes_in_row"], fields["last_pass_on"], page_id),
        )
    return redirect(url_for("home", just=result, due=fields["due_on"]))


@app.post("/demo")
def demo_load():
    with get_db() as con:
        if get_setting(con, "demo") != "1" and con.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]:
            return redirect(url_for("home"))
    seed_data.seed()
    today = date.today()
    with get_db() as con:
        due = recall.due_rows(con, today)
        weights = load_weights(con, today, due)
        if weights:
            build_plan(con, today, 15, weights)
    return redirect(url_for("home"))


@app.post("/demo/clear")
def demo_clear():
    with get_db() as con:
        if get_setting(con, "demo") != "1":
            return redirect(url_for("page_new"))
    seed_data.wipe_demo()
    return redirect(url_for("page_new"))



@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/docs")
def docs():
    return render_template("docs.html", ladder=recall.BOX_DAYS, held=recall.HELD_STREAK,
                           min_logs=montecarlo.MIN_LOGS, cap=montecarlo.OUTLIER_CAP // 60)


init_db()

if __name__ == "__main__":
    app.run(port=5001, debug=True)
