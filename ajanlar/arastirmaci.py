"""Araştırma ajanları (Türkiye / Dünya / Un). Web araması yapar, kaynaklı bulgu üretir."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .ortak import ayarlar, claude_json, kaydedici, tarih_metni

log = kaydedici("arastirmaci")

SISTEM_SABLONU = """Sen "{ad}" rolündesin: buğday ve un piyasaları konusunda titiz bir araştırma analistisin.

Odak alanın: {odak}
Öncelikli kaynaklar: {kaynaklar}

Kurallar:
- Web aramasıyla GÜNCEL bilgi topla. Bugünün tarihi: {tarih}. Son 7 günün verisini tercih et;
  daha eskiyse tarihini açıkça belirt.
- Her rakamı kaynağının URL'siyle birlikte yaz. Kaynağını bulamadığın hiçbir rakamı yazma.
- Resmî kurum ve birincil kaynakları (TMO, TÜİK, USDA, IGC, FAO, borsa bültenleri) haber
  sitelerine tercih et. Kaynaklar çelişiyorsa ikisini de yaz ve "belirsizlikler"e not düş.
- Görselleştirilebilecek zaman serisi (en az 4 nokta) bulursan "zaman_serileri"ne ekle. Uydurma
  ya da tahmini ara değer ekleme; yalnızca kaynakta görünen noktaları yaz.
- Yorum değil, olgu topla. Yorum yazarın işi.

YALNIZCA şu JSON'u döndür:
{{
  "ozet": "3-5 cümlelik olgusal özet",
  "bulgular": [
    {{"iddia": "...", "rakam": "sayısal değer ya da boş", "birim": "TL/ton, $/ton, bin ton, % ...",
      "veri_tarihi": "GG.AA.YYYY veya dönem", "kaynak_adi": "...", "kaynak_url": "https://..."}}
  ],
  "zaman_serileri": [
    {{"ad": "...", "birim": "...", "kaynak_url": "https://...",
      "noktalar": [{{"etiket": "Oca 2026", "deger": 0.0}}]}}
  ],
  "belirsizlikler": ["..."]
}}"""


def _gorev_calistir(gorev: dict) -> dict:
    a = ayarlar()
    profil = a["arastirma_ajanlari"][gorev["ajan"]]
    derin = gorev.get("derinlik") == "derin"
    limit = a["arastirma"]["derin_arama_limiti"] if derin else a["arastirma"]["hizli_arama_limiti"]
    sistem = SISTEM_SABLONU.format(ad=profil["ad"], odak=profil["odak"], kaynaklar=profil["kaynaklar"],
                                   tarih=tarih_metni())
    sorular = "\n".join(f"- {s}" for s in gorev.get("sorular", []))
    icerik = (
        f"Görev derinliği: {'DERİN araştırma' if derin else 'HIZLI tarama (yalnızca önemli gelişmeler)'}\n"
        f"Yanıtlanacak sorular:\n{sorular}"
    )
    log.info("%s başladı (%s, en fazla %d arama)", profil["ad"], gorev.get("derinlik"), limit)
    sonuc, alinti_kaynaklari = claude_json(sistem, icerik, a["modeller"]["arastirmaci"],
                                           max_tokens=8000, web_arama=limit)
    sonuc["ajan"] = gorev["ajan"]
    sonuc["derinlik"] = gorev.get("derinlik")
    sonuc["arama_alintilari"] = alinti_kaynaklari  # web aramasının döndürdüğü gerçek URL'ler
    sonuc.setdefault("bulgular", [])
    sonuc.setdefault("zaman_serileri", [])
    log.info("%s bitti: %d bulgu, %d seri", profil["ad"], len(sonuc["bulgular"]), len(sonuc["zaman_serileri"]))
    return sonuc


def arastir(gorevler: list[dict]) -> list[dict]:
    """Görevleri paralel çalıştırır."""
    with ThreadPoolExecutor(max_workers=3) as havuz:
        return list(havuz.map(_gorev_calistir, gorevler))


def kaynak_listesi(bulgular: list[dict]) -> list[dict]:
    """Tüm bulgulardaki kaynakları tekilleştirir."""
    gorulen, liste = set(), []
    for b in bulgular:
        adaylar = [{"url": x.get("kaynak_url"), "baslik": x.get("kaynak_adi", "")} for x in b.get("bulgular", [])]
        adaylar += [{"url": s.get("kaynak_url"), "baslik": s.get("ad", "")} for s in b.get("zaman_serileri", [])]
        for k in adaylar:
            if k["url"] and k["url"].startswith("http") and k["url"] not in gorulen:
                gorulen.add(k["url"])
                liste.append(k)
    return liste
