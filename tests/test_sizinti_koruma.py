"""Koruma turu sizinti testleri: kodu KIRMAYA calisan saldirilar (sizinti testcisi, koruma turu).

Yalnizca bu dosya yazildi; mevcut hicbir test, yardimci, `data/`, `config.py` ya da `.claude/` dosyasina
dokunulmadi. Kilitli dosyalara dokunulmaz: hook komutlari CALISTIRILMAZ, yalnizca metin olarak
degerlendirilir; git testleri gecici depoda calisir. Aga cikilmaz, getiri hesaplanmaz.

Kural: BASARILI saldirilar (kodda gercek acik) `xfail(strict=True, raises=AssertionError)` ile
isaretlidir ve gerekcesi `reason` alaninda yazilidir. Savusturulan saldirilar normal gecen testtir.
Saldiri testleri `pytest.raises` yerine `_reddeder` yardimcisini kullanir: reddedilmezse
AssertionError olur, boylece `raises=AssertionError` ile uyumlu kalir.

NOT: bu dosya yazilirken kabuk (komut calistirma) yoktu; sonuclar KOD OKUMAYLA ONGORULDU, testler
KOSULMADI. Beklenmedik `XPASS(strict)`/`FAILED` varsa ongoru yanlistir; once o teste bakin.

BASLIK -> TEST ESLEMESI
  1. PowerShell ve bilinmeyen kabuk kanali : test_ps_*, test_bash_*, test_main_*
  2. Yol normallestirmesi                  : test_yol_*
  3. Pozitif fiyat                         : test_fiyat_*, test_gecersizlik_*
  4. Kimlik capraz dogrulamasi             : test_kimlik_*
  5. Havuz imzasi ve esik sayimi           : test_havuz_*
  6. Kilit kaydi                           : test_kilit_*
  7. config korumasi                       : test_config_*
  8. Donem siniri ve bar dusurme           : test_donem_*, test_mum_zamanlari_*
"""

from __future__ import annotations

import copy
import dataclasses
import importlib.util
import io
import json
import math
import sys
import types
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import dizi, donem, ornekleme, pencere, pozisyon, sinyal, split
from dizi_yardimcisi import _karar_kur, olaylar_kur, tek_olay
from onay_yardimcisi import gecici_depo, git, kilit_metni, kilit_yaz
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur
from sinyal_yardimcisi import yapilandirma

KOK = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("kilit_hook_sizinti_koruma",
                                               KOK / ".claude" / "hooks" / "kilitli_dosya_korumasi.py")
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook
_SPEC.loader.exec_module(hook)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
K = "analysis/h1/" + "KILIT" + ".md"          # kilitli dosya (adi parcali yazilir)


def XF(neden: str):
    """Basarili saldiri: acik kapanana kadar beklenen hata (strict: acik kapanirsa XPASS = FAILED)."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=neden)


def _reddeder(cagri, *hatalar):
    """`cagri` verilen hata siniflarindan biriyle reddedilmeli; reddedilmezse AssertionError (saldiri basardi)."""
    hatalar = hatalar or (Exception,)
    try:
        cagri()
    except hatalar:
        return
    except Exception as hata:  # farkli sinif: reddedildi ama beklenen sinifla degil
        raise AssertionError(f"beklenen {hatalar}, gozlenen {type(hata).__name__}: {hata}") from None
    raise AssertionError("saldiri basarili: cagri reddedilmedi")


def _hook_reddeder(arac, komut):
    karar = hook.komut_degerlendir(arac, komut)
    assert not karar.izin, f"[{arac}] izin verildi: {komut!r}"


def _main(monkeypatch, capsys, girdi) -> str:
    monkeypatch.delenv(hook.ACMA_DEGISKENI, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(girdi)))
    assert hook.main() == 0
    return capsys.readouterr().out


# =====================================================================================================
# 1. PowerShell ve bilinmeyen kabuk kanali
# =====================================================================================================

PS_SAVUSTURULAN = [
    ("PowerShell", f"Set-Content -LiteralPath {K} -Value x"),
    ("PowerShell", f"Out-File -FilePath {K} -Append"),
    ("PowerShell", "Move-Item -Path x.md -Destination CLAUDE.md"),
    ("PowerShell", "Rename-Item CLAUDE.md y.md"),
    ("PowerShell", "Add-Content CLAUDE.md x"),
    ("PowerShell", "Remove-Item -Recurse analysis"),
    ("PowerShell", "Get-Date 1>CLAUDE.md"),
    ("PowerShell", "'x' >> CLAUDE.md"),
    ("PowerShell", 'cmd /c "echo x>CLAUDE.md"'),
    ("YeniKabuk", 'cmd /c "echo x>CLAUDE.md"'),
    ("PowerShell", 'powershell -Command "Set-Content CLAUDE.md x"'),
    ("PowerShell", "&{ Set-Content CLAUDE.md x }"),
    ("YeniKabuk", "&{Set-Content CLAUDE.md x}"),
    ("PowerShell", "@'\nSet-Content CLAUDE.md x\n'@ | Invoke-Expression"),
    ("PowerShell", "Copy-Item -Path y.md -Destination CLAUDE.md -Force"),
    ("YeniKabuk", "sed -i s/a/b/ CLAUDE.md"),
]


@pytest.mark.parametrize("arac,komut", PS_SAVUSTURULAN)
def test_ps_bilinen_yazma_yollari_reddedilir(arac, komut):
    """Dayanak: madde 1 (PowerShell kanali). Bilinen yazma cmdlet'leri, yonlendirme, ic ice kabuk."""
    _hook_reddeder(arac, komut)


PS_ACIKLAR = [
    pytest.param("PowerShell", f"[System.IO.File]::WriteAllText('{K}','x')",
                 marks=XF(".NET cagrisinda `(` parcayi boler; yol yeni parcanin ILK tokeni olur ve hic bakilmaz"),
                 id="dotnet-writealltext"),
    pytest.param("PowerShell", f'[IO.File]::WriteAllText("{K}", "x")',
                 marks=XF("ayni: yol parcanin ilk tokeni"), id="dotnet-bosluklu"),
    pytest.param("PowerShell", "Set-Content -Path:CLAUDE.md -Value x",
                 marks=XF("`-Path:deger` bicimi: token `-Path:CLAUDE.md` dosya adiyla eslesmez"),
                 id="iki-nokta-parametre"),
    pytest.param("PowerShell", f"Remove-Item -LiteralPath:{K}",
                 marks=XF("`-LiteralPath:analysis/...`: desen oncesinde ayirici arar, `:` ayirici degil"),
                 id="iki-nokta-kilit"),
    pytest.param("PowerShell", "Set-Content -Path a.txt,CLAUDE.md -Value x",
                 marks=XF("virgullu yol dizisi tek token; `a.txt,CLAUDE.md` eslesmez"), id="virgullu-dizi"),
    pytest.param("PowerShell", f"Add-Content -Path @('a.txt','{K}') -Value x",
                 marks=XF("`@( )` dizisi: parantez parcayi boler, yol ilk token"), id="dizi-argumani"),
    pytest.param("PowerShell", 'Invoke-Expression "Remove-Item CLAUDE.md"',
                 marks=XF("`Invoke-Expression` sarmalayici atlanir, tirnakli komut 'cmdlet adi' olur; icerik taranmaz"),
                 id="iex"),
    pytest.param("YeniKabuk", 'Invoke-Expression "Remove-Item CLAUDE.md"',
                 marks=XF("ayni; bash lehcesinin temkinli reddi PowerShell'in IZNIyle dusurulur"), id="iex-bilinmeyen-arac"),
    pytest.param("PowerShell", f"iex 'Set-Content {K} x'", marks=XF("`iex` takma adi ayni delik"), id="iex-takma"),
    pytest.param("PowerShell", "1 | ForEach-Object { Remove-Item CLAUDE.md }",
                 marks=XF("`ForEach-Object` salt okuma listesinde: betik blogundaki yazma gorulmez"), id="foreach-object"),
    pytest.param("PowerShell", "Get-ChildItem analysis -Recurse -Filter KILIT.md | Remove-Item",
                 marks=XF("boruyla beslenen silme: `Remove-Item` argumansiz, ad onceki parcada"), id="boru-ile-silme"),
    pytest.param("PowerShell", "Set-Content `\nCLAUDE.md x",
                 marks=XF("backtick-satir sonu devami: ad yeni parcanin ilk tokeni"), id="backtick-devam"),
    pytest.param("PowerShell", "Set-Content CLA`UDE.md x",
                 marks=XF("backtick kacisi dosya adini bozar (PowerShell `U`yu U sayar)"), id="backtick-kacis"),
    pytest.param("PowerShell", "Remove-Item analysis/h1/KILIT.m*",
                 marks=XF("somut dizin + joker: `kapsar_mi` joker yolunda dizin bileseni eslesmez"), id="somut-dizin-joker"),
    pytest.param("PowerShell", "Rename-Item -Path analysis/h1/taslak.md -NewName KILIT.md",
                 marks=XF("`-NewName KILIT.md` yalin ad: kilit dosyasi YENI ADLA olusturulur"), id="rename-newname"),
    pytest.param("PowerShell", "Set-Location analysis/h1; Set-Content KILIT.md x",
                 marks=XF("dizine girip yalin adla yazma: yalin KILIT.md korunmaz"), id="cd-sonra-yalin-ad"),
    pytest.param("PowerShell", "Set-Content -Path (Join-Path . CLAUDE.md) -Value x",
                 marks=XF("`(Join-Path ...)` ayri parca ve `Join-Path` salt okuma listesinde"), id="join-path"),
]


@pytest.mark.parametrize("arac,komut", PS_ACIKLAR)
def test_ps_diger_yazma_yollari_reddedilmeli(arac, komut):
    """Dayanak: madde 1; CLAUDE.md §5 Koruma katmani (kilitli dosyaya yazma niyeti reddedilir)."""
    _hook_reddeder(arac, komut)


@pytest.mark.parametrize("komut", [
    "Get-Content CLAUDE.md", f"Get-Content {K} | Measure-Object -Line", "Select-String -Path CLAUDE.md -Pattern x",
    "Get-ChildItem analysis", f"Test-Path {K}",
])
def test_ps_salt_okuma_yanlis_pozitif_vermez(komut):
    """Dayanak: madde 1; salt okuma cmdlet'leri gecer."""
    assert hook.komut_degerlendir("PowerShell", komut).izin, komut


BASH_ACIKLAR = [
    pytest.param("sed -n 'w CLAUDE.md' README.md", marks=XF("`sed` w komutu dosyaya yazar; yalnizca -i denetlenir"), id="sed-w"),
    pytest.param("awk 'BEGIN{print \"x\" > \"CLAUDE.md\"}'", marks=XF("`awk` program ici yonlendirme denetlenmez"), id="awk-yonlendirme"),
    pytest.param("sort -o CLAUDE.md CLAUDE.md", marks=XF("`sort -o` yazar ama `sort` salt okuma listesinde"), id="sort-o"),
    pytest.param("git diff --output=CLAUDE.md", marks=XF("`git diff --output=` yazar; diff okuma listesinde"), id="git-diff-output"),
    pytest.param("git config --file CLAUDE.md a.b c", marks=XF("`git config --file` yazar; config okuma listesinde"), id="git-config-file"),
    pytest.param("cd analysis/h1 && rm KILIT.md", marks=XF("cd sonrasi yalin ad korunmaz"), id="cd-rm"),
    pytest.param("cd analysis/h1 && echo x > KILIT.md", marks=XF("cd sonrasi yalin ad yonlendirmesi"), id="cd-yonlendirme"),
    pytest.param("find analysis -name KILIT.md -delete", marks=XF("`find -delete`: desen anmasi yol ister, yalin ad gecer"), id="find-delete"),
    pytest.param("printf 'CLAUDE.md' | xargs rm", marks=XF("ad boruyla tasinir; `xargs rm` argumansiz"), id="xargs"),
    pytest.param("rm analysis/h1/K*", marks=XF("somut dizin + joker"), id="somut-dizin-joker"),
    pytest.param("cp -t analysis/h1 /tmp/KILIT.md", marks=XF("`cp -t`: hedef dizin son arguman degil"), id="cp-t"),
    pytest.param("rm CLAUD${U}E.md", marks=XF("bos degisken ile ad bolunur (kararli saklama; hook'un bilinen siniri)"), id="degisken-saklama"),
    pytest.param("rm CLA\\UDE.md", marks=XF("bash `\\U` = U; hook ters egik cizgiyi ayirici sayar"), id="ters-egik-kacis"),
    pytest.param("rm PREREG~1.MD", marks=XF("8.3 kisa ad (dusuk onem: kararli atlatma)"), id="kisa-ad-8.3"),
    pytest.param(f"echo x > {K}:akis", marks=XF("NTFS alternatif akis `:akis` (tek iki nokta) taninmaz; ana akisi degistirmez (dusuk onem)"),
                 id="ads-tek-iki-nokta"),
]


@pytest.mark.parametrize("komut", BASH_ACIKLAR)
def test_bash_diger_yazma_yollari_reddedilmeli(komut):
    """Dayanak: madde 1 (bilinmeyen kanal) ve CLAUDE.md §5 Koruma katmani."""
    _hook_reddeder("Bash", komut)


@pytest.mark.parametrize("komut", [
    f"sed -i s/a/b/ {K}", "rm -rf analysis", "tee -a CLAUDE.md", "dd if=/dev/zero of=CLAUDE.md",
    "git checkout .", "python -c \"open('CLAUDE.md','w')\"", "echo x > CLAUDE.md", "mv x.md CLAUDE.md",
    "cp x.md CLAUDE.md", "python - <<EOF\nopen('CLAUDE.md','w')\nEOF",
])
def test_bash_bilinen_yazma_yollari_reddedilir(komut):
    """Dayanak: CLAUDE.md §5 Koruma katmani; onceki turlarin kapattigi yollar acilmadi."""
    _hook_reddeder("Bash", komut)


MAIN_ACIKLAR = [
    pytest.param("mcp__fs__move_file", {"source": "x.md", "destination": "CLAUDE.md"},
                 marks=XF("`destination` YOL_ALANLARI'nda yok: tasima araci kilitli dosyanin uzerine yazar"), id="destination"),
    pytest.param("mcp__fs__rename", {"old_path": "x.md", "new_path": "CLAUDE.md"},
                 marks=XF("`new_path` YOL_ALANLARI'nda yok"), id="new_path"),
    pytest.param("python_exec", {"code": "open('CLAUDE.md','w').write('x')"},
                 marks=XF("`code` alani KOMUT_ALANLARI'nda yok: kod calistiran arac denetlenmez"), id="code-alani"),
    pytest.param("YeniKabuk", {"commands": ["rm CLAUDE.md"]},
                 marks=XF("`commands` (cogul) alani KOMUT_ALANLARI'nda yok"), id="commands-alani"),
]


@pytest.mark.parametrize("arac,girdi", MAIN_ACIKLAR)
def test_main_taninmayan_alanlarla_yazma_reddedilmeli(monkeypatch, capsys, arac, girdi):
    """Dayanak: madde 1 (bilinmeyen kabuk kanali); hook yalniz 4 komut + 4 yol alanina bakar (fail-open)."""
    cikti = _main(monkeypatch, capsys, {"tool_name": arac, "tool_input": girdi})
    assert '"deny"' in cikti, f"izin verildi: {girdi}"


@pytest.mark.parametrize("arac,girdi", [
    ("str_replace_based_edit_tool", {"command": "create", "path": "CLAUDE.md", "file_text": "x"}),
    ("YeniKabuk", {"command": "echo ok", "script": "rm CLAUDE.md"}),
    ("YeniKabuk", {"cmd": "echo ok", "komut": "Set-Content CLAUDE.md x"}),
    ("Bash", {"command": ["sed", "-i", "s/a/b/", "CLAUDE.md"]}),
    ("Edit", {"path": ".", "filePath": str(KOK / "CLAUDE.md")}),
    ("Read", {"command": "rm CLAUDE.md"}),
    ("ls", {"cmd": "Remove-Item CLAUDE.md"}),
])
def test_main_geri_gerilemeler_savusturulur(monkeypatch, capsys, arac, girdi):
    """Dayanak: madde 1; commit ede0515: butun komut alanlari, liste komut, ilk KILITLI yol alani."""
    assert '"deny"' in _main(monkeypatch, capsys, {"tool_name": arac, "tool_input": girdi})


@pytest.mark.parametrize("arac", ["Read", "Glob", "Grep", "ls", "READ "])
def test_main_salt_okuma_araci_yolu_gecer(monkeypatch, capsys, arac):
    """Dayanak: commit ede0515 (okuma kilidin konusu degil): okuma araclarinin yolu denetlenmez."""
    assert _main(monkeypatch, capsys, {"tool_name": arac, "tool_input": {"file_path": str(KOK / "CLAUDE.md")}}) == ""


# =====================================================================================================
# 2. Yol normallestirmesi
# =====================================================================================================

YOL_ESDEGER = [
    K + " ", "analysis/./h1/../h1/" + "KILIT.md", "analysis\\h1/" + "KILIT.md", "ANALYSIS/H1/KILIT.MD",
    K + "/.", K + "::$DATA", '"' + K + '"', "'" + K + "'", "//analysis//h1//" + "KILIT.md", "./" + K + "..",
    "\\\\?\\" + str(KOK) + "\\analysis\\h1\\" + "KILIT.md",
]


@pytest.mark.parametrize("yol", YOL_ESDEGER)
def test_yol_esdegerleri_kilitli_sayilir(yol):
    """Dayanak: madde 2 (yol_normalle): bosluk, ./, ../, //, \\, buyuk/kucuk harf, ::$DATA, tirnak, UNC."""
    assert hook.kilitli_mi(yol) is not None, yol


@pytest.mark.parametrize("yol", [y for y in YOL_ESDEGER if "'" not in y and '"' not in y])
def test_yol_esdegerine_yonlendirme_reddedilir(yol):
    """Dayanak: madde 2: ayni esdegerlikler komut metninde (kapsar_mi) da gecerli."""
    assert not hook.bash_degerlendir(f"echo x > {yol}").izin, yol


@pytest.mark.parametrize("yol", [
    "analysis/h1/kilitler.md", "analysis/00_veri_denetimi/.rev1213_capasiz.kilit", "cache/" + "KILIT.md",
    "analysis/h1/alt/" + "KILIT.md", "analysis/h1/" + "KILIT.md" + ".bak",
])
def test_yol_benzer_adlar_yanlis_pozitif_vermez(yol):
    """Dayanak: madde 2 (yanlis pozitif yonu): yalnizca tam `analysis/<ad>/KILIT.md` kilitlidir."""
    assert hook.kilitli_mi(yol) is None, yol
    assert hook.bash_degerlendir(f"rm {yol}").izin, yol


@pytest.mark.parametrize("yol", [
    pytest.param("ANALYS~1/h1/" + "KILIT.md", marks=XF("8.3 kisa ad (`ANALYS~1`) ayni dizini gosterir; hook taniyamaz (dusuk onem)"),
                 id="kisa-ad"),
    pytest.param(K + ":akis", marks=XF("`:akis` alternatif akis soneki yalnizca `::` bicimiyle temizlenir (dusuk onem)"),
                 id="tek-iki-nokta-akis"),
])
def test_yol_kisa_ad_ve_alternatif_akis_kilitli_sayilmali(yol):
    """Dayanak: madde 2 (8.3 ve `:stream`). Write/Edit yolu da etkilenir."""
    assert hook.kilitli_mi(yol) is not None, yol


# =====================================================================================================
# 3. Pozitif fiyat
# =====================================================================================================


@pytest.mark.parametrize("deger", [0.0, -0.0, -1e-300, np.float32(0.0), np.float32(-1.0), Decimal("0"),
                                   Decimal("-1"), float("nan"), float("inf"), Decimal("NaN"), Decimal("Infinity")])
def test_fiyat_pozitif_olmayan_degerler_reddedilir(deger):
    """Dayanak: koruma turu madde 2b (`_pozitif_fiyat`): sifir/negatif/sonsuz/NaN; float32 ve Decimal dahil."""
    with pytest.raises(pencere.VeriHatasi):
        pozisyon._pozitif_fiyat(deger, "P0")


def test_fiyat_altnormal_deger_reddedilmeli():
    """Dayanak: madde 2b; `P0 > 0` MAE'nin paydasidir. 1e-320 pozitif ve sonlu ama `1.0/1e-320 = inf`: MAE sonsuz."""
    _reddeder(lambda: pozisyon._pozitif_fiyat(1e-320, "P0"), pencere.VeriHatasi)


test_fiyat_altnormal_deger_reddedilmeli = XF(
    "altnormal fiyat (1e-320) kabul edilir; MAE = max(H,P1)/P0-1 sonsuza gider")(test_fiyat_altnormal_deger_reddedilmeli)


H1_DEGERLER = {"pump_dip": 1.0, "pump_hacim_6": 1e9, "pump_hacim_medyani_180": 1.0, "tepe": 2.0,
               "pump_kapanis": 1.5, "kapanis": 1.0, "yuksek": 1.0}
H3_DEGERLER = {"hacim_medyani_30g": 1.0, "hacim_medyani_120_31": 1e9, "sma50": 10.0, "kapanis_30_once": 10.0,
               "kapanis": 5.0}


def test_fiyat_saglam_degerlerde_kosullar_saglanir():
    """Olumlu kontrol (saldirilarin kurulumu dogru mu): saglam H1/H3 degerleri kosulu saglar."""
    assert sinyal.kosullar_saglandi("H1", yapilandirma("H1"), H1_DEGERLER) is True
    assert sinyal.kosullar_saglandi("H3", yapilandirma("H3"), H3_DEGERLER) is True


@pytest.mark.parametrize("hipotez,degerler,bozuk", [
    pytest.param("H1", H1_DEGERLER, 0.0, id="H1-teyit-kapanisi-sifir"),
    pytest.param("H1", H1_DEGERLER, -5.0, id="H1-teyit-kapanisi-negatif"),
    pytest.param("H3", H3_DEGERLER, 0.0, id="H3-kapanis-sifir"),
    pytest.param("H3", H3_DEGERLER, -5.0, id="H3-kapanis-negatif"),
])
def test_fiyat_sinyal_barinin_kapanisi_pozitif_olmali(hipotez, degerler, bozuk):
    """Dayanak: madde 2b / `sinyal._pozitif` ilkesi (bozuk fiyat kural icat ettirmez, acik hata verir).
    `close[t]=0`, H1 teyidini (`close <= tepe*(1-delta)`) ve H3 dusus trendini (`oran <= -tau`) EN GUCLU biçimde saglar."""
    d = dict(degerler, kapanis=bozuk)
    try:
        sonuc = sinyal.kosullar_saglandi(hipotez, yapilandirma(hipotez), d)
    except pencere.VeriHatasi:
        return
    assert sonuc is False, f"{hipotez}: close[t]={bozuk} bir olay uretti"


test_fiyat_sinyal_barinin_kapanisi_pozitif_olmali = XF(
    "close[t] <= 0 olan bar H1/H3'te OLAY uretir: yalnizca bolenler (_pozitif) denetlenir, kapanis degil")(
    test_fiyat_sinyal_barinin_kapanisi_pozitif_olmali)


def _yuksek_cercevesi(yuksek: float):
    z = pd.date_range(T("2025-03-01"), periods=60, freq="4h")
    return pd.DataFrame({"open_time": z, "high": float(yuksek)}), z


def _gecersizlik(yuksek: float) -> float:
    m, z = _yuksek_cercevesi(yuksek)
    return sinyal.gecersizlik_seviyesi("H2", z[40], mumlar_4h=m, gunluk=None, capa=None,
                                       kume_baslangic=pd.Timestamp(config.KESIF_BASI), donem_baslangic=z[0])


def test_gecersizlik_saglam_veride_yuzde_iki_ustundedir():
    """Olumlu kontrol: high=1.0 -> stop seviyesi 1.02 (on-kayit §5 H2 madde 4)."""
    assert _gecersizlik(1.0) == pytest.approx(1.02)


@pytest.mark.parametrize("yuksek", [0.0, -3.0])
def test_gecersizlik_seviyesi_pozitif_olmayan_tabandan_uretilmemeli(yuksek):
    """Dayanak: madde 2b + CLAUDE.md §2 madde 5 (stop zorunlu): pozitif olmayan stop seviyesi anlamsizdir.
    `_sonlu` yalnizca sonluluga bakar: tum high'lar <= 0 ise seviye 0.0 / negatif doner."""
    try:
        sonuc = _gecersizlik(yuksek)
    except pencere.VeriHatasi:
        return
    assert math.isnan(sonuc), f"stop seviyesi {sonuc} (taban high={yuksek})"


test_gecersizlik_seviyesi_pozitif_olmayan_tabandan_uretilmemeli = XF(
    "gecersizlik_seviyesi pozitiflik denetlemez: high<=0 tabani 0.0/negatif stop seviyesi uretir")(
    test_gecersizlik_seviyesi_pozitif_olmayan_tabandan_uretilmemeli)


# =====================================================================================================
# 4. Kimlik capraz dogrulamasi
# =====================================================================================================

TB = T("2025-03-10 04:00")
BARLAR = [T("2025-03-01") + i * H4 for i in range(60)]          # TB bunlarin arasinda (indeks 55)
SEMBOLLER = ["AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT"]


def test_kimlik_olumlu_kontrol():
    """Kurulum dogru: uyumlu olay + K1 ve K2 adaylariyla ornekleme calisir."""
    k1 = ornekleme.ornekle(k1_adaylari_kur(BARLAR[:10]), olay=tek_olay(TB))
    k2 = ornekleme.ornekle(k2_adaylari_kur(SEMBOLLER, t=TB), olay=tek_olay(TB, sembol="ZZZUSDT"))
    assert (k1.rol, k2.rol) == ("K1", "K2")


@pytest.mark.parametrize("olay_ek", [{"sembol": "ZZZUSDT"}, {"donem_no": 1}, {"yapilandirma": yapilandirma("H2", k=12)}])
def test_kimlik_k1_olay_sembol_donem_yapilandirma_adaylarla_ayni_olmali(olay_ek):
    """Dayanak: on-kayit §6 K1 ("ayni coin, ayni donem, ayni yapilandirma"); `_olayin_kimligi`."""
    adaylar = k1_adaylari_kur(BARLAR[:10])
    olay = tek_olay(TB, **olay_ek)
    _reddeder(lambda: ornekleme.ornekle(adaylar, olay=olay), ValueError)


def test_kimlik_k1_olayin_kendi_bari_aday_olamaz():
    """Dayanak: on-kayit §6 K1; olayin kendi bari K1 kontrolu olamaz."""
    _reddeder(lambda: ornekleme.ornekle(k1_adaylari_kur(BARLAR), olay=tek_olay(TB)), ValueError)


def test_kimlik_k2_olay_bari_adaylarin_bariyla_ayni_olmali():
    """Dayanak: on-kayit §6 K2 ("ayni t barinda")."""
    _reddeder(lambda: ornekleme.ornekle(k2_adaylari_kur(SEMBOLLER, t=TB),
                                        olay=tek_olay(TB + H4, sembol="ZZZUSDT")), ValueError)


def test_kimlik_k2_olayin_kendi_coini_aday_olamaz():
    """Dayanak: on-kayit §6 K2 ("diger coinlerden")."""
    _reddeder(lambda: ornekleme.ornekle(k2_adaylari_kur(SEMBOLLER, t=TB),
                                        olay=tek_olay(TB, sembol="AAAUSDT")), ValueError)


def test_kimlik_k1_ayiklanmamis_adaylar_olaya_yakin_barlar_tasiyabilir():
    """Dayanak: on-kayit §6 K1 ("olaya birincil ufuk mesafesinden yakin olmayan"). `k1_adaylari` ayiklamasi ATLANIRSA:
    olayin hemen yanindaki barlar (olayin pozisyon penceresi icinde) kontrol olarak cekilebilir."""
    adaylar = k1_adaylari_kur([b for b in BARLAR if b != TB])
    olay = tek_olay(TB)
    _reddeder(lambda: ornekleme.ornekle(adaylar, olay=olay), ValueError)


test_kimlik_k1_ayiklanmamis_adaylar_olaya_yakin_barlar_tasiyabilir = XF(
    "`ornekle` yalnizca olayin KENDI barini kontrol eder; ufuk mesafesindeki komsu barlar atlanan ayiklamayla havuza girer")(
    test_kimlik_k1_ayiklanmamis_adaylar_olaya_yakin_barlar_tasiyabilir)


def test_kimlik_k2_olay_sembolu_buyuk_kucuk_harf_degistirilerek_verilemez():
    """Dayanak: on-kayit §6 K2. Olay coini `aaausdt`, aday `AAAUSDT`: ayni coin, farkli yazim (derinlemesine savunma;
    gercek kapi tablo eslemesiyle zaten tam yazim ister, bu yuzden erisilebilirlik DUSUK)."""
    olay = tek_olay(TB, sembol="aaausdt")
    _reddeder(lambda: ornekleme.ornekle(k2_adaylari_kur(SEMBOLLER, t=TB), olay=olay), ValueError)


test_kimlik_k2_olay_sembolu_buyuk_kucuk_harf_degistirilerek_verilemez = XF(
    "`p.sembol in adaylar.ogeler` buyuk/kucuk harfe duyarli: olayin kendi coini farkli yazimla K2 kontrolu olur")(
    test_kimlik_k2_olay_sembolu_buyuk_kucuk_harf_degistirilerek_verilemez)


def test_kimlik_bozulmus_adaylar_olay_ve_pozisyon_reddedilir():
    """Dayanak: on-kayit §4 rev.12 / §6 rev.13: `dataclasses.replace` ile (imza kopyalanarak) bozulan nesneler."""
    adaylar = k2_adaylari_kur(SEMBOLLER, t=TB)
    olay = tek_olay(TB, sembol="ZZZUSDT")
    for bozuk_adaylar in (dataclasses.replace(adaylar, ogeler=adaylar.ogeler + ("SAHTEUSDT",)),
                          dataclasses.replace(adaylar, bar_zamani=TB + H4),
                          dataclasses.replace(adaylar, kume="C2")):
        _reddeder(lambda: ornekleme.ornekle(bozuk_adaylar, olay=olay), ValueError)
    _reddeder(lambda: ornekleme.ornekle(adaylar, olay=dataclasses.replace(olay, zaman=TB + H4)), ValueError)
    sahte_poz = dataclasses.replace(olay.pozisyon, sembol="AAAUSDT")
    _reddeder(lambda: ornekleme.ornekle(adaylar, olay=dataclasses.replace(olay, pozisyon=sahte_poz)), ValueError)


def _dizi_cagrisi(karar, **kimlik):
    y = yapilandirma("H2")
    tam = dict(sembol="AAVEUSDT", kume="KESIF", donem_no=0)
    tam.update(kimlik)
    return dizi.olay_dizisi("H2", y, [TB], config.BAR_4H, birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_4H],
                            kosul=lambda t, capa: True, karar=karar, **tam)


def test_kimlik_olay_dizisi_olumlu_kontrol():
    """Kurulum dogru: kimlik karar'in onayiyla ayniysa tek olay uretilir."""
    karar = _karar_kur("H2", yapilandirma("H2"), "KESIF", "AAVEUSDT", 0)
    assert len(_dizi_cagrisi(karar).olaylar) == 1


@pytest.mark.parametrize("kimlik", [{"sembol": "BBBUSDT"}, {"sembol": "aavEUSDT"}, {"donem_no": 1}])
def test_kimlik_olay_dizisi_adaylarla_uyusmayan_uclu_reddedilir(kimlik):
    """Dayanak: bulgu K-B1 / on-kayit §5 rev.11: dizinin kimligi cagridan gelir, karar'in onayi ona uymali."""
    karar = _karar_kur("H2", yapilandirma("H2"), "KESIF", "AAVEUSDT", 0)
    with pytest.raises(ValueError):
        _dizi_cagrisi(karar, **kimlik)


def test_kimlik_olay_dizisi_kontrol_rolundeki_onay_olay_sayilmaz():
    """Dayanak: on-kayit §6 rev.11 (roller ayridir)."""
    y = yapilandirma("H2")

    def karar(t, capa):
        return pozisyon._test_onayi(hipotez="H2", yapilandirma=y, t=t, rol="K1", sembol="AAVEUSDT",
                                    kume="KESIF", donem_no=0)

    with pytest.raises(ValueError):
        _dizi_cagrisi(karar)


# =====================================================================================================
# 5. Havuz imzasi ve esik sayimi
# =====================================================================================================


def _cift(i=0, *, k1_n=12, k2_n=12):
    y = yapilandirma("H2")
    t = TB + i * H4
    olay = tek_olay(t, yapilandirma=y)
    k1 = ornekleme.ornekle(k1_adaylari_kur(BARLAR[:k1_n]), olay=olay)
    k2 = ornekleme.ornekle(k2_adaylari_kur([f"S{j:02d}USDT" for j in range(k2_n)], t=t), olay=olay)
    return k1, k2


def _yeniden_imzala(havuz):
    return dataclasses.replace(havuz, _imza=ornekleme._havuz_imzasi(havuz))


def test_havuz_olumlu_kontrol():
    """Kurulum dogru: gercek cift sayilir."""
    k1, k2 = _cift()
    assert ornekleme.olay_sayilari([(k1, k2)]).analize_giren == 1
    assert len(k1) == 10 == len(k2)


@pytest.mark.parametrize("alan,deger", [("secilenler", ("X",)), ("aday_sayisi", 99), ("rol", "K2"),
                                        ("alt_tohum_demeti", ("a", "b", "c", "d")), ("tohum", 1), ("genel_tohum", 7)])
def test_havuz_imza_kopyalanarak_bozulan_havuz_reddedilir(alan, deger):
    """Dayanak: madde 3c: `replace` eski `_imza`yi tasir, imza alanlardan yeniden hesaplanir."""
    k1, k2 = _cift()
    bozuk = dataclasses.replace(k1, **{alan: deger})
    _reddeder(lambda: ornekleme.olay_sayilari([(bozuk, k2)]), ValueError, TypeError)


def test_havuz_imzalanmis_olsa_bile_onuncudan_fazla_secilen_reddedilir():
    """Dayanak: on-kayit §6 (10 kontrol): imza dogru olsa da ikinci katman (`havuz_dogrula` boyut denetimi) tutar."""
    k1, k2 = _cift()
    fazla = _yeniden_imzala(dataclasses.replace(k1, secilenler=k1.secilenler + (BARLAR[20],), aday_sayisi=12))
    assert len(fazla.secilenler) == 11
    _reddeder(lambda: ornekleme.olay_sayilari([(fazla, k2)]), ValueError)


def test_havuz_imzalanmis_olsa_bile_aday_sayisindan_fazla_ve_tekrarli_secilen_reddedilir():
    """Dayanak: on-kayit §6 rev.13 (secilen aday sayisini asamaz, ornekleme iadesizdir)."""
    k1, k2 = _cift()
    asiri = _yeniden_imzala(dataclasses.replace(k1, aday_sayisi=3))
    tekrar = _yeniden_imzala(dataclasses.replace(k1, secilenler=(k1.secilenler[0],) * 2))
    for sahte in (asiri, tekrar):
        _reddeder(lambda: ornekleme.olay_sayilari([(sahte, k2)]), ValueError)


def test_havuz_imzalanmis_olsa_bile_rol_sirasi_degistirilemez():
    """Dayanak: madde 5 (cift (K1, K2) sirasinda)."""
    k1, k2 = _cift()
    _reddeder(lambda: ornekleme.olay_sayilari([(k2, k1)]), ValueError)


@pytest.mark.parametrize("bozuk", [None, 5, [()], [(None,)], "cift"])
def test_havuz_olay_sayilari_bicimsiz_girdiyi_reddeder(bozuk):
    """Dayanak: madde 5 (`olay_sayilari`ya ucli/bos demet ya da bicimsiz girdi)."""
    _reddeder(lambda: ornekleme.olay_sayilari(bozuk), TypeError)


def test_havuz_uclu_ve_liste_cifti_reddedilir():
    k1, k2 = _cift()
    for cift in ((k1, k2, k1), [k1, k2], (k1,)):
        _reddeder(lambda: ornekleme.olay_sayilari([cift]), TypeError)


def test_havuz_imzali_sahte_havuz_olay_sayisini_sisirmemeli():
    """Dayanak: madde 3c (K-C6): analize giren olay sayisi F2 esigi (150) ve F3 esigi (100)'tur.
    Bos havuzlu gercek ciftin K1'i `secilenler=("SAHTE",)` ile degistirilir ve imza `_havuz_imzasi` ile yeniden
    hesaplanir (imza gizli bir anahtar degil, herkese acik bir hash)."""
    k1, k2 = _cift(k1_n=0, k2_n=0)
    sahte = _yeniden_imzala(dataclasses.replace(k1, secilenler=("SAHTE",), aday_sayisi=1))
    try:
        sayi = ornekleme.olay_sayilari([(sahte, k2)])
    except (ValueError, TypeError):
        return
    assert sayi.analize_giren == 0, "sahte havuz bos olayi 'analize girdi' yapti"


test_havuz_imzali_sahte_havuz_olay_sayisini_sisirmemeli = XF(
    "imza anahtarsiz hash: `ornekleme._havuz_imzasi` ile yeniden imzalanan sahte havuz olay sayisini sisirir "
    "(kararli atlatma; dikkatsiz degisiklige karsi koruma saglam)")(test_havuz_imzali_sahte_havuz_olay_sayisini_sisirmemeli)


def test_havuz_imzali_sahte_adaylar_kabul_edilmemeli():
    """Dayanak: on-kayit §6 rev.13 (adaylar yalnizca kapidan gecmis onaylardan kurulur). `_aday_imzasi` ile
    yeniden imzalanan, sahte sembol iceren `Adaylar` `aday_dogrula`dan gecer."""
    a = k2_adaylari_kur(SEMBOLLER, t=TB)
    sahte = dataclasses.replace(a, ogeler=a.ogeler + ("SAHTEUSDT",))
    sahte = dataclasses.replace(sahte, _imza=ornekleme._aday_imzasi(sahte))
    _reddeder(lambda: ornekleme.aday_dogrula(sahte), ValueError)


test_havuz_imzali_sahte_adaylar_kabul_edilmemeli = XF(
    "aday imzasi da anahtarsiz hash: yeniden imzalanan sahte `Adaylar` dogrulanir (kararli atlatma)")(
    test_havuz_imzali_sahte_adaylar_kabul_edilmemeli)


# =====================================================================================================
# 6. Kilit kaydi
# =====================================================================================================


def _coz(**alanlar):
    return split.kilit_kaydi_coz(kilit_metni("H2", **alanlar), "H2")


def _kilit_reddeder(**alanlar):
    """KilitBozuk beklenir; baska hata ya da kabul = saldiri basardi."""
    try:
        _coz(**alanlar)
    except split.KilitBozuk:
        return
    except Exception as hata:
        raise AssertionError(f"KilitBozuk beklendi, {type(hata).__name__} geldi: {hata}") from None
    raise AssertionError(f"kayit kabul edildi: {alanlar}")


def test_kilit_olumlu_kontrol():
    """Kurulum dogru: varsayilan kayit cozulur; parametre sirasi farkli / sondaki sifirli yazim ayni demettir."""
    assert _coz().secildi
    assert _coz(parametreler="k=3 phi=0.00030").secildi
    assert not _coz(hukum=split.KILIT_KAPANDI, gerekce="aday yok").secildi


@pytest.mark.parametrize("alan", ["k2_farki", "ortalama_net_getiri"])
@pytest.mark.parametrize("deger", ["inf", "-inf", "nan", "Infinity", "1e-2", "1E5", ".5", "0.", "1_000", "０.５", "٠.٥",
                                   "0x10", "--1", "0.02x", "", "-", "0", "-0.01", "9" * 400])
def test_kilit_ondalik_alanlarda_gecersiz_bicimler_reddedilir(alan, deger):
    """Dayanak: madde 6 / rev.13 madde 4b: duz ASCII ondalik; ustel, inf/nan, Unicode rakam, alt cizgi reddi; > 0 sarti."""
    _kilit_reddeder(**{alan: deger})


@pytest.mark.parametrize("alan", ["olusmus", "analize_giren", "tohum"])
@pytest.mark.parametrize("deger", ["1e3", "-5", "1.5", "１５０", "1_000", "0x96", "", "nan"])
def test_kilit_tamsayi_alanlarda_gecersiz_bicimler_reddedilir(alan, deger):
    """Dayanak: madde 6 (`_tam`): negatif olmayan tamsayi, ASCII."""
    _kilit_reddeder(**{alan: deger})


@pytest.mark.parametrize("tohum", ["20260912", "1", "0"])
def test_kilit_tohum_on_kayit_degeri_olmali(tohum):
    """Dayanak: on-kayit §7 / CLAUDE.md §5 (sabit tohum): kayittaki tohum `config.TOHUM` ile ayni olmali."""
    _kilit_reddeder(tohum=tohum)


@pytest.mark.parametrize("parametreler", [
    "phi=0.0003 k=3 ek=1", "phi=0.0005 k=3", "phi=0.0003", "phi='0.0003' k=3", "phi=0.0003 phi=0.0003 k=3",
    "phi=0.0003% k=3", "phi=abc k=3", "0.0003 3", "phi=0,0003 k=3", "",
])
def test_kilit_parametreler_kimlikle_tutarli_olmali(parametreler):
    """Dayanak: madde 6 (K-C7): `parametreler` `yapilandirma` kimligiyle ayni demeti gostermeli."""
    _kilit_reddeder(parametreler=parametreler)


@pytest.mark.parametrize("kimlik", ["H2:phi=0.0003,k=4", "H1:theta=0.2,delta=0.08", "h2:phi=0.0003,k=3", "H2:phi=0.0003"])
def test_kilit_izgara_disi_kimlik_reddedilir(kimlik):
    """Dayanak: on-kayit §5 rev.11 / madde 6: kimlik izgarada bulunmali."""
    _kilit_reddeder(yapilandirma=kimlik)


def test_kilit_ortalama_net_getiri_secildide_zorunlu():
    """Dayanak: madde 4b (secildi hukmunde `ortalama_net_getiri` zorunlu)."""
    _kilit_reddeder(atla=("ortalama_net_getiri",))


def test_kilit_gerekce_yalnizca_kapandida_zorunlu():
    """Dayanak: madde 4c: kapandida gerekce `-`/eksik olamaz; secildide gerekce eksik olabilir."""
    _kilit_reddeder(hukum=split.KILIT_KAPANDI, gerekce="-")
    _kilit_reddeder(hukum=split.KILIT_KAPANDI, atla=("gerekce",))
    assert _coz(atla=("gerekce",)).secildi
    assert not _coz(hukum=split.KILIT_KAPANDI, gerekce="aday yok", atla=("ortalama_net_getiri",)).secildi


def test_kilit_hukum_ve_hipotez_tutarsizligi_reddedilir():
    """Dayanak: madde 6: hukum tam yazim; dosya baska hipotez icin okunamaz; alan iki kez yazilamaz."""
    _kilit_reddeder(hukum="Yapilandirma Secildi")
    with pytest.raises(split.KilitBozuk):
        split.kilit_kaydi_coz(kilit_metni("H2"), "H3")
    with pytest.raises(split.KilitBozuk):
        split.kilit_kaydi_coz(kilit_metni("H2") + "| tohum | 20260911 |\n", "H2")


def test_kilit_binlik_ayirici_kalibina_uymayan_ondalik_tamsayi_sayilmamali():
    """Dayanak: madde 6 (K-S6 "1.5 -> 15" duzeltmesi). `0.150` binlik kalibina uyar ve 150 okunur: ondalik gorunumlu
    bir deger aday esigini (>= 150) gecirir."""
    _kilit_reddeder(analize_giren="0.150")


test_kilit_binlik_ayirici_kalibina_uymayan_ondalik_tamsayi_sayilmamali = XF(
    "`0.150` regex `\\d{1,3}(\\.\\d{3})+` ile eslesir ve int('0150') = 150 okunur: ondalik gorunumlu deger esigi gecirir")(
    test_kilit_binlik_ayirici_kalibina_uymayan_ondalik_tamsayi_sayilmamali)


def test_kilit_devasa_tamsayi_kilit_bozuk_olarak_reddedilmeli():
    """Dayanak: madde 6 (hata sinifi): kayit cozme hatalari `KilitBozuk` ailesindendir. 5000 haneli tamsayi
    `int()` sinirina takilir ve ciplak ValueError yukari cikar."""
    _kilit_reddeder(olusmus="9" * 5000)


test_kilit_devasa_tamsayi_kilit_bozuk_olarak_reddedilmeli = XF(
    "5000 haneli sayi `int()` hane sinirindan ValueError verir; KilitBozuk degil (onay kosusunun hata sinifi kacar)")(
    test_kilit_devasa_tamsayi_kilit_bozuk_olarak_reddedilmeli)


def _kilidi_depoda_yaz_ve_commitle(depo, push: bool, **alanlar):
    kilit_yaz(depo, "H2", **alanlar)
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "kilit")
    if push:
        git(depo, "push", "-q", "origin", "main")


def test_kilit_ikinci_commitle_degistirilen_kayit_reddedilir(tmp_path):
    """Dayanak: ekleme kurali (madde 6, on-kayit §8 madde 5): kayit yazildiktan sonra ikinci commit ile degistirilemez."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _kilidi_depoda_yaz_ve_commitle(depo, True)
    assert split.kilit_oku("H2").secildi
    _kilidi_depoda_yaz_ve_commitle(depo, False, k2_farki="0.0500")
    _reddeder(lambda: split.kilit_oku("H2"), split.OnayOrtamiHatasi)


def test_kilit_origin_main_elle_ileri_sarilinca_itilmemis_kayit_kabul_edilmemeli(tmp_path):
    """Dayanak: madde 6 (uzak depo simetrisi; CLAUDE.md §3.3): kayit commit edilir ama ITILMEZ, sonra
    `git update-ref refs/remotes/origin/main HEAD` ile yerel izleme referansi ileri sarilir. Referans var oldugu icin
    `_kilit_gecmisini_denetle` fetch yapmaz ve yerel gecmisi 'uzak' sanar."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _kilidi_depoda_yaz_ve_commitle(depo, False)
    git(depo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _reddeder(lambda: split.kilit_oku("H2"), split.OnayOrtamiHatasi)


test_kilit_origin_main_elle_ileri_sarilinca_itilmemis_kayit_kabul_edilmemeli = XF(
    "izleme referansi varsa fetch yapilmaz; elle ileri sarilmis `origin/main` itilmemis kaydi 'uzakta' gosterir")(
    test_kilit_origin_main_elle_ileri_sarilinca_itilmemis_kayit_kabul_edilmemeli)


# =====================================================================================================
# 7. config korumasi
# =====================================================================================================


def test_config_property_fset_ve_dict_yazimi_etkisiz():
    """Dayanak: madde 7: `property.fset` salt okunur; `vars(config)` yazimi okumalari degistirmez."""
    prop = type(config).__dict__["TOHUM"]
    with pytest.raises(AttributeError):
        prop.fset = lambda self, v: None
    asil = config.TOHUM
    vars(config)["TOHUM"] = 1
    try:
        assert config.TOHUM == asil
    finally:
        vars(config)["TOHUM"] = asil


def test_config_izgara_ic_ice_salt_okunur():
    """Dayanak: madde 7: `IZGARA` MappingProxyType + demet; yerinde degistirilemez."""
    with pytest.raises(TypeError):
        config.IZGARA["H2"]["phi"] = (1.0,)
    with pytest.raises(TypeError):
        config.IZGARA["H9"] = {}


def test_config_kopya_modul_korumali_kalir():
    """Dayanak: madde 7 (`copy.copy(config)`): kopya olusursa da sinif korumasi tasinir; olusmazsa da koruma sagdir."""
    try:
        kopya = copy.copy(config)
    except Exception:
        return
    with pytest.raises(config.SabitDegistirilemez):
        kopya.TOHUM = 1


def test_config_metasinif_type_setattr_ile_sinif_degistirilemez():
    """Dayanak: madde 7 / `_SabitModulTuru`: `type(config).__setattr__ = ...` kapali, ama `type.__setattr__(sinif, ...)`
    metasinifin ozel `__setattr__`ini DOGRUDAN atlar."""
    sinif = type(config)
    asil = sinif.__dict__["__setattr__"]
    yeni = types.ModuleType.__setattr__
    try:
        type.__setattr__(sinif, "__setattr__", yeni)
        degisti = sinif.__dict__["__setattr__"] is yeni
    finally:
        type.__setattr__(sinif, "__setattr__", asil)
    assert not degisti, "sinifin __setattr__'i type.__setattr__ ile degistirildi"


test_config_metasinif_type_setattr_ile_sinif_degistirilemez = XF(
    "`type.__setattr__(type(config), ...)` metasinif korumasini atlar: sinif ozel yontemi degisir (tanimlayicilar da silinebilir)")(
    test_config_metasinif_type_setattr_ile_sinif_degistirilemez)


def test_config_veri_tanimlayicisi_type_delattr_ile_silinemez():
    """Dayanak: madde 7: `type.__delattr__(type(config), "KONTROL_SAYISI")` tanimlayiciyi siler; sonra atama serbest kalir."""
    sinif = type(config)
    ozellik = sinif.__dict__["KONTROL_SAYISI"]
    try:
        type.__delattr__(sinif, "KONTROL_SAYISI")
        silindi = "KONTROL_SAYISI" not in sinif.__dict__
    finally:
        if "KONTROL_SAYISI" not in sinif.__dict__:
            type.__setattr__(sinif, "KONTROL_SAYISI", ozellik)
    assert not silindi, "veri tanimlayicisi silindi"


test_config_veri_tanimlayicisi_type_delattr_ile_silinemez = XF(
    "`type.__delattr__` tanimlayiciyi siler; koruma yalnizca `setattr(type(config), ...)` yolunu kapatir")(
    test_config_veri_tanimlayicisi_type_delattr_ile_silinemez)


def test_config_tanimlayici_kapanisi_defaults_ile_degistirilemez():
    """Dayanak: madde 7 (`gc`/kapanis yazimi): deger `_al(self, _deger=deger)` varsayilan argumanindadir;
    `fget.__defaults__` yazilabilir bir islev ozelligidir ve `config.TOHUM` okumasini degistirir."""
    ozellik = type(config).__dict__["TOHUM"]
    asil = ozellik.fget.__defaults__
    try:
        ozellik.fget.__defaults__ = (1,)
        degisti = config.TOHUM == 1
    finally:
        ozellik.fget.__defaults__ = asil
    assert not degisti and config.TOHUM == 20260911, "TOHUM okumasi fget.__defaults__ ile degistirildi"


test_config_tanimlayici_kapanisi_defaults_ile_degistirilemez = XF(
    "okuma degeri islevin `__defaults__`inde; `property.fget.__defaults__ = (x,)` TOHUM okumasini degistirir")(
    test_config_tanimlayici_kapanisi_defaults_ile_degistirilemez)


def test_config_object_setattr_ile_modul_sinifi_degistirilemez():
    """Dayanak: madde 7 / RESULTS §14.33 (BILINEN ACIK): `object.__setattr__(config, "__class__", ModuleType)`."""
    asil = type(config)
    try:
        object.__setattr__(config, "__class__", types.ModuleType)
        korumasiz = type(config) is types.ModuleType
    finally:
        object.__setattr__(config, "__class__", asil)
    assert not korumasiz and type(config) is asil, "modul sinifi degistirildi"


test_config_object_setattr_ile_modul_sinifi_degistirilemez = XF(
    "bilinen acik (RESULTS §14.33): `object.__setattr__(config, '__class__', ModuleType)` tanimlayicilari kaldirir")(
    test_config_object_setattr_ile_modul_sinifi_degistirilemez)


KORUNMAYAN_SABITLER = ["DOLGU_KOSU_ESIGI_BAR", "AZAMI_EKSIK_BAR_BOSLUGU", "TEK_YON_MALIYET", "GIDIS_DONUS_MALIYET",
                       "ASGARI_HACIM_4H", "ASGARI_HACIM_1D", "ASGARI_LISTELEME_YASI_GUN", "DONEM_BASI", "DONEM_SONU",
                       "BOLME_TUZU", "H2_FUNDING_PENCERESI_SAAT", "HIPOTEZ_IZGARASI"]


@pytest.mark.parametrize("ad", [pytest.param(a, marks=XF(
    f"{a} on-kayit/CLAUDE.md degeri ama `_DEGISMEZ_ADLAR`da yok: calisma aninda atanabilir") ) for a in KORUNMAYAN_SABITLER])
def test_config_on_kayit_sabiti_calisma_aninda_degistirilemez(ad):
    """Dayanak: CLAUDE.md §3 madde 4 (esikler sonuctan once sabitlenir) ve §3.7 (maliyet). Her atama GERI ALINIR."""
    asil = getattr(config, ad)
    degisti = False
    try:
        try:
            setattr(config, ad, "bozuk")
            degisti = True
        except config.SabitDegistirilemez:
            pass
    finally:
        if degisti:
            setattr(config, ad, asil)
    assert not degisti, f"config.{ad} yeniden atandi"


@pytest.mark.parametrize("ad,anahtar", [
    pytest.param("BIRINCIL_UFUK", "4h", marks=XF("duz dict: yerinde yazim ad korumasina takilmaz"), id="birincil-ufuk"),
    pytest.param("ILERI_KAYMA_SINIRI", "4h", marks=XF("duz dict"), id="ileri-kayma"),
    pytest.param("IKINCIL_UFUKLAR", "4h", marks=XF("duz dict"), id="ikincil-ufuklar"),
])
def test_config_sozluk_sabitleri_yerinde_degistirilemez(ad, anahtar):
    """Dayanak: on-kayit §4 "Ufuk degerlerinin baglanmasi" (ufuklar yalnizca on-kayitta tanimli). Yerinde yazim GERI ALINIR."""
    sozluk = getattr(config, ad)
    asil = sozluk[anahtar]
    degisti = False
    try:
        try:
            sozluk[anahtar] = 1
            degisti = sozluk[anahtar] == 1
        except TypeError:
            pass
    finally:
        sozluk[anahtar] = asil
    assert not degisti, f"config.{ad}[{anahtar!r}] yerinde degistirildi"


# =====================================================================================================
# 8. Donem siniri ve bar dusurme
# =====================================================================================================


def _seri(n):
    return pd.date_range(T("2025-01-01"), periods=n, freq="4h"), np.ones(n)


@pytest.mark.parametrize("maske", [np.ones(5, bool), [True] * 7, np.ones((10, 1), bool), True, np.ones((2, 5), bool)])
def test_donem_hucreler_tam_yanlis_sekilli_maske_reddedilir(maske):
    """Dayanak: madde 8 (`gercek_bar_maskesi`): `hucreler_tam` hacimle ayni uzunlukta ve tek boyutlu olmali."""
    z, h = _seri(10)
    with pytest.raises(ValueError):
        donem.listeleme_donemleri(z, h, "4h", hucreler_tam=maske)


def test_donem_hucreler_tam_none_ve_liste_esdegerdir():
    """Dayanak: madde 8: None geriye uyumlu; liste maskesi dizi maskesiyle ayni sonuc."""
    z, h = _seri(10)
    assert donem.listeleme_donemleri(z, h, "4h") == donem.listeleme_donemleri(z, h, "4h", hucreler_tam=None)
    assert (donem.listeleme_donemleri(z, h, "4h", hucreler_tam=[True] * 10)
            == donem.listeleme_donemleri(z, h, "4h", hucreler_tam=np.ones(10, bool)))


def test_donem_bozuk_hucreli_uc_barlar_donem_siniri_olamaz():
    """Dayanak: madde 8 (bulgu K-C9, on-kayit §2 rev.12): seride bulunmayan bar sinir gosteremez."""
    z, h = _seri(12)
    bas = np.ones(12, bool)
    bas[0] = False
    son = np.ones(12, bool)
    son[-1] = False
    d1 = donem.listeleme_donemleri(z, h, "4h", hucreler_tam=bas)[0]
    d2 = donem.listeleme_donemleri(z, h, "4h", hucreler_tam=son)[0]
    assert d1.baslangic == z[1]
    assert d2.bitis == z[-2]


def test_donem_bes_bozuk_bar_donemi_bolmez():
    """Dayanak: on-kayit §2 rev.7 esigi (5 bar bolmez) + madde 8; bozuk hucre bar sayisi esigin altinda."""
    z, h = _seri(24)
    tam = np.ones(24, bool)
    tam[8:13] = False
    assert len(donem.listeleme_donemleri(z, h, "4h", hucreler_tam=tam)) == 1


def test_donem_alti_bozuk_bar_silinmis_baristan_farkli_sinifta_olmamali():
    """Dayanak: madde 8 ("olcutun dolgu kosusu ve uzun bosluk siniflandirmasini degistirdigi kurgu"). Ardisik 6 bozuk-hucreli
    bar, kapida seriden DUSER (24 saatlik bosluk, 7 gunden kisa -> donem bolunmez). Ayni barlar `hucreler_tam` ile
    verilince 'dolgu kosusu' (6 ardisik) sayilir ve donemi boler: ayni veri, iki farkli sinif."""
    z, h = _seri(24)
    tam = np.ones(24, bool)
    tam[8:14] = False
    maskeli = donem.listeleme_donemleri(z, h, "4h", hucreler_tam=tam)
    silinmis = donem.listeleme_donemleri(z[tam], h[tam], "4h")
    assert len(maskeli) == len(silinmis), f"maskeli {len(maskeli)} donem, silinmis {len(silinmis)} donem"


test_donem_alti_bozuk_bar_silinmis_baristan_farkli_sinifta_olmamali = XF(
    "6 ardisik bozuk-hucreli bar dolgu kosusu sayilip donemi boler; ayni barlar silinse (24s bosluk) bolmez (yorum farki)")(
    test_donem_alti_bozuk_bar_silinmis_baristan_farkli_sinifta_olmamali)


def _dort_saatlik(zamanlar, **ek):
    return pd.DataFrame({"open_time": pd.DatetimeIndex(zamanlar), **ek})


def test_mum_zamanlari_olumlu_kontrol():
    """Kurulum dogru: close_time'siz bosluklu 4h serisi (en kucuk fark 4s) kabul edilir (bulgu K-C8)."""
    z = pd.DatetimeIndex([T("2025-03-01 00:00"), T("2025-03-01 04:00"), T("2025-03-01 12:00")])
    assert len(pozisyon._mum_zamanlari(_dort_saatlik(z))) == 3


def test_mum_zamanlari_gunluk_cerceve_close_timesiz_reddedilir():
    """Dayanak: madde 8 / on-kayit §4 "Fiyat okuma tabani": saf 1d cercevesi 4h gibi gecemez."""
    z = pd.date_range(T("2025-03-01"), periods=5, freq="1D")
    with pytest.raises(pencere.VeriHatasi):
        pozisyon._mum_zamanlari(_dort_saatlik(z))


def test_mum_zamanlari_gunluk_close_time_ile_reddedilir():
    """Dayanak: madde 8: gercek 1d `close_time` (open + 1g - 1ms) bar suresi 4 saati asar."""
    z = pd.date_range(T("2025-03-01"), periods=5, freq="1D")
    with pytest.raises(pencere.VeriHatasi):
        pozisyon._mum_zamanlari(_dort_saatlik(z, close_time=z + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)))


def test_mum_zamanlari_nat_close_time_reddedilir():
    """Dayanak: madde 8 (NaT'li `close_time` sessizce gecemez)."""
    z = pd.date_range(T("2025-03-01"), periods=3, freq="4h")
    ct = pd.Series(z + H4 - pd.Timedelta(milliseconds=1))
    ct.iloc[1] = pd.NaT
    with pytest.raises(pencere.VeriHatasi):
        pozisyon._mum_zamanlari(_dort_saatlik(z, close_time=ct.to_numpy()))


def test_mum_zamanlari_karisik_gunluk_ve_dort_saatlik_cerceve_reddedilmeli():
    """Dayanak: madde 8 (ardisiklik sarti yalnizca close_time yoksa aranir): gunluk barlar + TEK bitisik 4h cifti
    `en kucuk fark = 4 saat` olcutunu gecer; cerceve cogunlukla 1d iken 4h olarak kabul edilir."""
    z = pd.DatetimeIndex([T("2025-03-01"), T("2025-03-02"), T("2025-03-03 00:00"), T("2025-03-03 04:00")])
    _reddeder(lambda: pozisyon._mum_zamanlari(_dort_saatlik(z)), pencere.VeriHatasi)


test_mum_zamanlari_karisik_gunluk_ve_dort_saatlik_cerceve_reddedilmeli = XF(
    "ardisiklik sarti `min(fark) == 4s`: tek bitisik cift, gunluk agirlikli cerceveyi 4h serisi yapar")(
    test_mum_zamanlari_karisik_gunluk_ve_dort_saatlik_cerceve_reddedilmeli)


def test_mum_zamanlari_dort_saatlik_close_time_yazilmis_gunluk_cerceve_reddedilmeli():
    """Dayanak: madde 8 (K-C8 ticaret-disi: close_time VARken ardisiklik aranmaz): `close_time = open + 4h` yazilmis
    GUNLUK bar sure olcutunu gecer ve izgara olcutu (00:00 acilis) de gunluk barlar icin saglanir."""
    z = pd.date_range(T("2025-03-01"), periods=5, freq="1D")
    _reddeder(lambda: pozisyon._mum_zamanlari(
        _dort_saatlik(z, close_time=z + H4 - pd.Timedelta(milliseconds=1))), pencere.VeriHatasi)


test_mum_zamanlari_dort_saatlik_close_time_yazilmis_gunluk_cerceve_reddedilmeli = XF(
    "close_time varken yalnizca izgara + bar suresi aranir; `open+4h` yazilmis gunluk cerceve 4h serisi sayilir "
    "(K-C8'in bilinen odunu)")(test_mum_zamanlari_dort_saatlik_close_time_yazilmis_gunluk_cerceve_reddedilmeli)
