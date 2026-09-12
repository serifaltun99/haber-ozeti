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
CACHE = os.path.join(ROOT, "cache", "translations.json")
CACHE_MAX = 3000  # kaç çeviri saklansın
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


TR_CHARS = re.compile(r"[ğışçöüĞİŞÇÖÜ]")
TR_WORDS = {
    "ve", "ile", "için", "bir", "bu", "da", "de", "mi", "ne", "en", "çok", "son", "yeni", "oldu",
    "olan", "dedi", "sonra", "karşı", "kadar", "göre", "dair", "arasında", "milli", "takım", "maç",
    "lig", "yılında", "türkiye", "bakan", "başkan", "açıklama", "deprem", "yangın", "sel", "haber",
}


def guess_lang(title, url):
    """Başlığın dili: Türkçe kaynak/karakter/kelime varsa tr, yoksa en."""
    if "hl=tr" in url or ".tr/" in url or url.endswith(".tr"):
        return "tr"
    if TR_CHARS.search(title):
        return "tr"
    words = set(re.findall(r"[a-zçğıöşü]+", title.lower()))
    return "tr" if len(words & TR_WORDS) >= 2 else "en"


def clean_src(s):
    """Kaynak adını kısalt: 'AI | The Verge' -> 'The Verge', 'BBC News - Business' -> 'BBC News'."""
    s = re.sub(r"\s+", " ", s or "").strip().strip('"\u201c\u201d\'')
    s = re.sub(r"^(Feed|RSS)\s*:\s*", "", s, flags=re.I)
    if "|" in s:                      # yayıncı adı genelde sonda
        s = s.split("|")[-1].strip() or s
    for sep in (" - ", " – ", " — ", " :: ", ": "):
        if sep in s:                  # "BBC News - Business" gibi: yayıncı başta
            s = s.split(sep)[0].strip() or s
            break
    if len(s) > 26:                   # kelime sınırında kes
        s = s[:26].rsplit(" ", 1)[0]
    return s


def clean_title(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t[:140]


def fetch_feed(url):
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        f = feedparser.parse(r.content)
        if "news.google.com" in url:
            src = "Google Haber"
        else:
            src = clean_src(f.feed.get("title") or url.split("/")[2])
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
                    s = clean_src(s)
                lang = guess_lang(title, url)
                items.append({"title": title, "link": link, "src": s, "time": t,
                              "lang": lang, "title_tr": title, "title_en": title})
        items.sort(key=lambda x: x["time"], reverse=True)
        c["news"] = items[:MAX_PER_CAT]
        print(f"  {c['key']}: {len(c['news'])}")
    return categories


def salvage(text):
    """Kaçırılmamış tırnak yüzünden bozulan {"12": "..."} JSON'undan çiftleri kurtarır."""
    out = {}
    keys = list(re.finditer(r'"(\d+)"\s*:\s*"', text))
    for i, m in enumerate(keys):
        chunk = text[m.end(): keys[i + 1].start() if i + 1 < len(keys) else len(text)]
        j = chunk.rfind('"')
        if j > 0:
            out[m.group(1)] = chunk[:j].replace('\\"', '"').strip()
    print(f"  kurtarilan: {len(out)}")
    return out


def ask(prompt, max_tokens, etiket, kurtar=False):
    """Tek Claude isteği; JSON gövdesini sözlük olarak döndürür, hata olursa None."""
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
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=180,
        )
        if r.status_code != 200:
            print(f"  ! {etiket} http {r.status_code}: {r.text[:300]}")
            return None
        data = r.json()
        u = data.get("usage", {})
        print(f"  {etiket} tokens: in={u.get('input_tokens')} out={u.get('output_tokens')}")
        text = data["content"][0]["text"]
        text = text[text.find("{"): text.rfind("}") + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError as ex:
            print(f"  ! {etiket} json: {ex}")
            return salvage(text) if kurtar else None
    except Exception as ex:
        print(f"  ! {etiket}: {ex}")
        return None


def summarize(categories):
    """Kategori başına iki dilli özet ve en önemli 3 haber."""
    blocks = []
    for c in categories:
        if not c["news"]:
            continue
        lines = "\n".join(f"{it['id']}. {it['title']}" for it in c["news"])
        blocks.append(f"## {c['key']}\n{lines}")
    if not blocks:
        return
    prompt = (
        "Aşağıda kategori başına bugünün haber başlıkları var. Her kategori için:\n"
        "- ozet_tr: Türkçe, en fazla 2 cümle ve 200 karakter, sadece en önemli gelişmeyi söyle, "
        "başlıkları tekrar etme\n"
        "- ozet_en: aynı özetin İngilizcesi\n"
        "- top: en önemli 3 başlığın numarası\n"
        'Sadece şu JSON\'u döndür, açıklama yazma: '
        '{"kategori_key": {"ozet_tr": "...", "ozet_en": "...", "top": [1,2,3]}}\n\n'
        + "\n\n".join(blocks)
    )
    out = ask(prompt, 3000, "ozet")
    if not out:
        return
    for c in categories:
        d = out.get(c["key"]) or {}
        c["summary_tr"] = d.get("ozet_tr", "")
        c["summary_en"] = d.get("ozet_en", "")
        tops = {n for n in d.get("top", []) if isinstance(n, int)}
        for it in c["news"]:
            if it["id"] in tops:
                it["top"] = True


def cache_load():
    try:
        with open(CACHE, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def cache_save(d):
    if len(d) > CACHE_MAX:  # en eski girdileri at (dict ekleme sırasını korur)
        d = dict(list(d.items())[-CACHE_MAX:])
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def translate(items):
    """Her başlığın diğer dildeki karşılığı: tr -> en, en -> tr. Önce önbellek, kalanı API."""
    if not items:
        return
    cache = cache_load()
    kalan = []
    isabet = 0
    for it in items:
        it["ckey"] = f"{it['lang']}:{norm(it['title'])}"
        t = cache.pop(it["ckey"], None)          # tekrar ekleyince taze sayılır
        if isinstance(t, str) and t.strip():
            it["title_en" if it["lang"] == "tr" else "title_tr"] = t
            cache[it["ckey"]] = t
            isabet += 1
        else:
            kalan.append(it)
    print(f"  önbellek: {isabet} isabet, {len(kalan)} yeni")
    if not kalan:
        cache_save(cache)
        return

    tr = [it for it in kalan if it["lang"] == "tr"]
    en = [it for it in kalan if it["lang"] == "en"]
    parts = []
    if tr:
        parts.append("## Türkçeden İngilizceye çevir\n"
                     + "\n".join(f"{it['id']}. {it['title']}" for it in tr))
    if en:
        parts.append("## İngilizceden Türkçeye çevir\n"
                     + "\n".join(f"{it['id']}. {it['title']}" for it in en))
    prompt = (
        f"Aşağıda numaralı {len(kalan)} haber başlığı var: {len(tr)} tanesi Türkçe bölümünde, "
        f"{len(en)} tanesi İngilizce bölümünde. Her başlığı kendi bölümünün yönüne göre çevir.\n"
        "Haber başlığı üslubunu koru, kısa tut, özel isimleri ve skorları aynen bırak.\n"
        "Çeviri metninde çift tırnak (\") KULLANMA, gerekiyorsa tek tırnak kullan.\n"
        f'Sadece şu JSON\'u döndür, açıklama yazma: {{"1": "çeviri", "2": "çeviri", ...}}\n'
        f"{len(kalan)} numaranın HEPSİ cevapta olmalı, hiçbirini atlama.\n\n"
        + "\n\n".join(parts)
    )
    out = ask(prompt, 8000, "ceviri", kurtar=True)
    if not out:
        cache_save(cache)
        return
    n = 0
    for it in kalan:
        t = out.get(str(it["id"]))
        if isinstance(t, str) and t.strip():
            t = clean_title(t)
            it["title_en" if it["lang"] == "tr" else "title_tr"] = t
            cache[it["ckey"]] = t
            n += 1
    print(f"  çeviri: {n}/{len(kalan)} yeni başlık (toplam {isabet + n}/{len(items)})")
    cache_save(cache)


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
    items = [it for c in cats for it in c["news"]]
    for i, it in enumerate(items, 1):
        it["id"] = i
    if USE_AI:
        print("summarize")
        summarize(cats)
        print("translate")
        translate(items)
    render(cats)
    print("ok -> public/index.html")
