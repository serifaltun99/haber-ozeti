# haber-ozeti

RSS kaynaklarından son 24 saatin haberlerini toplar, Claude Haiku ile kategori başına
kısa bir Türkçe özet yazdırır, tek sayfalık statik HTML üretir. 6 saatte bir GitHub Actions
üzerinde çalışır, Cloudflare Pages'e yüklenir.

## Token maliyeti

- Sadece başlıklar gönderilir (makale gövdesi yok), kategori başına en fazla 12 başlık.
- Tek istek, JSON çıktı, `max_tokens=1800`. Çalışma başına ~2.800 giriş + ~1.000 çıkış token.
- Haiku 4.5 ile günde 4 çalışma ≈ 0,03 $ / gün (~1 $ / ay).
- `USE_AI=0` ile API tamamen kapatılır; sayfa özetsiz üretilir.

## Lokal çalıştırma (Windows cmd)

    pip install -r requirements.txt
    set ANTHROPIC_API_KEY=sk-ant-...
    python build.py
    start public\index.html

## Kurulum (bir kere)

1. Repo'yu GitHub'a private olarak at.
2. Cloudflare Dashboard → Workers & Pages → Create → Pages → **Direct Upload**,
   proje adı `haber-ozeti` (workflow'daki `--project-name` ile aynı olmalı).
3. Cloudflare → My Profile → API Tokens → Create Token → şablon **Edit Cloudflare Workers**
   (Pages yazma yetkisi içerir). Account ID'yi Pages sayfasının sağ tarafından al.
4. GitHub repo → Settings → Secrets and variables → Actions:
   `ANTHROPIC_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
5. Actions sekmesinden `build` → Run workflow. Adres: `https://haber-ozeti.pages.dev`

Sayfayı kilitlemek istersen: Cloudflare → Zero Trust → Access → Applications → Add,
domain `haber-ozeti.pages.dev`, policy: e-posta OTP. Ücretsiz.

## Ayarlar (ortam değişkeni)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `WINDOW_HOURS` | 24 | Kaç saat geriye bakılsın |
| `MAX_PER_CAT` | 12 | Kategori başına haber sayısı |
| `USE_AI` | 1 | 0 = özet yok |
| `AI_MODEL` | claude-haiku-4-5-20251001 | Model |
