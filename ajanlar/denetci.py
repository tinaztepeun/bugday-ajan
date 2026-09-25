"""Denetçi ajan: yayından önce metni ve görseli denetler.

İki katman:
1) Kural tabanlı kontroller (uzunluk, grafik değerlerinin veride bulunması, zorunlu alanlar)
2) Claude ile editoryal ve olgusal denetim (görseli de görerek)
"""
from __future__ import annotations

import json
from pathlib import Path

from .gorsel import seri_dogrula
from .ortak import ayarlar, claude_json, gorsel_blogu, kaydedici, tarih_metni

log = kaydedici("denetci")

SISTEM_SABLONU = """Sen kıdemli bir editör ve emtia piyasası doğrulama uzmanısın. Bir LinkedIn paylaşımını
yayından önce son kez denetliyorsun. Şirketin itibarı senin titizliğine bağlı.

Kontrol listesi:
1. Olgusal doğruluk: metindeki ve görseldeki HER rakam araştırma bulgularında aynı değer,
   birim ve tarihle geçiyor mu? Kaynaksız rakam = kritik hata.
2. Güncellik: veriler bugünün ({tarih}) bağlamında güncel mi, eski veri "güncel" gibi mi sunulmuş?
3. Yatırım tavsiyesi: al/sat önerisi, kesin fiyat tahmini, "kaçırmayın" tarzı ifade var mı? Varsa kritik.
4. TR ve EN metinler aynı olguları anlatıyor mu, çelişki var mı?
5. Dil: yazım, dilbilgisi, akış, profesyonel ton. Stil rehberine uyum:
{stil}
6. Görsel: okunaklı mı, başlık ve değerler metinle tutarlı mı, taşan/üst üste binen yazı var mı,
   kaynak satırı var mı?
7. Tekrar: son paylaşımlarla aynı içerik mi?

Karar:
- "onay": yayınlanabilir (puan >= {asgari_puan}, kritik hata yok)
- "revize": düzeltilebilir sorunlar var — yazar ve/veya görsel için somut, uygulanabilir talimat yaz
- "red": temel sorun (ör. güvenilir veri yok) — yayınlanmamalı

YALNIZCA şu JSON'u döndür:
{{
  "karar": "onay|revize|red",
  "puan": 0,
  "kritik_hatalar": ["..."],
  "yazar_icin": ["somut düzeltme talimatı"],
  "gorsel_icin": ["somut düzeltme talimatı"],
  "ekip_notu": "gelecek paylaşımlar için kalıcı ders (yoksa boş)",
  "gerekce": "kısa açıklama"
}}"""


def kural_kontrolleri(taslak: dict, spec: dict, bulgular: list[dict]) -> tuple[list[str], list[str]]:
    """(yazar_hatalari, gorsel_hatalari) döndürür."""
    u = ayarlar()["uzunluk"]
    yazar, gorsel = [], []
    tr, en = taslak.get("metin_tr", ""), taslak.get("metin_en", "")
    if not tr or not en:
        yazar.append("Türkçe ve İngilizce metinlerin ikisi de dolu olmalı")
    if len(tr) > u["tr_azami"]:
        yazar.append(f"Türkçe metin {len(tr)} karakter; en fazla {u['tr_azami']} olmalı, kısalt")
    if len(en) > u["en_azami"]:
        yazar.append(f"İngilizce metin {len(en)} karakter; en fazla {u['en_azami']} olmalı, kısalt")
    if "http" in tr or "http" in en:
        yazar.append("Metinlerden linkleri çıkar; kaynaklar ayrıca yayınlanıyor")
    if not taslak.get("anahtar_rakamlar"):
        yazar.append("anahtar_rakamlar listesi boş; kullanılan her rakamı kaynağıyla listele")
    gorsel += seri_dogrula(spec, bulgular)
    if not spec.get("kaynak"):
        gorsel.append("Görselde kaynak satırı eksik")
    return yazar, gorsel


def denetle(taslak: dict, spec: dict, png: Path, bulgular: list[dict], son_paylasimlar: str) -> dict:
    a = ayarlar()
    yazar_k, gorsel_k = kural_kontrolleri(taslak, spec, bulgular)

    sistem = SISTEM_SABLONU.format(tarih=tarih_metni(), stil=a["stil"], asgari_puan=a["denetim"]["asgari_puan"])
    metin = (
        f"Son paylaşımlar:\n{son_paylasimlar}\n\n"
        f"TASLAK (JSON):\n{json.dumps(taslak, ensure_ascii=False)}\n\n"
        f"GÖRSEL TASARIMI (JSON):\n{json.dumps(spec, ensure_ascii=False)}\n\n"
        f"ARAŞTIRMA BULGULARI (tek doğruluk kaynağı):\n{json.dumps(bulgular, ensure_ascii=False)}\n\n"
        "Ekteki görsel, yayınlanacak görselin kendisidir. Denetle."
    )
    icerik = [gorsel_blogu(png), {"type": "text", "text": metin}]
    rapor, _ = claude_json(sistem, icerik, a["modeller"]["denetci"], max_tokens=4000)

    rapor.setdefault("yazar_icin", [])
    rapor.setdefault("gorsel_icin", [])
    rapor.setdefault("kritik_hatalar", [])
    rapor["yazar_icin"] += yazar_k
    rapor["gorsel_icin"] += gorsel_k
    rapor["kural_kontrolleri"] = {"yazar": yazar_k, "gorsel": gorsel_k}

    # Kural ihlali ya da düşük puan varsa onay verilemez
    if rapor.get("karar") == "onay" and (yazar_k or gorsel_k or rapor.get("kritik_hatalar")
                                         or rapor.get("puan", 0) < a["denetim"]["asgari_puan"]):
        rapor["karar"] = "revize"
    log.info("Denetim: %s (puan %s) | yazar: %d, görsel: %d düzeltme", rapor.get("karar"), rapor.get("puan"),
             len(rapor["yazar_icin"]), len(rapor["gorsel_icin"]))
    return rapor
