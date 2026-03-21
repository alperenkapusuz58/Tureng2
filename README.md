# Tureng-Style Dictionary (MVP)

Bu proje, "en dengeli" yaklasimla baslatildi:
- Backend: Django
- Ucretsiz CMS panel: Django Admin
- Veritabani: Gelistirmede SQLite, uretimde PostgreSQL

## Neden bu yontem?
- **Django Admin ucretsizdir** ve kelime/anlam/ornek cumle CRUD islerini hizlica cozer.
- Sozlukteki **ozel arama kurallarini** (sadece madde basi) kodla net uygulayabiliriz.
- Sonradan reklam, SEO, performans ve mobil API kolay genisletilir.

## Kurulum
```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser
.venv\Scripts\python manage.py runserver
```

## Ekranlar
- `/` : Ana sayfa + canli arama
- `/en-tr/<slug>/` : Ingilizce -> Turkce detay (anlam + ornek cumle)
- `/tr-en/<slug>/` : Turkce -> Ingilizce detay (sadece karsiliklar)
- `/admin/` : CMS panel

## CSV ile toplu veri import
1. Admin panelde `Dictionary > Headwords` sayfasina gir.
2. Sag ustten `CSV ile ice aktar` butonuna tikla.
3. `sample_dictionary_import.csv` dosyasini baz alarak kendi CSV dosyani yukle.
4. Once `Sadece kontrol et (kaydetme)` ile test et, sonra normal import yap.

CSV'de `section` kolonu zorunludur:
- `en_tr` satirlari: `en_lemma`, `translation` zorunlu
- `tr_en` satirlari: `tr_lemma`, `en_lemma` zorunlu

## Veri Modeli
- `Headword` : madde basi (en/tr), okunus, aktiflik
- `Sense` : anlam (kelime turu + ceviri)
- `ExampleSentence` : ornek cumle ve cevirisi (EN->TR akisinda)
- `TrEnLink` : TR madde basini EN madde baslarina baglar

## Yol Haritasi (Tahmini)
1. **MVP Tamamlama (1-2 hafta)**
   - Admin iyilestirmeleri
   - Arama kalitesi (normalization, typo toleransi)
   - Ilk reklam slotlari
2. **V1 Yayina Hazir (2-4 hafta)**
   - SEO ve sayfa hizi
   - Ses dosyalari/TTS entegrasyonu
   - Temel analiz ve loglama
3. **Olcekleme (4-8 hafta)**
   - PostgreSQL tuning
   - Cache (Redis)
   - API + mobil hazirligi

## Kaba Maliyet Araligi (Freelance / Kucuk ekip)
- MVP: ~1500 - 5000 USD
- V1 (reklam + SEO + kalite): ~5000 - 12000 USD
- Icerik hacmi, tasarim kalitesi ve test derinligi maliyeti dogrudan etkiler.
