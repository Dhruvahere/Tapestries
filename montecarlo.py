
import json
import math

import numpy as np

import recall

OUTLIER_CAP = 15 * 60
MIN_LOGS = 10
PRIOR_SECONDS = 90
PRIOR_SIGMA = 0.5
RUNS = 1_000
CANDIDATES = 36
STEP = 1


def rng(seed=0):
    return np.random.default_rng(seed)


def fit_subject(seconds):
    clean = [s for s in seconds if 0 < s <= OUTLIER_CAP]
    if len(clean) < MIN_LOGS:
        return {"ok": False, "mu": math.log(PRIOR_SECONDS), "sigma": PRIOR_SIGMA, "n": len(clean)}
    x = np.log(np.asarray(clean, dtype=float))
    sigma = float(x.std(ddof=1))
    return {"ok": True, "mu": float(x.mean()), "sigma": max(sigma, 0.15), "n": len(clean)}


def median_seconds(fit):
    return float(np.exp(fit["mu"]))


def draw_seconds(fit, gen, n=1):
    return gen.lognormal(fit["mu"], fit["sigma"], size=n)


def _round_split(raw, minutes):
    if not raw or minutes <= 0:
        return {k: 0 for k in raw}
    total = sum(raw.values())
    if total <= 0:
        even = minutes // max(len(raw), 1)
        leftover = minutes - even * len(raw)
        out = {k: even for k in raw}
        for k in list(raw)[:leftover]:
            out[k] += 1
        return out
    ideal = {k: minutes * (v / total) for k, v in raw.items()}
    base = {k: int(v) for k, v in ideal.items()}
    leftover = minutes - sum(base.values())
    for k in sorted(ideal, key=lambda k: ideal[k] - base[k], reverse=True)[:leftover]:
        base[k] += 1
    return base


def equal_split(subject_ids, minutes):
    return _round_split({sid: 1.0 for sid in subject_ids}, minutes)


def proportional_split(weights, minutes):
    return _round_split(weights, minutes)


def group_due(due):
    groups = {}
    for p in due:
        groups.setdefault(p["subject_id"], []).append(p)
    for pages in groups.values():
        pages.sort(key=lambda p: (-p["risk"], p["box"], p["page_no"]))
    return groups


def candidates(weights, minutes, n=CANDIDATES, seed=0):
    ids = list(weights)
    base = proportional_split(weights, minutes)
    out = [base]
    gen = rng(seed)
    w = np.array([max(weights[sid], 1e-6) for sid in ids], dtype=float)
    w = w / w.sum()
    for _ in range(n - 1):
        draw = gen.dirichlet(w * 8)
        out.append(_round_split({sid: float(x) for sid, x in zip(ids, draw)}, minutes))
    seen, uniq = set(), []
    for split in out:
        key = tuple(split[sid] for sid in ids)
        if key not in seen:
            seen.add(key)
            uniq.append(split)
    return uniq


def _walk(pages, budget_sec, durations):
    done, used = [], 0.0
    for p, dur in zip(pages, durations):
        if used + dur > budget_sec:
            break
        used += dur
        done.append(p)
    return done


def simulate_split(due, split, fits, runs=RUNS, seed=0):
    groups = group_due(due)
    gen = rng(seed)
    scores = []
    finished_sets = []
    for _ in range(runs):
        done_ids, risk_sum = set(), 0.0
        for sid, pages in groups.items():
            durs = draw_seconds(fits[sid], gen, n=len(pages))
            done = _walk(pages, split.get(sid, 0) * 60, durs)
            done_ids.update(p["id"] for p in done)
            risk_sum += sum(p["risk"] for p in done)
        scores.append(risk_sum)
        finished_sets.append(done_ids)
    return scores, finished_sets


def top_risk_ids(due, minutes, fits):
    remaining = minutes * 60
    chosen = []
    for p in sorted(due, key=lambda x: (-x["risk"], x["box"])):
        need = median_seconds(fits[p["subject_id"]])
        if remaining >= need:
            chosen.append(p["id"])
            remaining -= need
        else:
            break
    return chosen


def seconds_by_subject(con):
    rows = con.execute(
        """
        SELECT u.subject_id, r.seconds
        FROM recalls r
        JOIN pages p ON p.id = r.page_id
        JOIN units u ON u.id = p.unit_id
        """
    ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["subject_id"], []).append(r["seconds"])
    return out


def plan(due, weights, minutes, prior_seconds, seed=0):
    """Recommend a minute split. kind is 'simulated' only when every weighted subject has enough logs."""
    ids = list(weights)
    fits = {sid: fit_subject(prior_seconds.get(sid, [])) for sid in ids}
    enough = all(fits[sid]["ok"] for sid in ids)
    prop = proportional_split(weights, minutes)
    if not due or minutes <= 0:
        return {"kind": "proportional", "split": prop, "score": 0.0, "p_top": None, "fits": fits}
    if not enough:
        return {"kind": "proportional", "split": prop, "score": 0.0, "p_top": None, "fits": fits}

    best, best_score, best_sets = prop, -1.0, []
    for i, split in enumerate(candidates(weights, minutes, seed=seed)):
        scores, sets = simulate_split(due, split, fits, seed=seed + i + 1)
        mean = float(np.mean(scores))
        if mean > best_score:
            best, best_score, best_sets = split, mean, sets
    top = set(top_risk_ids(due, minutes, fits))
    p_top = None
    if top and best_sets:
        p_top = float(np.mean([top <= done for done in best_sets]))
    return {"kind": "simulated", "split": best, "score": best_score, "p_top": p_top, "fits": fits}


def encode_plan(planned):
    return json.dumps({
        "kind": planned["kind"],
        "split": {str(k): v for k, v in planned["split"].items()},
        "typical": {str(k): v for k, v in planned.get("typical", {}).items()},
        "p_top": planned["p_top"],
        "page_ids": planned.get("page_ids", []),
    })


def decode_plan(text):
    if not text:
        return None
    data = json.loads(text)
    data["split"] = {int(k): v for k, v in data["split"].items()}
    data["typical"] = {int(k): v for k, v in data.get("typical", {}).items()}
    return data
