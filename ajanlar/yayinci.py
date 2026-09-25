"""Yayıncı ajan: onaylanmış paylaşımı Metricool API üzerinden LinkedIn'e planlar.

Gerekli ortam değişkenleri (GitHub Secrets):
  METRICOOL_USER_TOKEN, METRICOOL_USER_ID, METRICOOL_BLOG_ID
İsteğe bağlı:
  MEDIA_BASE_URL  -> görselin herkese açık adres kökü (varsayılan: GitHub raw adresi)
"""
from __future__ import annotations

import datetime as dt
import os

import requests

from .ortak import ayarlar, kaydedici, simdi

log = kaydedici("yayinci")
API = "https://app.metricool.com/api"


def metni_birlestir(taslak: dict) -> str:
    a = ayarlar()
    parcalar = [taslak["metin_tr"].strip(), "— English —", taslak["metin_en"].strip()]
    if a["marka"].get("linkedin_imza"):
        parcalar.append(a["marka"]["linkedin_imza"])
    if taslak.get("hashtagler"):
        parcalar.append(" ".join(taslak["hashtagler"][:5]))
    if a["yayin"].get("uyari_notu"):
        parcalar.append(a["yayin"]["uyari_notu"])
    return "\n\n".join(parcalar)


def ilk_yorum(kaynaklar: list[dict]) -> str:
    satirlar = ["Kaynaklar / Sources:"] + [f"• {k.get('baslik') or k['url']}: {k['url']}" for k in kaynaklar[:8]]
    return "\n".join(satirlar)


def yayin_zamani() -> dt.datetime:
    saat, dakika = map(int, ayarlar()["yayin"]["saat"].split(":"))
    su_an = simdi()
    hedef = su_an.replace(hour=saat, minute=dakika, second=0, microsecond=0)
    # İş akışı gecikmişse en az 15 dakika sonrasına planla
    return max(hedef, su_an + dt.timedelta(minutes=15))


class Metricool:
    def __init__(self):
        self.token = os.environ["METRICOOL_USER_TOKEN"]
        self.user_id = os.environ["METRICOOL_USER_ID"]
        self.blog_id = os.environ["METRICOOL_BLOG_ID"]

    def _parametreler(self, **ek):
        return {"userId": self.user_id, "blogId": self.blog_id, **ek}

    def _basliklar(self):
        return {"X-Mc-Auth": self.token, "Content-Type": "application/json"}

    def gorsel_normallestir(self, url: str) -> str:
        """Metricool, görseli kendi sunucusuna alıp kullanılabilir bir URL döndürür."""
        y = requests.get(f"{API}/actions/normalize/image/url", headers=self._basliklar(),
                         params=self._parametreler(url=url), timeout=60)
        y.raise_for_status()
        try:
            veri = y.json()
        except ValueError:
            return y.text.strip().strip('"') or url
        if isinstance(veri, str):
            return veri
        if isinstance(veri, dict):
            for anahtar in ("url", "data", "mediaUrl", "normalizedUrl"):
                if isinstance(veri.get(anahtar), str):
                    return veri[anahtar]
        return url

    def planla(self, metin: str, gorsel_url: str | None, zaman: dt.datetime, taslak_mi: bool,
               ilk_yorum_metni: str = "") -> dict:
        medya = [self.gorsel_normallestir(gorsel_url)] if gorsel_url else []
        govde = {
            "autoPublish": not taslak_mi,
            "draft": taslak_mi,
            "descendants": [],
            "firstCommentText": ilk_yorum_metni,
            "hasNotReadNotes": False,
            "media": medya,
            "mediaAltText": [],
            "providers": [{"network": "linkedin"}],
            "publicationDate": {"dateTime": zaman.strftime("%Y-%m-%dT%H:%M:%S"),
                                "timezone": ayarlar().get("zaman_dilimi", "Europe/Istanbul")},
            "shortener": False,
            "smartLinkData": {"ids": []},
            "text": metin,
            "linkedinData": {"documentTitle": "", "publishImagesAsPDF": False, "previewIncluded": True,
                             "type": "post"},
        }
        y = requests.post(f"{API}/v2/scheduler/posts", headers=self._basliklar(),
                          params=self._parametreler(), json=govde, timeout=60)
        if y.status_code >= 400:
            raise RuntimeError(f"Metricool hatası {y.status_code}: {y.text[:500]}")
        log.info("Metricool'a planlandı: %s (%s)", zaman.strftime("%d.%m %H:%M"), "taslak" if taslak_mi else "otomatik")
        try:
            return y.json()
        except ValueError:
            return {"yanit": y.text}


def varsayilan_medya_koku() -> str | None:
    if os.environ.get("MEDIA_BASE_URL"):
        return os.environ["MEDIA_BASE_URL"].rstrip("/")
    depo, dal = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{depo}/{dal}" if depo else None
