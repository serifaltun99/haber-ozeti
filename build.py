import os, re, json, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import feedparser, requests, yaml
from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.abspath(__file__))
WINDOW_HOURS = int(os.getenv("WINDOW_HOURS", "24"))
MAX_PER_CAT = int(os.getenv("MAX_PER_CAT", "12"))
USE_AI = os.getenv("USE_AI", "1") == "1" and bool(os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")
TZ = dt.timezone(dt.timedelta(hours=3))  # Türkiye
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
}


def entry_time(e):
    for k in ("published_parsed", "updated_parsed"):
        if e.get(k):
            return dt.datetime(*e[k][:6], tzinfo=dt.timezone.utc)
    return None


def norm(title):
    return re.sub(r"[^a-z0-9çğıöşü]", "", title.lower())[:70]


def clean_title(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t[:140]


def fetch_feed(url):
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        f = feedparser.parse(r.content)
        src = (f.feed.get("title") or url.split("/")[2]).replace(" - Google News", "").strip()[:40]
        return url, src, f.entries
    except Exception as ex:
        print(f"  ! {url}: {ex}")
        return url, None, []


def collect(categories):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=WINDOW_HOURS)
    urls = [u for c in categories for u in c["feeds"]]
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = {url: (src, entries) for url, src, entries in ex.map(fetch_feed, urls)}

    seen = set()
    for c in categories:
        items = []
        for url in c["feeds"]:
            src, entries = results[url]
            for e in entries:
                t = entry_time(e)
                if not t or t < cutoff:
                    continue
                title = clean_title(e.get("title"))
                link = e.get("link", "")
                key = norm(title)
                if not title or not link or key in seen:
                    continue
                seen.add(key)
                # Google News başlıkları " - Kaynak" ile biter; kaynağı oradan al
                s = src
                if "news.google.com" in url and " - " in title:
                    title, s = title.rsplit(" - ", 1)
                items.append({"title": title, "link": link, "src": s, "time": t})
        items.sort(key=lambda x: x["time"], reverse=True)
        c["news"] = items[:MAX_PER_CAT]
        print(f"  {c['key']}: {len(c['news'])}")
    return categories


def summarize(categories):
    """Tek istek. Sadece başlık gönderilir, JSON döner."""
    blocks = []
    for c in categories:
        if not c["news"]:
            continue
        lines = "\n".join(f"{i+1}. {it['title']}" for i, it in enumerate(c["news"]))
        blocks.append(f"## {c['key']}\n{lines}")
    if not blocks:
        return
    prompt = (
        "Aşağıda kategori başına bugünün haber başlıkları var. Her kategori için:\n"
        "- ozet: Türkçe, en fazla 2 cümle ve 200 karakter, sadece en önemli gelişmeyi söyle, "
        "başlıkları tekrar etme\n"
        "- top: en önemli 3 başlığın numarası\n"
        'Sadece şu JSON\'u döndür, açıklama yazma: {"kategori_key": {"ozet": "...", "top": [1,2,3]}}\n\n'
        + "\n\n".join(blocks)
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 1800,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        if r.status_code != 200:
            print(f"  ! ai http {r.status_code}: {r.text[:300]}")
            return
        data = r.json()
        u = data.get("usage", {})
        print(f"  ai tokens: in={u.get('input_tokens')} out={u.get('output_tokens')}")
        text = data["content"][0]["text"]
        text = text[text.find("{"): text.rfind("}") + 1]
        out = json.loads(text)
    except Exception as ex:
        print(f"  ! ai: {ex}")
        return
    for c in categories:
        d = out.get(c["key"]) or {}
        c["summary"] = d.get("ozet", "")
        for n in d.get("top", []):
            if isinstance(n, int) and 1 <= n <= len(c["news"]):
                c["news"][n - 1]["top"] = True


def render(categories):
    env = Environment(loader=FileSystemLoader(ROOT), autoescape=True)
    env.filters["hm"] = lambda t: t.astimezone(TZ).strftime("%H:%M")
    env.filters["dm"] = lambda t: t.astimezone(TZ).strftime("%d.%m")
    html = env.get_template("template.html").render(
        categories=categories,
        generated=dt.datetime.now(TZ).strftime("%d.%m.%Y %H:%M"),
        window=WINDOW_HOURS,
        ai=USE_AI,
    )
    os.makedirs(os.path.join(ROOT, "public"), exist_ok=True)
    with open(os.path.join(ROOT, "public", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    with open(os.path.join(ROOT, "sources.yaml"), encoding="utf-8") as f:
        cats = yaml.safe_load(f)["categories"]
    print("fetch")
    collect(cats)
    if USE_AI:
        print("summarize")
        summarize(cats)
    render(cats)
    print("ok -> public/index.html")
