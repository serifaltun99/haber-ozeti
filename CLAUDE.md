# haber-ozeti — Claude Code için proje bağlamı

Kişisel haber özet sitesi. Tek kullanıcı (Şerif), Türkçe arayüz, public'e açılmayacak.

## Mimari
- `build.py`: `sources.yaml`'daki RSS akışlarını paralel çeker (son 24 saat, kategori başına 12 haber,
  başlık bazlı tekilleştirme), tek bir Claude isteğiyle kategori başına 2 cümle Türkçe özet + en önemli 3
  haberi seçtirir, `template.html` (Jinja2) ile `public/index.html` üretir.
- `.github/workflows/build.yml`: 6 saatte bir (UTC 0/6/12/18) çalışır, `public/`'i Cloudflare Pages'e
  `wrangler pages deploy` ile yükler. Proje adı: `haber-ozeti`. Secrets: `ANTHROPIC_API_KEY`,
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.
- Repo private. `public/` gitignore'da (deploy edilir, commit edilmez).

## Kararlar
- Token maliyeti öncelikli: API'ye yalnızca başlık gönderilir, tek istek, JSON çıktı, `max_tokens=1800`,
  model `claude-haiku-4-5-20251001`. `USE_AI=0` ile API tamamen kapatılabilir.
- Arayüz sade olacak: üstte kategori butonları, tek kategori görünür, özet kutusu, ★ önemli haber.
  Dış font/CSS/JS bağımlılığı yok. Karmaşık tasarım istenmiyor.
- Federasyon siteleri RSS vermediği için voleybol ve Türkiye takımları Google News RSS ile:
  `https://news.google.com/rss/search?q=ARAMA&hl=tr&gl=TR&ceid=TR:tr`
- Jinja'da `c.items` dict metoduyla çakıştığı için haber listesi `c.news` anahtarında.

## Kategoriler (sources.yaml sırası)
ai, ekonomi, afet, dunya, teknoloji, yorum (bilim insanları/öne çıkan isimlerin blog-Substack akışları),
f1, ligler, turkiye, voleybol

## Lokal çalıştırma (Windows cmd)
    pip install -r requirements.txt
    set ANTHROPIC_API_KEY=sk-ant-...
    python build.py
    start public\index.html
Logda `!` ile başlayan satır = erişilemeyen kaynak; sources.yaml'dan çıkar.

## Açık işler
- Gerçek veriyle ilk çalıştırma; kırık RSS kaynaklarını ayıkla.
- "Öne çıkan isimler" listesini Şerif'in takip etmek istediği kişilerle doldur (Bluesky: `https://bsky.app/profile/HANDLE/rss`).
- Cloudflare Pages projesi + secret'lar + ilk push (README'de adımlar).
- İsteğe bağlı: Cloudflare Access ile sayfayı e-posta OTP arkasına al.

## Çalışma tarzı
Türkçe yanıt, kısa ve doğrudan, minimal hedefli değişiklik, Windows cmd uyumlu komutlar.
