"""Görsel ajan: bulgulardan grafik tasarımı (JSON) üretir ve markalı PNG olarak çizer.

Claude grafiğin NE göstereceğine karar verir; çizimi deterministik olarak matplotlib yapar.
Böylece görseldeki her sayı araştırma verisinden gelir ve denetlenebilir.
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from .ortak import ayarlar, claude_json, kaydedici, tarih_metni  # noqa: E402

log = kaydedici("gorsel")

SISTEM = """Sen bir veri görselleştirme tasarımcısısın. LinkedIn gönderisine eşlik edecek TEK bir görsel tasarlarsın.

Seçenekler:
- "cizgi": zaman içindeki değişim (en az 4 nokta). En fazla 3 seri, aynı birimde.
- "bar": kategoriler arası karşılaştırma (ülkeler, yıllar, pazarlar). En fazla 8 çubuk.
- "kart": uygun seri yoksa 1-3 anahtar rakamı büyük puntoyla gösteren bilgi kartı.

Kurallar:
- Grafik değerlerini YALNIZCA araştırma bulgularındaki "zaman_serileri" noktalarından veya
  "bulgular"daki rakamlardan birebir al. Değer uydurma, enterpolasyon yapma.
- Gönderi metniyle tutarlı ol: görsel metnin ana mesajını desteklesin.
- Başlıklar kısa olsun: baslik_tr en fazla 60, baslik_en en fazla 60 karakter.
- Kart açıklamaları en fazla 45 karakter.
- "kaynak" alanına kurum adları ve veri tarihini yaz (ör. "Kaynak: TMO, Konya TB — 22.09.2026").

YALNIZCA şu JSON'u döndür:
{
  "tip": "cizgi|bar|kart",
  "baslik_tr": "...", "baslik_en": "...",
  "birim": "TL/ton",
  "etiketler": ["..."],
  "seriler": [{"ad": "...", "degerler": [0.0]}],
  "kartlar": [{"deger": "13.250 TL/t", "aciklama_tr": "...", "aciklama_en": "...", "yon": "yukari|asagi|yatay"}],
  "not_tr": "isteğe bağlı kısa not",
  "kaynak": "Kaynak: ..."
}"""


def tasarla(taslak: dict, bulgular: list[dict], gorsel_fikri: str = "", geri_bildirim: list[str] | None = None,
            onceki: dict | None = None) -> dict:
    icerik = (
        f"Planlanan görsel fikri: {gorsel_fikri}\n\n"
        f"Gönderi başlığı: {taslak.get('baslik')}\nGönderi metni:\n{taslak.get('metin_tr')}\n\n"
        f"Araştırma bulguları:\n{json.dumps(bulgular, ensure_ascii=False)}"
    )
    if geri_bildirim:
        icerik += (
            f"\n\nÖnceki tasarım:\n{json.dumps(onceki, ensure_ascii=False)}\n"
            "Denetçinin istediği düzeltmeler:\n" + "\n".join(f"- {g}" for g in geri_bildirim)
        )
    spec, _ = claude_json(SISTEM, icerik, ayarlar()["modeller"]["gorsel"], max_tokens=3000)
    log.info("Görsel tasarımı: %s — %s", spec.get("tip"), spec.get("baslik_tr"))
    return spec


# ------------------------------------------------------------ doğrulama

def _sayilar(metin) -> set[float]:
    """'13.250,5' / '13,250.5' / '%3,2' gibi ifadelerden olası sayıları çıkarır."""
    sonuc = set()
    if isinstance(metin, (int, float)):
        return {float(metin)}
    for parca in re.findall(r"-?\d[\d.,]*", str(metin or "")):
        parca = parca.rstrip(".,")
        adaylar = {
            parca.replace(".", "").replace(",", "."),   # TR biçimi
            parca.replace(",", ""),                      # EN biçimi
        }
        for a in adaylar:
            try:
                sonuc.add(float(a))
            except ValueError:
                pass
    return sonuc


def seri_dogrula(spec: dict, bulgular: list[dict]) -> list[str]:
    """Grafikteki her değerin araştırma verisinde bulunduğunu kontrol eder."""
    if spec.get("tip") not in ("cizgi", "bar"):
        return []
    havuz: set[float] = set()
    for b in bulgular:
        for s in b.get("zaman_serileri", []):
            for n in s.get("noktalar", []):
                havuz |= _sayilar(n.get("deger"))
        for x in b.get("bulgular", []):
            havuz |= _sayilar(x.get("rakam"))
            havuz |= _sayilar(x.get("iddia"))
    hatalar = []
    for seri in spec.get("seriler", []):
        for d in seri.get("degerler", []):
            if d is None:
                continue
            if not any(abs(float(d) - h) <= max(0.01, abs(h) * 0.005) for h in havuz):
                hatalar.append(f"Grafik değeri araştırma verisinde yok: {seri.get('ad')} = {d}")
    etiket_sayisi = len(spec.get("etiketler", []))
    for seri in spec.get("seriler", []):
        if len(seri.get("degerler", [])) != etiket_sayisi:
            hatalar.append(f"'{seri.get('ad')}' serisinin değer sayısı etiket sayısıyla uyuşmuyor")
    if not spec.get("seriler"):
        hatalar.append("Grafik tipinde seri yok")
    return hatalar


# ------------------------------------------------------------ çizim

def _tr_sayi(x: float) -> str:
    if abs(x) >= 100:
        return f"{x:,.0f}".replace(",", ".")
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").rstrip("0").rstrip(",")


def ciz(spec: dict, cikti: Path) -> Path:
    a = ayarlar()
    r = a["marka"]["renkler"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": r["koyu"], "text.color": r["koyu"],
                         "axes.labelcolor": r["koyu"], "xtick.color": r["koyu"], "ytick.color": r["koyu"]})

    fig = plt.figure(figsize=(8, 10), dpi=150, facecolor=r["zemin"])

    # Üst bant
    bant = fig.add_axes([0, 0.93, 1, 0.07])
    bant.set_axis_off()
    bant.add_patch(plt.Rectangle((0, 0), 1, 1, color=r["koyu"], transform=bant.transAxes))
    bant.text(0.05, 0.5, a["marka"]["ad"], color=r["zemin"], fontsize=15, weight="bold", va="center")
    bant.text(0.95, 0.5, tarih_metni(), color=r["ana"], fontsize=12, va="center", ha="right")

    # Başlıklar
    y = 0.885
    for satir in textwrap.wrap(spec.get("baslik_tr", ""), 34)[:2]:
        fig.text(0.06, y, satir, fontsize=23, weight="bold", color=r["koyu"], va="top")
        y -= 0.04
    for satir in textwrap.wrap(spec.get("baslik_en", ""), 52)[:2]:
        fig.text(0.06, y, satir, fontsize=14, color=r["ana"], va="top", style="italic")
        y -= 0.028
    fig.add_artist(plt.Line2D([0.06, 0.2], [y - 0.008, y - 0.008], color=r["ana"], lw=4))
    ust = y - 0.04

    tip = spec.get("tip")
    if tip in ("cizgi", "bar") and spec.get("seriler"):
        ax = fig.add_axes([0.13, 0.19, 0.81, ust - 0.23])
        ax.set_facecolor(r["zemin"])
        etiketler = spec.get("etiketler", [])
        palet = [r["ana"], r["koyu"], r["vurgu"]]
        seriler = spec["seriler"][:3]
        if tip == "cizgi":
            for i, s in enumerate(seriler):
                ax.plot(range(len(s["degerler"])), s["degerler"], color=palet[i], lw=3, marker="o", ms=6,
                        label=s.get("ad"))
                ax.annotate(_tr_sayi(s["degerler"][-1]), (len(s["degerler"]) - 1, s["degerler"][-1]),
                            xytext=(0, 12), textcoords="offset points", ha="center", fontsize=12,
                            weight="bold", color=palet[i])
        else:
            n = len(seriler)
            gen = 0.8 / n
            for i, s in enumerate(seriler):
                xs = [k + (i - (n - 1) / 2) * gen for k in range(len(s["degerler"]))]
                cubuklar = ax.bar(xs, s["degerler"], width=gen * 0.92, color=palet[i], label=s.get("ad"))
                for c, d in zip(cubuklar, s["degerler"]):
                    ax.annotate(_tr_sayi(d), (c.get_x() + c.get_width() / 2, c.get_height()),
                                xytext=(0, 4), textcoords="offset points", ha="center", fontsize=10)
        ax.set_xticks(range(len(etiketler)))
        ax.set_xticklabels(etiketler, rotation=35 if len(etiketler) > 6 else 0,
                           ha="right" if len(etiketler) > 6 else "center", fontsize=11)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _tr_sayi(v)))
        ax.set_ylabel(spec.get("birim", ""), fontsize=12)
        for kenar in ("top", "right"):
            ax.spines[kenar].set_visible(False)
        ax.grid(axis="y", alpha=0.25)
        ust_deger = max(max(s["degerler"]) for s in seriler)
        alt_deger = min(min(s["degerler"]) for s in seriler)
        if tip == "bar":
            ax.set_ylim(min(0, alt_deger * 1.1), ust_deger * 1.1)
        else:
            pay = (ust_deger - alt_deger) * 0.15 or abs(ust_deger) * 0.05 or 1
            ax.set_ylim(alt_deger - pay, ust_deger + pay)
        if len(seriler) > 1 or seriler[0].get("ad"):
            ax.legend(frameon=False, fontsize=11, loc="lower left", bbox_to_anchor=(0, 1.01),
                      ncol=len(seriler), borderaxespad=0)
    else:
        kartlar = spec.get("kartlar", [])[:3] or [{"deger": "—", "aciklama_tr": "Veri yok"}]
        alan_ust, alan_alt = ust, 0.19
        yuk = (alan_ust - alan_alt) / len(kartlar)
        oklar = {"yukari": ("▲", r["vurgu"]), "asagi": ("▼", r["uyari"]), "yatay": ("●", r["ana"])}
        for i, k in enumerate(kartlar):
            kx0, ky0 = 0.06, alan_ust - (i + 1) * yuk + 0.012
            fig.add_artist(FancyBboxPatch((kx0, ky0), 0.88, yuk - 0.024, boxstyle="round,pad=0,rounding_size=0.015",
                                          transform=fig.transFigure, facecolor="white", edgecolor=r["ana"], lw=1.2))
            orta = ky0 + (yuk - 0.024) / 2
            isaret, renk = oklar.get(k.get("yon", "yatay"), oklar["yatay"])
            fig.text(0.1, orta + 0.022, f"{isaret} {k.get('deger', '')}", fontsize=30, weight="bold",
                     color=renk, va="center")
            fig.text(0.1, orta - 0.028, k.get("aciklama_tr", ""), fontsize=14, color=r["koyu"], va="center")
            if k.get("aciklama_en"):
                fig.text(0.1, orta - 0.055, k["aciklama_en"], fontsize=11, color=r["ana"], va="center",
                         style="italic")

    # Alt bilgi
    if spec.get("not_tr"):
        fig.text(0.06, 0.115, textwrap.shorten(spec["not_tr"], 90), fontsize=10.5, color=r["koyu"])
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.095, 0.095], color=r["ana"], lw=0.8))
    fig.text(0.06, 0.07, textwrap.shorten(spec.get("kaynak", ""), 95), fontsize=10, color=r["koyu"])
    fig.text(0.06, 0.042, textwrap.shorten(a["yayin"].get("uyari_notu", ""), 110), fontsize=8, color=r["ana"])

    cikti.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(cikti, dpi=150, facecolor=r["zemin"])
    plt.close(fig)
    log.info("Görsel çizildi: %s", cikti)
    return cikti
