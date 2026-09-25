"""Yazar ajan: LinkedIn gönderisi (TR + EN) ve arşiv için kısa makale yazar."""
from __future__ import annotations

import json

from .ortak import ayarlar, claude_json, kaydedici, tarih_metni

log = kaydedici("yazar")

SISTEM_SABLONU = """Sen buğday ve un piyasaları üzerine yazan deneyimli bir sektör analisti ve içerik yazarısın.
Araştırma ajanlarının topladığı bulgulardan LinkedIn için kısa, değerli, güvenilir bir analiz yazarsın.

Stil rehberi:
{stil}

Kurallar:
- YALNIZCA bulgularda geçen rakamları kullan; rakamı değiştirme, yuvarlarken anlamı bozma.
- Her rakamın tarihini/dönemini belirt.
- Türkçe metin en fazla {tr_azami} karakter, İngilizce metin en fazla {en_azami} karakter.
- Metinlere hashtag ve link koyma; hashtagler ayrı alanda, kaynaklar ayrıca yayınlanır.
- "makale_md" alanı: arşiv ve web sitesi için 350-550 kelimelik Türkçe kısa makale (markdown,
  ara başlıklı, sonunda "Kaynaklar" listesi URL'lerle).
- "anahtar_rakamlar": metinde kullandığın her rakam için bir satır (değer + açıklama + kaynak URL).
  Denetçi bunları tek tek kontrol edecek.

YALNIZCA şu JSON'u döndür:
{{
  "baslik": "kısa başlık (TR)",
  "baslik_en": "short title (EN)",
  "metin_tr": "...",
  "metin_en": "...",
  "hashtagler": ["#Buğday", "..."],
  "makale_md": "...",
  "anahtar_rakamlar": [{{"deger": "...", "aciklama": "...", "kaynak_url": "https://..."}}],
  "ozet": "hafıza için tek cümlelik özet"
}}"""


def _sistem() -> str:
    a = ayarlar()
    return SISTEM_SABLONU.format(stil=a["stil"], tr_azami=a["uzunluk"]["tr_azami"], en_azami=a["uzunluk"]["en_azami"])


def yaz(plan: dict, bulgular: list[dict], son_paylasimlar: str) -> dict:
    icerik = (
        f"Bugün: {tarih_metni()}\n"
        f"Tema: {plan['tema']}\nAçı: {plan.get('aci')}\n\n"
        f"Son paylaşımlar (tekrar etme):\n{son_paylasimlar}\n\n"
        f"Araştırma bulguları (JSON):\n{json.dumps(bulgular, ensure_ascii=False)}"
    )
    taslak, _ = claude_json(_sistem(), icerik, ayarlar()["modeller"]["yazar"], max_tokens=8000)
    log.info("Taslak hazır: %s", taslak.get("baslik"))
    return taslak


def revize_et(taslak: dict, geri_bildirim: list[str], bulgular: list[dict]) -> dict:
    icerik = (
        "Denetçi aşağıdaki düzeltmeleri istedi. Hepsini uygula, geri kalanını koru ve aynı JSON "
        "yapısında tam metni döndür.\n\n"
        f"Düzeltmeler:\n" + "\n".join(f"- {g}" for g in geri_bildirim) + "\n\n"
        f"Mevcut taslak:\n{json.dumps(taslak, ensure_ascii=False)}\n\n"
        f"Araştırma bulguları:\n{json.dumps(bulgular, ensure_ascii=False)}"
    )
    yeni, _ = claude_json(_sistem(), icerik, ayarlar()["modeller"]["yazar"], max_tokens=8000)
    log.info("Taslak revize edildi")
    return yeni
