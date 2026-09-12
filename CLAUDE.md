# haber-ozeti — Claude Code için proje bağlamı

Kişisel haber özet sitesi. Tek kullanıcı (Şerif), Türkçe arayüz, public'e açılmayacak.

## Mimari
- `build.py`: `sources.yaml`'daki RSS akışlarını paralel çeker (son 24 saat, kategori başına 12 haber,
  başlık bazlı tekilleştirme), tek bir Claude isteğiyle kategori başına 2 cümle Türkçe özet + en önemli 3
  haberi seçtirir, `template.html` (Jinja2) ile `public/index.html` üretir.
- `.github/workflows/build.yml`: 6 saatte bir (UTC 0/6/12/18) çalışır, `public/`'i GitHub Pages'e
  yükler (`upload-pages-artifact` + `deploy-pages`). Secret: `ANTHROPIC_API_KEY`.
- Repo public (GitHub Pages ücretsiz planı gerektiriyor). `public/` gitignore'da.

## Kararlar
- Token maliyeti öncelikli: API'ye yalnızca başlık gönderilir, tek istek, JSON çıktı, `max_tokens=1800`,
  model `claude-haiku-4-5-20251001`. `USE_AI=0` ile API tamamen kapatılabilir.
- Arayüz haber sitesi görünümünde (BBC benzeri): siyah üst bant + kırmızı vurgu, yapışkan kategori
  şeridi (alt çizgili aktif sekme), "Öne çıkan" haberler kart ızgarasında, gerisi liste. Koyu tema
  `prefers-color-scheme` ile. Dış font/CSS/JS bağımlılığı YOK, her şey template.html içinde.
- Kategori seçimi `localStorage`'da tutulur. URL'e `#kategori` YAZILMAZ: tarayıcı o bölüme atlayıp
  sayfayı ~140px kaydırıyor ve üst bant görünmüyordu. Gelen `#kategori` linki okunur, sonra
  `load`'da `scrollTo(0,0)` ile üste dönülür.
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

## Canlı kurulum (2026-09-12 itibarıyla tamam)
- Repo: https://github.com/serifaltun99/haber-ozeti (public)
- Adres: https://serifaltun99.github.io/haber-ozeti/
- Cloudflare Pages DENENDİ VE BIRAKILDI: `*.pages.dev` Türkiye'den TLS/SNI seviyesinde engelli
  (DNS küresel olarak çözülüyor, bağlantı kapatılıyor; mobil veride de aynı). DNS değiştirmek
  çözmüyor. Kendi alan adı alınırsa Cloudflare tekrar kullanılabilir.
- CI notu: Substack akışlarının bir kısmı (importai, garymarcus, thezvi) GitHub runner IP'lerinden
  403 veriyor; tarayıcı UA'sı çözmüyor. Substack dışı bloglar tercih edilmeli.

## Açık işler
- "Öne çıkan isimler" listesini Şerif'in takip etmek istediği kişilerle doldur (Bluesky:
  `https://bsky.app/profile/HANDLE/rss`). Şu an geçici liste: Mollick, Willison, ACX, Karpathy,
  Altman, Ben Evans, Marginal Revolution, LessWrong.
- Cloudflare Access ile kilitleme DÜŞÜNÜLDÜ, YAPILMAYACAK: sayfada gizli bilgi yok, sadece
  herkese açık haber başlıkları. Adres noindex, arama motorlarına düşmüyor.

## Çalışma tarzı
Türkçe yanıt, kısa ve doğrudan, minimal hedefli değişiklik, Windows cmd uyumlu komutlar.
