# haber-ozeti

RSS kaynaklarından son 24 saatin haberlerini toplar, Claude Haiku ile kategori başına
kısa bir Türkçe özet yazdırır, tek sayfalık statik HTML üretir. 6 saatte bir GitHub Actions
üzerinde çalışır, GitHub Pages'e yüklenir.

Adres: https://serifaltun99.github.io/haber-ozeti/

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

1. Repo public olmalı (GitHub Pages ücretsiz planda public repo ister).
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Secrets and variables → Actions: `ANTHROPIC_API_KEY`.
4. Actions sekmesinden `build` → Run workflow.

Not: Cloudflare Pages ile de denendi, ancak `*.pages.dev` Türkiye'den TLS seviyesinde
engellendiği için vazgeçildi. Kendi alan adını bağlarsan Cloudflare tekrar seçenek olur.

## Ayarlar (ortam değişkeni)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `WINDOW_HOURS` | 24 | Kaç saat geriye bakılsın |
| `MAX_PER_CAT` | 12 | Kategori başına haber sayısı |
| `USE_AI` | 1 | 0 = özet yok |
| `AI_MODEL` | claude-haiku-4-5-20251001 | Model |
