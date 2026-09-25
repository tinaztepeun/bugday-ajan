"""Koordinatör ajan: günün temasını, açısını ve araştırma görevlerini belirler."""
from __future__ import annotations

from .hafiza import Hafiza
from .ortak import ayarlar, claude_json, kaydedici, simdi, tarih_metni

log = kaydedici("koordinator")

SISTEM = """Sen bir tarım emtiası içerik ekibinin koordinatörüsün. Ekip Türkiye ve dünya buğday
piyasası ile un sektörü hakkında her gün LinkedIn'de Türkçe + İngilizce kısa analiz paylaşıyor.

Görevin: günün temasını esas alarak özgün bir paylaşım açısı seçmek ve araştırma ajanlarına
net görevler vermek. Son paylaşımları tekrar etme; aynı rakamı veya aynı haberi yeniden
anlatma. Ancak o gün temadan bağımsız çok önemli bir gelişme olma ihtimaline karşı en az bir
"hızlı" tarama görevi ver.

Kullanılabilir araştırma ajanları: "turkiye", "dunya", "un".
Her görev için "derinlik": "derin" (ana konu, 1 ajan) veya "hizli" (kısa tarama).
Genelde 1 derin + 1-2 hızlı görev yeterlidir. Haftalık özet günlerinde 3 hızlı görev ver.

YALNIZCA şu JSON'u döndür:
{
  "tema": "kısa tema adı",
  "aci": "bugünkü paylaşımın odak sorusu/açısı (1-2 cümle)",
  "gorsel_fikri": "görselde ne gösterilebilir (ör. son 8 haftalık fiyat, ihracat karşılaştırması)",
  "gorevler": [
    {"ajan": "turkiye|dunya|un", "derinlik": "derin|hizli", "sorular": ["...", "..."]}
  ],
  "gerekce": "neden bu açı (1 cümle)"
}"""


def planla(hafiza: Hafiza) -> dict:
    a = ayarlar()
    bugun = simdi()
    tema = a["haftalik_tema"][bugun.weekday()]
    icerik = (
        f"Bugün: {tarih_metni(bugun)}\n"
        f"Günün ana teması: {tema}\n\n"
        f"Son paylaşımlar (tekrar etme):\n{hafiza.ozet_metni()}\n\n"
        f"Ekip notları:\n{hafiza.notlar_metni()}\n\n"
        "Planı hazırla."
    )
    plan, _ = claude_json(SISTEM, icerik, a["modeller"]["koordinator"], max_tokens=2000)

    gecerli = set(a["arastirma_ajanlari"])
    plan["gorevler"] = [g for g in plan.get("gorevler", []) if g.get("ajan") in gecerli]
    if not plan["gorevler"]:
        raise RuntimeError("Koordinatör geçerli görev üretmedi")
    plan.setdefault("tema", tema)
    log.info("Plan: %s | %s", plan["tema"], plan.get("aci"))
    return plan
