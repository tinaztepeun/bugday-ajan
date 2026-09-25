# Buğday & Un İçerik Ajanları

Türkiye buğday piyasası, dünya buğday piyasası ve un sektörü hakkında her iş günü araştırma yapan, Türkçe + İngilizce LinkedIn paylaşımı ve görsel hazırlayan, bunları denetleyip Metricool üzerinden yayınlayan çok ajanlı sistem.

## Nasıl çalışır

Her iş günü saat 06:00'da (Türkiye) GitHub Actions sistemi başlatır:

1. **Koordinatör ajan** günün temasına (`config.yaml` → `haftalik_tema`) ve ortak hafızadaki son paylaşımlara bakarak özgün bir açı seçer, araştırma görevlerini dağıtır.
2. **Araştırma ajanları** (Türkiye / Dünya / Un) paralel olarak web araması yapar; her rakamı kaynağıyla birlikte kaydeder.
3. **Yazar ajan** bulgulardan Türkçe ve İngilizce LinkedIn metni ile 350-550 kelimelik kısa makale yazar.
4. **Görsel ajan** grafiğin ne göstereceğine karar verir (çizgi, çubuk veya bilgi kartı); çizimi program yapar, böylece görseldeki her sayı araştırma verisinden gelir.
5. **Denetçi ajan** görseli de görerek her rakamı kaynağıyla karşılaştırır, yatırım tavsiyesi, dil, tutarlılık ve tekrar kontrolü yapar. Sorun bulursa işi yazara/görsel ajana geri gönderir (en fazla 2 tur). Ayrıca kural tabanlı kontroller (uzunluk sınırları, grafikte veride olmayan değer vb.) aşılmadan onay verilemez.
6. **Yayıncı ajan** onaylanan içeriği Metricool ile LinkedIn'e 09:30'a planlar. Kaynak linkleri ilk yoruma yazılır.

Ajanlar `data/hafiza.json` üzerinden ortak hafıza paylaşır: geçmiş paylaşımlar (tekrarı önlemek için) ve denetçinin bıraktığı kalıcı "ekip notları" sonraki günlerin tüm ajanlarına aktarılır.

Denetimi geçemeyen içerik **yayınlanmaz**; taslak arşivde kalır ve depoda otomatik bir GitHub Issue açılır (GitHub size e-posta bildirimi gönderir).

## Kurulum (yaklaşık 20 dakika)

### 1. Depoyu oluşturun
GitHub'da yeni bir depo açıp bu klasörün içeriğini yükleyin.

Görsel, Metricool'a herkese açık bir adres üzerinden verilir. En kolay yol deponun **public** olmasıdır (gizli anahtarlar Secrets'ta durduğu için kodun açık olması risk oluşturmaz; arşivdeki içerik zaten LinkedIn'de yayınlanıyor). Depoyu gizli tutmak isterseniz görselleri başka bir herkese açık alana koyup adres kökünü `Settings → Secrets and variables → Actions → Variables` altında `MEDIA_BASE_URL` olarak tanımlayın.

### 2. Yazma iznini açın
`Settings → Actions → General → Workflow permissions` → **Read and write permissions** seçin.

### 3. Gizli anahtarları ekleyin
`Settings → Secrets and variables → Actions → New repository secret`:

| Ad | Nereden alınır |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `METRICOOL_USER_TOKEN` | Metricool → Hesap ayarları → API bölümü |
| `METRICOOL_USER_ID` | Aynı API bölümünde gösterilir |
| `METRICOOL_BLOG_ID` | LinkedIn hesabınızın bağlı olduğu markanın ID'si (Metricool panelinde adres çubuğundaki `blogId=` değeri) |

Metricool API erişimi her pakette bulunmayabilir; hesabınızda API bölümü görünmüyorsa paketinizi kontrol edin.

### 4. Markanızı ayarlayın
`config.yaml` içinde en azından `marka.ad` alanını değiştirin. Renkler, yayın saati, tema döngüsü, stil rehberi ve modeller de buradan ayarlanır.

### 5. Deneme çalıştırması
`Actions → Günlük buğday paylaşımı → Run workflow` (deneme kutusu işaretli). İçerik üretilir, `arsiv/<tarih>/` klasörüne yazılır ama LinkedIn'e gönderilmez. `gonderi.txt`, `gorsel.png` ve `denetim.json` dosyalarını inceleyin.

### 6. Yayına alma
Birkaç deneme sonucu içinize sinince hiçbir şey yapmanıza gerek yok: zamanlanmış çalışma deneme modunda değildir ve her iş günü otomatik yayınlar.

**İlk hafta için öneri:** `config.yaml` → `yayin.mod: "taslak"` yapın. İçerikler Metricool'da taslak olarak bekler, siz tek tıkla yayınlarsınız. Kaliteden emin olunca `"otomatik"`e geçin. Otomatik modda da 06:00 ile 09:30 arasında Metricool'dan gönderiyi düzenleme ya da iptal etme penceresi vardır.

## Arşiv

Her gün `arsiv/YYYY-MM-DD/` altında şunlar saklanır:

- `gonderi.txt` — LinkedIn'e giden son metin
- `gorsel.png` — 1200×1500 görsel
- `makale.md` — kısa makale (LinkedIn Makaleleri API ile yayınlanamadığı için web sitenizde ya da elle LinkedIn makalesi olarak kullanabilirsiniz)
- `arastirma.json` — plan ve tüm kaynaklı bulgular
- `denetim.json` — her denetim turunun raporu
- `paylasim.json`, `yayin.json` — durum ve Metricool yanıtı

## Özelleştirme

- **Hafta sonu da paylaşım:** `.github/workflows/gunluk.yml` içinde `cron: "0 3 * * 1-5"` → `"0 3 * * *"`.
- **Çalışma saati:** cron UTC'dir; Türkiye saati = UTC+3.
- **Maliyet/kalite dengesi:** `config.yaml` → `modeller` ve `arastirma` altındaki arama limitleri.
- **Yeni araştırma alanı** (ör. arpa, mısır): `arastirma_ajanlari` altına yeni bir anahtar ekleyin ve `ajanlar/koordinator.py` içindeki ajan listesine adını yazın.

## Sorun giderme

- **Görsel gönderide görünmüyor:** Depo public mi, `arsiv/<tarih>/gorsel.png` adresi tarayıcıda açılıyor mu kontrol edin. Metricool görseli `actions/normalize/image/url` uç noktasıyla kendi sunucusuna alır; `yayin.json` içindeki yanıtı inceleyin.
- **Metricool 401/403:** Token, userId ve blogId değerlerini kontrol edin.
- **Her gün "yayına uygun değil":** `denetim.json` içindeki `gerekce` ve `kritik_hatalar` alanlarına bakın. Genelde güncel veri bulunamadığında olur; `config.yaml` → `arastirma.derin_arama_limiti` değerini artırmak yardımcı olur.

## Önemli not

İçerikler yapay zekâ tarafından üretilir. Denetim katmanları hatayı büyük ölçüde azaltsa da piyasa verisinde tek bir yanlış rakam itibar kaybına yol açabilir. Arşivi düzenli aralıklarla gözden geçirmeniz önerilir.
