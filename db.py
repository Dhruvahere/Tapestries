#please do not try to change this. this is the database calller.

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "Library/Application Support/Tapestries/tapestries.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    name TEXT NOT NULL,
    UNIQUE (subject_id, name)
);
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    topic TEXT NOT NULL,
    page_no TEXT NOT NULL,
    head_word TEXT NOT NULL,
    created_on TEXT NOT NULL,
    box INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
    due_on TEXT NOT NULL,
    passes_in_row INTEGER NOT NULL DEFAULT 0,
    last_pass_on TEXT
);
CREATE TABLE IF NOT EXISTS recalls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES pages(id),
    opened_at TEXT NOT NULL,
    tapped_at TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('pass', 'fail')),
    seconds INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS days (
    date TEXT PRIMARY KEY,
    minutes INTEGER NOT NULL,
    plan_json TEXT
);
CREATE TABLE IF NOT EXISTS day_weights (
    date TEXT NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    weight REAL NOT NULL,
    PRIMARY KEY (date, subject_id)
);
CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, 
        value TEXT NOT NULL
        );
"""


def get_db(path=None):
    con = sqlite3.connect(path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(path=None):
    with get_db(path) as con:
        con.executescript(SCHEMA)

def get_setting(con, key, default=None):
    row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(con, key, value):
    con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))