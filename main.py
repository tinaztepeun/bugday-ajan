"""Günlük üretim hattı: plan → araştırma → yazım → görsel → denetim (revizyon döngüsü) → arşiv.

Çıktılar: arsiv/YYYY-MM-DD/
  paylasim.json   yayınlanacak içerik ve durum
  gonderi.txt     LinkedIn'e gidecek metnin son hâli
  makale.md       kısa makale (web sitesi / LinkedIn makalesi için)
  gorsel.png      görsel
  arastirma.json  ham bulgular
  denetim.json    denetim raporları

Çıkış kodu: 0 = onaylandı, 2 = yayına uygun bulunmadı.
"""
from __future__ import annotations

import sys

from ajanlar import arastirmaci, denetci, gorsel, koordinator, yazar
from ajanlar.hafiza import Hafiza
from ajanlar.ortak import ARSIV, ayarlar, json_yaz, kaydedici, simdi
from ajanlar.yayinci import ilk_yorum, metni_birlestir

log = kaydedici("hat")


def calistir() -> int:
    a = ayarlar()
    gun = simdi().strftime("%Y-%m-%d")
    klasor = ARSIV / gun
    hafiza = Hafiza()
    son = hafiza.ozet_metni()

    # 1) Koordinatör planlar
    plan = koordinator.planla(hafiza)

    # 2) Araştırma ajanları paralel çalışır
    bulgular = arastirmaci.arastir(plan["gorevler"])
    json_yaz(klasor / "arastirma.json", {"plan": plan, "bulgular": bulgular})
    if not any(b.get("bulgular") for b in bulgular):
        log.error("Araştırmadan kullanılabilir bulgu çıkmadı")
        json_yaz(klasor / "paylasim.json", {"durum": "reddedildi", "neden": "bulgu yok", "plan": plan})
        return 2

    # 3) Yazar ve 4) görsel ajan
    taslak = yazar.yaz(plan, bulgular, son)
    spec = gorsel.tasarla(taslak, bulgular, plan.get("gorsel_fikri", ""))
    png = gorsel.ciz(spec, klasor / "gorsel.png")

    # 5) Denetim + revizyon döngüsü
    raporlar = []
    for tur in range(a["denetim"]["en_fazla_revizyon"] + 1):
        rapor = denetci.denetle(taslak, spec, png, bulgular, son)
        rapor["tur"] = tur + 1
        raporlar.append(rapor)
        json_yaz(klasor / "denetim.json", raporlar)
        if rapor.get("ekip_notu"):
            hafiza.not_ekle(rapor["ekip_notu"])

        if rapor["karar"] in ("onay", "red") or tur == a["denetim"]["en_fazla_revizyon"]:
            break
        log.info("Revizyon turu %d", tur + 1)
        if rapor["yazar_icin"]:
            taslak = yazar.revize_et(taslak, rapor["yazar_icin"], bulgular)
        if rapor["gorsel_icin"] or rapor["yazar_icin"]:
            spec = gorsel.tasarla(taslak, bulgular, plan.get("gorsel_fikri", ""),
                                  geri_bildirim=rapor["gorsel_icin"] or ["Revize edilen metinle uyumu koru"],
                                  onceki=spec)
            png = gorsel.ciz(spec, klasor / "gorsel.png")

    son_rapor = raporlar[-1]
    onayli = son_rapor["karar"] == "onay"
    kaynaklar = arastirmaci.kaynak_listesi(bulgular)
    gonderi = metni_birlestir(taslak)
    if len(gonderi) > a["uzunluk"]["toplam_azami"]:
        log.error("Birleşik gönderi %d karakter, sınır aşıldı", len(gonderi))
        onayli = False

    (klasor / "gonderi.txt").write_text(gonderi, encoding="utf-8")
    (klasor / "makale.md").write_text(taslak.get("makale_md", ""), encoding="utf-8")
    json_yaz(klasor / "paylasim.json", {
        "durum": "onaylandi" if onayli else "reddedildi",
        "tarih": gun,
        "plan": plan,
        "taslak": taslak,
        "gorsel": spec,
        "kaynaklar": kaynaklar,
        "ilk_yorum": ilk_yorum(kaynaklar),
        "puan": son_rapor.get("puan"),
    })

    # 6) Ortak hafızayı güncelle
    if onayli:
        hafiza.paylasim_ekle(gun, plan["tema"], taslak.get("baslik", ""), taslak.get("ozet", ""),
                             [r.get("deger", "") for r in taslak.get("anahtar_rakamlar", [])])
    hafiza.kaydet()

    if onayli:
        log.info("ONAYLANDI (puan %s): %s", son_rapor.get("puan"), taslak.get("baslik"))
        return 0
    log.error("YAYINA UYGUN DEĞİL: %s", son_rapor.get("gerekce"))
    return 2


if __name__ == "__main__":
    sys.exit(calistir())
