"""Scrapes AP's daily "How major US stock indexes fared" story (syndicated on WTOP) for each
candidate day and each hand-labeled event day → data/headlines.json (cached by date).
WTOP drops AP stories after ~8 months, so older days fall back to the Wayback Machine's copy.
Hand-labeled days with no AP copy fall back to the same-day article linked in events.json (calibration only;
retrospective pages like Wikipedia are skipped so the tagger can't see hindsight).

Obeys robots.txt, 1 request/sec, no logins. Misses are retried weekly.
Fails loudly if it tried never-seen days and got nothing.
Run: python3 scripts/scrape.py
"""
import json, os, sys, time, datetime as dt
import urllib.robotparser
import requests
from urllib.parse import urlsplit
from scrapling.fetchers import Fetcher

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "headlines.json")
UA = "trump-vs-spx-research/1.0 (+https://github.com/vtalla-hq/trump-vs-spx)"
SITE = "https://wtop.com"


def ap_urls(d):
    """Newer stories live under /national/; the /news/ 301 is refused by curl, so request both directly."""
    t = dt.date.fromisoformat(d)
    slug = f"{t:%Y/%m}/how-major-us-stock-indexes-fared-{t:%A}-{t.month}-{t.day}-{t.year}/".lower()
    return [f"{SITE}/news/{slug}", f"{SITE}/national/{slug}"]


def wayback(url):
    snap = requests.get("https://archive.org/wayback/available", params={"url": url}, headers={"User-Agent": UA},
                        timeout=30).json().get("archived_snapshots", {}).get("closest")
    return snap and f"https://web.archive.org/web/{snap['timestamp']}id_/{url}"  # id_ = original page bytes


def get(url, follow=False):
    try:
        page = Fetcher.get(url, headers={"User-Agent": UA}, timeout=30, retries=1, follow_redirects=follow)
        return page if page.status == 200 else None
    except Exception as e:  # curl errors (refused redirects, resets) shouldn't kill the run
        print(f"    {url}: {str(e)[:100]}")


ROBOTS = {}


def allowed(url):
    host = "{0.scheme}://{0.netloc}".format(urlsplit(url))
    if host not in ROBOTS:
        ROBOTS[host] = urllib.robotparser.RobotFileParser(host + "/robots.txt")
        try:
            ROBOTS[host].read()
        except Exception:  # unreachable robots.txt: be conservative
            ROBOTS[host].disallow_all = True
    return ROBOTS[host].can_fetch(UA, url)


def linked_article(d, url):
    if not url or "wikipedia.org" in url or not allowed(url):
        return None
    page = get(url, follow=True)
    paras = [p.get_all_text().strip() for p in page.css("p")] if page else []
    lead = [p for p in paras if len(p) > 80][:5]
    return lead and {"date": d, "source": "linked article", "url": url, "title": page.css("h1::text").get() or "", "text": "\n".join(lead)}


def scrape(d, robots, alt=None):
    urls = [u for u in ap_urls(d) if robots.can_fetch(UA, u)]
    if not urls:
        print(f"  {d}: robots.txt disallows {ap_urls(d)}")
        return None
    url, page = urls[0], None
    for u in urls:
        page = get(u)
        if page:
            url = u
            break
    if page is None:
        try:
            snap = wayback(url)
        except (requests.RequestException, ValueError):
            snap = None
        page = snap and get(snap)
        if page is None:
            row = linked_article(d, alt)
            print(f"  {d}: not on WTOP or the Wayback Machine" + (" → used linked article" if row else ""))
            return row
    paras = [p.get_all_text().strip() for p in page.css("article p")]
    # Keep the narrative lead; drop the "On Tuesday: / The S&P 500 rose X points" boilerplate.
    lead = [p for p in paras if len(p) > 80 and " points, or " not in p][:3]
    if not lead:
        return None
    return {"date": d, "source": "WTOP / AP", "url": url, "title": page.css("h1::text").get(), "text": "\n".join(lead)}


def main():
    load = lambda p: json.load(open(p)) if os.path.exists(p) else []
    cache = {r["date"]: r for r in load(OUT)}
    gold = {e["date"]: e["url"] for e in load(os.path.join(ROOT, "public", "data", "events.json"))}
    latest = load(os.path.join(ROOT, "public", "data", "daily.json"))[-1:]  # latest session: news for watch.py's deadline updates
    dates = sorted({r["date"] for r in load(os.path.join(ROOT, "data", "candidates.json"))} | set(gold) | {r["date"] for r in latest})
    week_ago = str(dt.date.today() - dt.timedelta(days=7))
    todo = [d for d in dates if d not in cache or (cache[d].get("missing") and cache[d]["tried"] < week_ago)]
    new = [d for d in todo if d not in cache]
    robots = urllib.robotparser.RobotFileParser(SITE + "/robots.txt")
    robots.read()
    got = 0
    for d in todo:
        row = scrape(d, robots, gold.get(d))
        got += bool(row)
        cache[d] = row or {"date": d, "missing": True, "tried": str(dt.date.today())}
        time.sleep(1)
    json.dump(sorted(cache.values(), key=lambda r: r["date"]), open(OUT, "w"), ensure_ascii=False, indent=1)
    have = sum(not r.get("missing") for r in cache.values())
    print(f"scraped {got}/{len(todo)} days this run ({len(new)} never tried); {have} of {len(dates)} wanted days on file")
    if new and got == 0:
        sys.exit("scrape returned zero rows: source layout or URL pattern probably changed")


if __name__ == "__main__":
    main()
