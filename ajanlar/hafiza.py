"""Ajanların ortak hafızası: geçmiş paylaşımlar, tekrar önleme, notlar.

data/hafiza.json dosyasında tutulur ve her çalışmadan sonra depoya işlenir.
"""
from __future__ import annotations

from .ortak import VERI, json_oku, json_yaz

DOSYA = VERI / "hafiza.json"
AZAMI_KAYIT = 90


class Hafiza:
    def __init__(self):
        self.veri = json_oku(DOSYA, {"paylasimlar": [], "notlar": []})

    def son_paylasimlar(self, adet: int = 15) -> list[dict]:
        return self.veri["paylasimlar"][-adet:]

    def ozet_metni(self, adet: int = 15) -> str:
        satirlar = [
            f"- {p['tarih']} | {p['tema']} | {p['baslik']} | ana rakamlar: {', '.join(p.get('anahtar_rakamlar', [])[:3])}"
            for p in self.son_paylasimlar(adet)
        ]
        return "\n".join(satirlar) or "(Henüz paylaşım yok)"

    def notlar_metni(self, adet: int = 10) -> str:
        return "\n".join(f"- {n}" for n in self.veri["notlar"][-adet:]) or "(Not yok)"

    def paylasim_ekle(self, tarih: str, tema: str, baslik: str, ozet: str, anahtar_rakamlar: list[str]):
        self.veri["paylasimlar"].append(
            {"tarih": tarih, "tema": tema, "baslik": baslik, "ozet": ozet, "anahtar_rakamlar": anahtar_rakamlar}
        )
        self.veri["paylasimlar"] = self.veri["paylasimlar"][-AZAMI_KAYIT:]

    def not_ekle(self, not_metni: str):
        if not_metni and not_metni not in self.veri["notlar"]:
            self.veri["notlar"].append(not_metni)
            self.veri["notlar"] = self.veri["notlar"][-40:]

    def kaydet(self):
        json_yaz(DOSYA, self.veri)
