"""Yayın aşaması. main.py'den ve arşivin depoya gönderilmesinden SONRA çalışır
(görselin herkese açık URL'si ancak o zaman erişilebilir olur)."""
from __future__ import annotations

import sys

from ajanlar.ortak import ARSIV, ayarlar, json_oku, json_yaz, kaydedici, simdi
from ajanlar.yayinci import Metricool, metni_birlestir, varsayilan_medya_koku, yayin_zamani

log = kaydedici("yayinla")


def calistir() -> int:
    gun = simdi().strftime("%Y-%m-%d")
    klasor = ARSIV / gun
    paylasim = json_oku(klasor / "paylasim.json")
    if not paylasim or paylasim.get("durum") != "onaylandi":
        log.error("Bugün için onaylı paylaşım yok, yayın yapılmadı")
        return 2
    if json_oku(klasor / "yayin.json"):
        log.info("Bugünün paylaşımı zaten planlanmış, tekrar gönderilmedi")
        return 0

    a = ayarlar()
    kok = varsayilan_medya_koku()
    gorsel_url = f"{kok}/arsiv/{gun}/gorsel.png" if kok else None
    zaman = yayin_zamani()
    yanit = Metricool().planla(
        metin=metni_birlestir(paylasim["taslak"]),
        gorsel_url=gorsel_url,
        zaman=zaman,
        taslak_mi=a["yayin"]["mod"] == "taslak",
        ilk_yorum_metni=paylasim["ilk_yorum"] if a["yayin"].get("kaynaklari_ilk_yoruma_yaz") else "",
    )
    json_yaz(klasor / "yayin.json", {"planlanan_zaman": zaman.isoformat(), "mod": a["yayin"]["mod"],
                                     "gorsel_url": gorsel_url, "metricool_yaniti": yanit})
    return 0


if __name__ == "__main__":
    sys.exit(calistir())
