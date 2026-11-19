"""Watches Trump's Truth Social posts (trumpstruth.org RSS archive; robots.txt allows all) → data/posts.json.

With GROQ_API_KEY: classifies new posts (market_relevant, topic, target, threat size, deadline),
adds new deadlines to data/deadlines.json, and updates pending deadlines' status from recent
market-relevant posts and AP market stories. Without it, posts are stored and classified on a later run.
Run: python3 scripts/watch.py
"""
import html, json, os, re, sys, datetime as dt
import urllib.robotparser
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from jsonschema import Draft202012Validator
from scrapling.fetchers import Fetcher
from extract import groq_json, TOPICS

ROOT = os.path.join(os.path.dirname(__file__), "..")
P = lambda *a: os.path.join(ROOT, *a)
FEED = "https://www.trumpstruth.org/feed"
UA = "trump-vs-spx-research/1.0 (+https://github.com/vtalla-hq/trump-vs-spx)"
MIN_CONF, LOOKBACK_DAYS = 0.8, 14
STATUSES = ["pending", "followed_through", "walked_back", "extended"]
DATE = {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"}

POST_SCHEMA = {"type": "object", "required": ["market_relevant", "topic", "target", "threat_size", "deadline", "summary"],
               "properties": {"market_relevant": {"type": "boolean"}, "topic": {"enum": TOPICS},
                              "target": {"type": ["string", "null"]}, "threat_size": {"type": ["number", "null"], "minimum": 0},
                              "deadline": DATE, "summary": {"type": "string"}}}
STATUS_SCHEMA = {"type": "object", "required": ["status", "confidence", "resolved_on", "new_deadline", "evidence"],
                 "properties": {"status": {"enum": STATUSES}, "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "resolved_on": DATE, "new_deadline": DATE, "evidence": {"type": "string"}}}

POST_SYSTEM = f"""You screen Donald Trump's Truth Social posts for anything that could move the US stock market.
Return ONE JSON object:
- market_relevant (bool): a tariff, trade, sanctions, war/military, Fed/interest-rate or economic-policy statement or threat.
  Endorsements, attacks on people, media and sports posts are false.
- topic: one of {TOPICS}.
- target: the country, company or institution targeted (short), or null.
- threat_size: the tariff rate threatened in percent (largest number if several), or null.
- deadline: the date (YYYY-MM-DD) on which a threatened or promised policy action takes effect or an ultimatum expires
  (a tariff start, sanctions, military action, a pause running out), or null. Press conferences, meetings, votes, bills and
  other scheduled events are not deadlines. Resolve relative dates ("next Friday", "in two weeks") against the post date.
- summary: one sentence."""

STATUS_SYSTEM = f"""You track deadlines Donald Trump has set. Given one deadline and recent posts and news, decide its status:
- pending: not resolved yet. followed_through: the threatened action took effect on schedule.
- walked_back: he dropped, paused indefinitely or softened it. extended: he moved the deadline later.
Return ONE JSON object: status (one of {STATUSES}), confidence (0-1), resolved_on (YYYY-MM-DD or null),
new_deadline (YYYY-MM-DD if extended, else null), evidence (one sentence quoting what decided it).
Only leave pending if the texts do not settle it."""

load = lambda p, d: json.load(open(p)) if os.path.exists(p) else d
dump = lambda p, o: json.dump(o, open(p, "w"), ensure_ascii=False, indent=1)
errors = lambda schema, row: [e.message for e in Draft202012Validator(schema).iter_errors(row)]


def text_of(desc):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", desc or ""))).strip()


def fetch_posts():
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(Fetcher.get("https://www.trumpstruth.org/robots.txt", headers={"User-Agent": UA}, timeout=30).body.decode().splitlines())
    assert robots.can_fetch(UA, FEED), "robots.txt disallows the feed"
    page = Fetcher.get(FEED, headers={"User-Agent": UA}, timeout=30)
    assert page.status == 200, f"feed HTTP {page.status}"
    ns = {"truth": "https://truthsocial.com/ns"}
    posts = []
    for it in ET.fromstring(page.body).iter("item"):  # Scrapling's HTML parser mangles RSS, so parse the XML ourselves
        posts.append({"id": it.findtext("guid").rsplit("/", 1)[-1], "url": it.findtext("truth:originalUrl", it.findtext("link"), ns),
                      "ts": parsedate_to_datetime(it.findtext("pubDate")).isoformat(), "text": text_of(it.findtext("description"))})
    return posts


def main():
    posts = {p["id"]: p for p in load(P("data", "posts.json"), [])}
    fresh = [p for p in fetch_posts() if p["id"] not in posts]
    print(f"feed: {len(fresh)} new posts")
    for p in fresh:
        posts[p["id"]] = {**p, "cls": None}
    if not posts:
        sys.exit("watch: feed returned zero posts")
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        dump(P("data", "posts.json"), sorted(posts.values(), key=lambda p: p["ts"]))
        print("GROQ_API_KEY not set: posts stored, classification skipped")
        return

    deadlines = load(P("data", "deadlines.json"), [])
    for p in sorted(posts.values(), key=lambda p: p["ts"]):
        if p["cls"] is not None:
            continue
        if len(re.sub(r"https?://\S+|RT:|View (image|video)|Quoted Donald J\. Trump", "", p["text"]).strip()) < 25:  # media-only or bare reposts
            p["cls"] = {"skipped": "no text"}
            continue
        try:
            row = groq_json(POST_SYSTEM, f"Post date: {p['ts'][:10]}\n\n{p['text'][:4000]}", key, p["id"])
        except Exception as e:
            print(f"  {p['id']}: {e}")
            continue
        p["cls"] = row if not errors(POST_SCHEMA, row) else {"invalid": errors(POST_SCHEMA, row), "raw": row}
        # Only market topics: the model still files bill/vote timelines under "Other" as deadlines.
        if (row.get("market_relevant") and row.get("deadline") and row["deadline"] > p["ts"][:10] and "invalid" not in p["cls"]
                and row.get("topic") in ("Tariffs", "Iran war", "Fed")):
            dup = any(d["status"] == "pending" and d["deadline"] == row["deadline"] and (d["target"] or "").lower() == (row["target"] or "").lower()
                      for d in deadlines)
            if not dup:
                deadlines.append({"id": "a" + p["id"], "announced": p["ts"][:10], "deadline": row["deadline"], "said": row["summary"],
                                  "target": row["target"] or "Unspecified", "topic": row["topic"], "threat_size": row["threat_size"] or 0,
                                  "source_url": p["url"], "status": "pending", "resolved_on": None, "origin": "auto"})
                print(f"  new deadline {row['deadline']}: {row['summary']}")
    dump(P("data", "posts.json"), sorted(posts.values(), key=lambda p: p["ts"]))

    # Status updates: recent market-relevant posts and AP stories are the evidence.
    since = str(dt.date.today() - dt.timedelta(days=LOOKBACK_DAYS))
    news = [f"[{p['ts'][:10]} Trump post] {p['text'][:600]}" for p in posts.values()
            if p["ts"][:10] >= since and (p["cls"] or {}).get("market_relevant")]
    news += [f"[{s['date']} AP market story] {s['text'][:800]}" for s in load(P("data", "headlines.json"), [])
             if not s.get("missing") and s["date"] >= since]
    for d in [d for d in deadlines if d["status"] == "pending"]:
        if not news:
            break
        try:
            row = groq_json(STATUS_SYSTEM, f"Deadline: {json.dumps({k: d[k] for k in ('announced', 'deadline', 'said', 'target')})}\n\n"
                            + "\n".join(sorted(news)[-40:]), key, d["id"])
        except Exception as e:
            print(f"  {d['id']}: {e}")
            continue
        if errors(STATUS_SCHEMA, row) or row["status"] == "pending" or row["confidence"] < MIN_CONF:
            continue
        d.update(status=row["status"], resolved_on=row["resolved_on"] or str(dt.date.today()), status_evidence=row["evidence"])
        print(f"  {d['id']} → {row['status']}: {row['evidence']}")
        if row["status"] == "extended" and row["new_deadline"]:
            deadlines.append({**{k: d[k] for k in ("target", "topic", "threat_size", "source_url", "origin")},
                              "id": d["id"] + "x", "announced": d["resolved_on"], "deadline": row["new_deadline"],
                              "said": f"Extended: {d['said']}", "status": "pending", "resolved_on": None})
    dump(P("data", "deadlines.json"), deadlines)
    rel = sum(bool((p["cls"] or {}).get("market_relevant")) for p in posts.values())
    print(f"{len(posts)} posts on file, {rel} market-relevant; {sum(d['status'] == 'pending' for d in deadlines)} deadlines pending")


if __name__ == "__main__":
    main()
