#This is how the app talks to you!!! 

def first_open():
    return "You do not have to set this up. Try the demo, or add one page you already wrote."

def _pages(n):
    return "1 page" if n == 1 else f"{n} pages"


def _topics(n):
    return "1 topic has held" if n == 1 else f"{n} topics have held"


def today_line(n_left, minutes, kind):
    if n_left == 0:
        return "All done! "
    label = "from your own times" if kind == "simulated" else "a first-pass split until you have more timed recalls"
    return f"Today: {_pages(n_left)} in about {minutes} minutes ({label}). Open the first page and recall it."


def weekly_line(total, parts):
    if total == 0:
        return "Held means three failed attempts, on three different days. At the start, there shouldn't be any. "
    bits = ", ".join(f"{p['name']} {p['n']}" for p in parts if p["n"])
    extra = f" ({bits})" if bits else ""
    return f"{_topics(total)}.{extra}"


def after_tap(result, due_on):
    if result == "pass":
        return f"That page will come back on {due_on}."
    return f"Valiant effort! Study up for another recall on({due_on})."


def chance_line(p_top):
    if p_top is None:
        return None
    pct = round(p_top * 100)
    return f"Chance the riskiest pages all get done in this time: {pct}%."


def minutes_phrase(n):
    n = int(n or 0)
    if n <= 0:
        return "no time today"
    if n == 1:
        return "1 minute"
    return f"{n} minutes"


def page_time_phrase(seconds):
    seconds = max(int(round(seconds or 0)), 1)
    if seconds < 90:
        return f"about {seconds} seconds"
    mins = max(1, int(round(seconds / 60.0)))
    if mins == 1:
        return "about 1 minute"
    return f"about {mins} minutes"


def open_prompt(page):
    return (f"Close the notebook first. Recall page {page['page_no']}, {page['head_word']}. "
            f"then open the notebook and check. Tap the button if you really know.")
