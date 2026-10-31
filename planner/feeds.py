"""Free NBA news feeds (RSS and Atom), matched to the players you're tracking.

ESPN's own player news is fetched elsewhere (cards.news). This adds other outlets so the Injury
Watch verdicts and the injury alerts can react to a report wherever it shows up first.

Matching is by full name only ("Jalen Williams", never just "Williams"), so a story about a
teammate with the same surname isn't counted. Each matched story is tagged:
  back     the story points to a return (cleared, upgraded, expected to play...)
  setback  the story points the other way (setback, surgery, ruled out, indefinitely...)
  None     neither, so it's shown but doesn't change any advice

Keyword tagging is a hint, not a reading of the article: always open the link before acting.

Feeds come from the NEWS_FEEDS variable as comma-separated "Name|url" pairs (or bare urls), or
the defaults below. Set NEWS_FEEDS to "none" to turn this off. A feed that fails is skipped.
"""
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

DEFAULT_FEEDS = (
    ("RotoWire", "https://www.rotowire.com/rss/news.php?sport=NBA"),
    ("CBS Sports", "https://www.cbssports.com/rss/headlines/nba/"),
    ("Yahoo Sports", "https://sports.yahoo.com/nba/rss.xml"),
    ("ESPN", "https://www.espn.com/espn/rss/nba/news"),
    ("Hoops Rumors", "https://www.hoopsrumors.com/feed"),
)
MAX_AGE = timedelta(days=4)  # older stories are ignored

# Clear bad news: always wins, so "not expected to play" never counts as "expected to play".
SETBACK = ("setback", "ruled out", "unavailable", "not available", "won't play", "will not play",
           "not expected to play", "won't return", "will not return", "remains out", "remain out",
           "indefinitely", "season-ending", "out for the season", "rest of the season",
           "remainder of the season", "no timetable", "no return date", "shut down", "downgraded",
           "re-aggravat", "aggravated", "will miss", "more time", "not close")
# Injury words that also appear in recaps ("Williams, who had ankle surgery, was cleared..."):
# they only count as bad news when nothing in the story points to a return.
INJURY = ("surgery", "torn", "tore", "fracture", "suffered a", "sprain", "strain")
BACK = ("cleared", "upgraded", "expected to play", "will play", "will return", "set to return",
        "make his return", "makes his return", "made his return", "making his return",
        "nearing a return", "nearing return", "close to returning", "targeting", "full practice",
        "full-contact", "full contact", "practiced", "practicing", "probable", "available",
        "return to the lineup", "back in the lineup", "minutes restriction", "ramping up", "ramp-up",
        "activated", "g league")  # a G League rehab stint usually comes right before a return
SUFFIX = re.compile(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", re.I)


def parse_config(text):
    """'RotoWire|https://..., https://...' -> [(name, url)]; '' -> defaults; 'none' -> []."""
    text = (text or "").strip()
    if not text:
        return list(DEFAULT_FEEDS)
    if text.lower() in ("none", "off", "0"):
        return []
    out = []
    for part in (p.strip() for p in text.split(",") if p.strip()):
        name, sep, url = part.partition("|")
        if not sep:
            name, url = re.sub(r"^https?://(www\.)?", "", part).split("/")[0], part
        out.append((name.strip(), url.strip()))
    return out


def _text(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return " ".join(s.split())


def _when(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)  # RSS: 'Sat, 31 Oct 2026 18:04:00 GMT'
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))  # Atom: ISO 8601
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_feed(xml_bytes, source):
    """Items from one RSS or Atom document: source, headline, story, link, published (ISO)."""
    root = ET.fromstring(xml_bytes)
    items = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            k = _local(c.tag)
            if k == "link" and c.get("href"):
                f.setdefault("link", c.get("href"))
            elif k in ("title", "link", "description", "summary", "content", "encoded", "pubDate",
                       "published", "updated", "date") and (c.text or "").strip():
                f.setdefault(k, c.text.strip())
        when = _when(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date"))
        title = _text(f.get("title"))
        if not title:
            continue
        story = _text(f.get("description") or f.get("summary") or f.get("encoded") or f.get("content"))
        if len(story) > 320:
            story = story[:317].rsplit(" ", 1)[0] + "…"
        items.append({"source": source, "headline": title, "story": story, "link": f.get("link", ""),
                      "published": when.isoformat() if when else ""})
    return items


def fetch_all(feeds, timeout=15, now=None):
    """Recent items from every feed, newest first, plus a note per feed that failed."""
    now = now or datetime.now(timezone.utc)
    items, failed = [], []
    for name, url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fantasy-planner)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                got = parse_feed(r.read(), name)
        except Exception as exc:  # one dead feed shouldn't stop the rest
            failed.append(f"{name} ({exc.__class__.__name__})")
            continue
        for it in got:
            when = _when(it["published"])
            if when is None or now - when <= MAX_AGE:
                items.append(it)
    if failed:
        print(f"News feeds skipped: {', '.join(failed)}")
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        key = it["link"] or (it["source"], it["headline"])
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _name_pattern(full_name):
    base = SUFFIX.sub("", full_name.strip())
    words = [re.escape(w) for w in base.split()]
    return re.compile(r"(?<![\w])" + r"[\s.]+".join(words) + r"(?![\w])", re.I)


def mentions(items, full_name):
    """Items that name this player in the headline or story."""
    pat = _name_pattern(full_name)
    return [it for it in items if pat.search(it["headline"]) or pat.search(it["story"])]


def signal(text):
    t = (text or "").lower()
    if any(k in t for k in SETBACK):
        return "setback"
    if any(k in t for k in BACK):
        return "back"
    return "setback" if any(re.search(rf"\b{re.escape(k)}", t) for k in INJURY) else None


def _about(it, full_name):
    """The part of a story about this player: his sentence(s), so a teammate's news isn't counted."""
    pat = _name_pattern(full_name)
    last = SUFFIX.sub("", full_name.strip()).split()[-1]
    text = f"{it['headline']}. {it['story']}"
    sentences = re.split(r"(?<=[.!?])\s+", text)
    keep = [s for s in sentences if pat.search(s) or re.search(rf"\b{re.escape(last)}\b|\bhe\b|\bhis\b", s, re.I)]
    return " ".join(keep) or text


def for_player(items, full_name, limit=3):
    """Matched items for one player, tagged, in the same shape as ESPN news on the Injuries tab."""
    out = []
    for it in mentions(items, full_name)[:limit]:
        out.append({**it, "published": it["published"][:10], "signal": signal(_about(it, full_name))})
    return out
