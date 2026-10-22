#!/usr/bin/env python3
"""Kilitli dosyalara yazmayi engelleyen PreToolUse hook'u.

Amac: F2'de ilk kez getiri hesaplanacak. Metodolojinin sessizce delinmemesi icin
on-kayit, veri bolmesi, onay kaydi ve proje anayasasi dosyalari yalnizca
kullanicinin acik izniyle degistirilebilir (CLAUDE.md §3.2-3.4).

Calisma bicimi:
  - Write / Edit / NotebookEdit: hedef dosya yolu kilitliyse reddeder.
  - KOMUT TASIYAN her arac (Bash, PowerShell, bilinmeyen bir kabuk araci):
    komut metni denetlenir. Arac adi BEYAZ LISTEYE baglanmaz; `tool_input`
    icinde komut alani varsa denetim yapilir, cunku yeni bir kabuk araci
    eklendiginde sessizce atlanmasi korumanin tamamini deler. Arac adi yalnizca
    hangi LEHCENIN (bash / powershell) ayristirildigini secer; taninmayan bir
    arac adinda her iki lehce de denetlenir ve biri reddediyorsa komut reddedilir.
  - Bash: komut metni kilitli bir dosyaya YAZMA niyeti tasiyorsa reddeder
    (yonlendirme, sed -i, mv, cp hedefi, rm, truncate, tee, agac degistiren git
    alt komutlari). Salt okuma komutlari (cat, git log, git show, grep, head,
    tail ...) gecer. Sinifi belirlenemeyen ve kilitli dosyayi anan komutlar
    TEMKINLI olarak reddedilir; gerekce bunu acikca soyler.
  - PowerShell: yazan cmdlet'ler (`Set-Content`, `Add-Content`, `Out-File`,
    `Clear-Content`, `Remove-Item`, `Move-Item`, `Rename-Item`, `New-Item`,
    `Copy-Item` hedefi, `Tee-Object`, `Export-Csv` ...), `>`/`>>` yonlendirmesi
    ve bunlarin takma adlari (`sc`, `ri`, `del`, `mv`, `cp` ...) reddedilir;
    salt okuma cmdlet'leri (`Get-Content`, `Select-String`, `Get-ChildItem`,
    `Test-Path` ...) gecer. Taninmayan cmdlet kilitli dosyayi aniyorsa temkinli
    reddedilir.
  - Calisan Python kodunu ETKILEMEZ. `data/split.py` icindeki `onay_kaydet`
    ONAY_KAYDI.md'ye yazmaya devam eder; o bir arac cagrisi degil.
  - `SHORT_LAB_KILIT_ACIK=1` ayarliysa her seye izin verir.

Bilinen sinirlar (bilincli):
  - Kilitli dosyayi ADIYLA anmadan yazan bir betik (`python yama.py`)
    yakalanamaz; komut metninde iz yoktur.
  - Cift tirnak icindeki komut ikamesi (`echo "$(sed -i ... X)"`) yalnizca
    kilitli ad geciyorsa temkinli reddedilir.

Girdi : stdin uzerinden JSON (tool_name, tool_input)
Cikti : izin veriyorsa sessiz cikis; engelliyorsa PreToolUse deny JSON'u.

Ek bagimlilik kullanmaz; yalnizca standart kutuphane.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

# Proje koku: bu betik .claude/hooks/ altinda durur.
KOK = Path(__file__).resolve().parents[2]

# Gerekce metni Turkce; konsol kodlamasi bozmasin diye cikti UTF-8'e sabitlenir.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Kilitli dosyalar, proje kokune gore. Glob karakteri (*?[) iceren girdiler
# DESEN olarak eslesir; digerleri tam yol olarak.
KILITLI = (
    "PREREGISTRATION.md",
    "data/split.csv",
    "data/universe.csv",
    # Evren kurulumunun girdisi; universe.csv ile ayni statude (bir kez uretilir).
    "data/exchange_info_anlik.json",
    "ONAY_KAYDI.md",
    "CLAUDE.md",
    # F2'nin kilitledigi yapilandirma: her hipotezin kendi dosyasi, olusturuldugu
    # andan itibaren (CLAUDE.md §5, on-kayit §8 madde 5). Desen bilerek
    # `analysis/` altina baglidir: depo kokundeki bir KILIT.md KORUNMAZ, cunku
    # kilit yalnizca on-kaydin adini verdigi yol icin yazilidir.
    "analysis/*/KILIT.md",
)

ACMA_DEGISKENI = "SHORT_LAB_KILIT_ACIK"


def _desen_mi(kalip: str) -> bool:
    """Kilitli girdi tam yol degil, glob deseni mi?"""
    return any(c in kalip for c in "*?[")


# NTFS veri akisi (`dosya::$DATA`) ayni dosyayi gosterir.
_AKIS_SONEKI = re.compile(r"::\$?[A-Za-z0-9_]+$")


def yol_normalle(yol: str) -> str:
    """Yolu ESLESTIRME ONCESI normalize eder (madde 1b).

    Kapatilan esdegerlikler: ters egik cizgi, `./`, `../`, `//`, sondaki nokta ve
    bosluk (Win32 `GetFullPathName` bunlari yok sayar), NTFS veri akisi soneki
    (`::$DATA`). Buyuk/kucuk harf burada DEGISTIRILMEZ; cagiran yere gore ya
    `casefold` uygulanir ya da regex `IGNORECASE` ile eslesir.

    `Path.resolve()` yetmez: Windows'ta sondaki noktayi temizlemedigi olculdu
    (sizinti turu), yani `analysis/h1/KILIT.md.` ayni dosyayi gosterdigi halde
    desene uymuyordu. Saf fonksiyon; dosya sistemine dokunmaz.
    """
    metin = yol.strip().strip('"').strip("'")
    metin = metin.replace("\\", "/")
    metin = _AKIS_SONEKI.sub("", metin)
    onek = ""
    surucu = re.match(r"^[A-Za-z]:(?=/|$)", metin)
    if surucu:
        onek, metin = surucu.group(0), metin[surucu.end():]
    if metin.startswith("/"):
        onek += "/"
    parcalar: list[str] = []
    for parca in metin.split("/"):
        if parca in ("", "."):
            continue                      # `//` ve `./`
        if parca == "..":
            if parcalar:
                parcalar.pop()            # `a/../b` -> `b`
            continue
        parcalar.append(parca.rstrip(". \t"))
    return onek + "/".join(parcalar)


def _anma_deseni(kalip: str) -> re.Pattern[str]:
    """Desen girdisi icin METINDE arama regexi.

    Yol bicimi korunur: `analysis/*/KILIT.md` yalnizca `analysis/<ad>/KILIT.md`
    seklinde anildiginda eslesir, yalin `KILIT.md` eslesmez. Hem `/` hem `\\`
    ayiricisi kabul edilir.

    Dosya adi HARF HARF eslesir (buyuk/kucuk duyarli) ve `*` tek bir yol
    parcasini karsilar. Gerekce: desen YALNIZCA adi tam `KILIT.md` olan yollari
    korur; `.kilit` uzantili bir dosya (ör. kosu kilidi `.rev1213_capasiz.kilit`)
    ya da `kilit` iceren baska bir ad korumaya girmez. Bu yanlis pozitif, kosu
    kilidi artiklarinin silinmesini engelliyordu.

    Dosya adi TAM eslesir ama buyuk/kucuk harf duyarsizdir (madde 1b, bulgu K-C2):
    Windows'ta `analysis/h1/kilit.md` ayni dosyayi gosterdigi icin o yazim da
    korunur. Eski yanlis pozitif (`.rev1213_capasiz.kilit`) geri gelmez, cunku
    eslesme adin TAMAMINI ister, `kilit` alt dizgisini degil.
    """
    parcalar = []
    for p in kalip.split("/"):
        if _desen_mi(p):
            parcalar.append(r"[^/\\\s]+")
        else:
            parcalar.append(re.escape(p))
    return re.compile(r"[/\\]".join(parcalar), re.IGNORECASE)


def _yol_deseni(kalip: str) -> re.Pattern[str]:
    """Desen girdisi icin YOL regexi: `*` tek bir yol parcasini karsilar.

    `fnmatch` yerine regex kullanilir, cunku `fnmatch`te `*` `/` karakterini de
    karsilar: `analysis/*` deseni `analysis/00_veri_denetimi/.rev1213_capasiz.kilit`
    yolunu da eslestiriyordu ve kilitli olmayan bir dosya korumaya giriyordu.
    """
    parcalar = [r"[^/\\]+" if _desen_mi(p) else re.escape(p) for p in kalip.split("/")]
    return re.compile(r"(?:^|.*[/\\])" + r"[/\\]".join(parcalar) + r"$", re.IGNORECASE)


def _dizin_kapsar(dizin: str, kalip: str) -> bool:
    """`dizin` argumani, desen girdisinin UST DIZINLERINDEN biri mi?

    Parca parca karsilastirilir; desenin `*` parcasi tek bir parcayi karsilar.
    Dizin adlari buyuk/kucuk duyarsiz (dizin adi korumanin konusu degil), ama
    karsilastirma yol parcasi duzeyindedir: `analysis` kapsar, `analysis/h1`
    kapsar, `analysis/h1/baska.md` KAPSAMAZ.
    """
    arg = [p for p in yol_normalle(dizin).strip("/").split("/") if p not in ("", ".")]
    hedef = kalip.split("/")[:-1]          # dosya adi haric ust dizinler
    if not arg or len(arg) > len(hedef):
        return False
    for verilen, beklenen in zip(arg, hedef):
        if _desen_mi(beklenen):
            continue                        # `*`: hangi hipotez dizini olursa olsun
        if verilen.lower() != beklenen.lower():
            return False
    return True


# Desen girdileri icin: metinde anma regexi ve yol regexi.
DESEN_ANMA = {k: _anma_deseni(k) for k in KILITLI if _desen_mi(k)}
DESEN_TAM = {k: _yol_deseni(k) for k in KILITLI if _desen_mi(k)}

# --- Bash komut siniflari ----------------------------------------------------

# Dosya icerigini degistirmeyen komutlar.
OKUMA_KOMUTLARI = frozenset(
    {
        "cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "less", "more",
        "wc", "diff", "cmp", "ls", "stat", "file", "md5sum", "sha1sum",
        "sha256sum", "echo", "printf", "test", "[", "sort", "uniq", "cut", "tr",
        "nl", "od", "xxd", "column", "jq", "realpath", "dirname", "basename",
    }
)

# Dosya iceriginin yerini degistiren ya da silen komutlar. Arguman kilitli
# dosyayi kapsiyorsa reddedilir.
YAZMA_KOMUTLARI = frozenset(
    {
        "mv", "rm", "unlink", "truncate", "tee", "touch", "dd", "shred", "ln",
        "install", "rsync", "chmod", "chown",
    }
)

# Calisma agacini degistiren git alt komutlari. Kilitli dosyayi ADIYLA anmasalar
# da (`git checkout .`, `git apply yama.patch`) kilitli dosyalari degistirebilirler,
# bu yuzden her zaman reddedilirler (dar istisnalar asagida).
GIT_AGAC_YAZMA = frozenset(
    {
        "checkout", "restore", "apply", "stash", "clean", "am", "cherry-pick",
        "merge", "rebase", "pull", "switch", "revert",
    }
)

# Dosya icerigini degistirmeyen git alt komutlari. `add` ve `commit` yalnizca
# kayit tutar; kilitli dosyanin icerigine dokunmaz.
GIT_OKUMA = frozenset(
    {
        "log", "show", "diff", "status", "blame", "grep", "ls-files", "cat-file",
        "rev-parse", "check-ignore", "shortlog", "describe", "add", "commit",
        "branch", "tag", "remote", "config", "fetch", "push",
    }
)

# Arguman kilitli dosyayi kapsiyorsa reddedilen git alt komutlari.
GIT_DOSYA_YAZMA = frozenset({"mv", "rm"})

# Komutun onune gelip asil komutu degistirmeyen sarmalayicilar.
SARMALAYICILAR = frozenset({"sudo", "time", "nohup", "command", "builtin", "exec", "nice"})

# Komut ayiricilari (shlex noktalama tokenlari).
AYIRICILAR = frozenset({"&&", "||", ";", ";;", "|", "|&", "&", "\n", "(", ")"})

# Dosyaya yazan yonlendirme operatorleri.
YONLENDIRME = frozenset({">", ">>", ">|", "&>", "&>>", "<>"})

HEREDOC_DESENI = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


@dataclass(frozen=True)
class Karar:
    """Bash komutu degerlendirmesinin sonucu."""

    izin: bool
    kalip: str | None = None
    neden: str = ""
    belirsiz: bool = False  # sinif belirlenemedi, temkinli reddedildi


IZIN = Karar(izin=True)


# --- Yol eslestirme ----------------------------------------------------------


def kilitli_mi(yol: str) -> str | None:
    """Yol kilitli dosyalardan birine mi isaret ediyor? Eslesen kalibi doner.

    Iki asamali eslestirme yapilir, cunku yol farkli bicimlerde gelebilir
    (Windows mutlak yolu, POSIX bicimi `/d/...`, ya da goreli yol):
      1. Mutlak yol karsilastirmasi (normal durum),
      2. Normallestirilmis son-ek karsilastirmasi (yedek).
    Yedek asama bir koruma katmani icin bilerek genistir: baska bir dizindeki
    ayni adli dosya da engellenir. Yanlis engelleme zararsizdir (kullanici kilidi
    acabilir); yanlis izin vermek degildir.
    """
    normal = yol_normalle(yol)
    try:
        mutlak = Path(normal).resolve()
        goreli_ham = None
        try:
            goreli_ham = mutlak.relative_to(KOK).as_posix()
        except ValueError:
            pass
        for kalip in KILITLI:
            if _desen_mi(kalip):
                if goreli_ham is not None and DESEN_TAM[kalip].search(goreli_ham):
                    return kalip
            elif mutlak == (KOK / kalip).resolve():
                return kalip
    except Exception:
        pass

    ham = normal.rstrip("/")
    duz = ham.lower()
    for kalip in KILITLI:
        hedef = kalip.lower()
        if _desen_mi(kalip):
            if DESEN_TAM[kalip].search(ham):
                return kalip
        elif duz == hedef or duz.endswith("/" + hedef):
            return kalip
    return None


def _metin_normalle(metin: str) -> str:
    """Komut METNINDEKI yol yazimlarini normalize eder (madde 1b).

    `yol_normalle` tek bir yol icindir; burada metnin tamami taranir, bu yuzden
    donusumler yol parcasi duzeyinde ve yineleyerek uygulanir. Fazla normalleme
    zararsizdir: sonuc yalnizca "kilitli dosya ANILIYOR mu" sorusunda kullanilir
    ve yanlis anma temkinli redde goturur (hook aciklamasi).
    """
    m = metin.replace("\\", "/")
    m = re.sub(r"::\$?[A-Za-z0-9_]+", "", m)
    m = re.sub(r"/{2,}", "/", m)
    m = re.sub(r"/\./", "/", m)
    onceki = None
    while onceki != m:                      # `a/../b` -> `b`, ic ice yazimlar icin yinele
        onceki = m
        m = re.sub(r"[^/\s\"']+/\.\./", "", m)
    return re.sub(r"\.+(?=[\s\"';|&)]|$)", "", m)


def _ad_geciyor_mu(metin: str) -> str | None:
    """Metinde kilitli bir dosyanin adi geciyor mu? (buyuk-kucuk harf duyarsiz)

    Tam yol girdileri icin dosya adi yeter. Desen girdileri icin yolun tamami
    aranir: `KILIT.md` tek basina anilmis olmak yetmez, `analysis/<ad>/KILIT.md`
    bicimi gerekir.

    Arama hem HAM metinde hem de normallestirilmis kopyada yapilir (madde 1b),
    boylece `analysis/h1/../h1/KILIT.md`, `analysis//h1/KILIT.md`,
    `analysis\\h1\\KILIT.md` ve `KILIT.md.` yazimlari da anma sayilir.
    """
    for aday in (metin, _metin_normalle(metin)):
        kucuk = aday.lower()
        for kalip in KILITLI:
            if _desen_mi(kalip):
                # Desen girdisinde dosya adi TAM eslesir (buyuk/kucuk duyarsiz): `.kilit`
                # uzantili ya da `kilit` iceren baska adlar korumaya girmez.
                if DESEN_ANMA[kalip].search(aday):
                    return kalip
            elif kalip.rsplit("/", 1)[-1].lower() in kucuk:
                return kalip
    return None


def kapsar_mi(arguman: str) -> str | None:
    """Bir yazma komutunun argumani kilitli bir dosyayi kapsiyor mu?

    Kapsama uc bicimde olur:
      - arguman dosyanin kendisidir (`CLAUDE.md`, `of=data/split.csv`),
      - arguman dosyayi iceren bir dizindir (`data`, `.`, proje koku),
      - arguman dosyayla eslesen bir glob desenidir (`*.md`, `data/*`).
    """
    if not arguman:
        return None
    duz = arguman.strip()
    if "=" in duz and not duz.startswith("-"):  # dd of=..., --file=...
        duz = duz.split("=", 1)[1]
    elif duz.startswith("--") and "=" in duz:
        duz = duz.split("=", 1)[1]
    duz = yol_normalle(duz)          # madde 1b: `./`, `../`, `//`, `\`, sondaki nokta, `::$DATA`
    kucuk = duz.lower()

    # 1) Dosyanin kendisi: tam goreli yol ya da ayni dosya adi
    #    (desen girdilerinde yalin dosya adi YETMEZ, yolun bicimi gerekir)
    for kalip in KILITLI:
        if _desen_mi(kalip):
            if DESEN_TAM[kalip].search(duz):
                return kalip
            continue
        ad = kalip.lower()
        dosya_adi = ad.rsplit("/", 1)[-1]
        if kucuk in (ad, dosya_adi) or kucuk.endswith("/" + ad) or kucuk.endswith("/" + dosya_adi):
            return kalip

    # 2) Dosyayi iceren dizin
    dizin = kucuk.rstrip("/")
    while dizin.startswith("./"):
        dizin = dizin[2:]
    kok_adi = KOK.name.lower()
    for kalip in KILITLI:
        ust = kalip.lower().rsplit("/", 1)[0] if "/" in kalip else ""
        if dizin in ("", ".", "*"):
            return kalip
        if dizin == kok_adi or dizin.endswith("/" + kok_adi):
            return kalip
        if _desen_mi(kalip):
            # Desenin ust dizini de desenli olabilir (`analysis/*`): arguman bu ust
            # dizinlerden biriyse kapsar. Karsilastirma PARCA PARCA yapilir; `fnmatch`
            # kullanilmaz, cunku oradaki `*` `/` karakterini de karsilar ve
            # `analysis/<dizin>/<baska dosya>` yollari da kapsanmis sayilirdi.
            if _dizin_kapsar(dizin, kalip):
                return kalip
            sabit_kok = ust.split("/", 1)[0]
            if sabit_kok and dizin.endswith("/" + sabit_kok):
                return kalip
            continue
        if ust and (dizin == ust or dizin.endswith("/" + ust)):
            return kalip

    # 3) Glob deseni
    if any(c in duz for c in "*?["):
        for kalip in KILITLI:
            aday = kalip.lower()
            desen = kucuk.lstrip("./")
            if fnmatch.fnmatch(aday, desen) or fnmatch.fnmatch(aday.rsplit("/", 1)[-1], desen):
                return kalip
    return None


# --- Bash ayristirma ---------------------------------------------------------


def heredoc_ayikla(komut: str) -> tuple[str, list[tuple[str, str]]]:
    """Heredoc govdelerini komut metninden cikarir.

    Doner: (govdesiz metin, [(heredoc'un sahibi olan satir, govde)]).
    Govde, bir betige ya da commit mesajina girdi olan ham metindir; komut
    olarak ayristirilmaz.
    """
    satirlar = komut.split("\n")
    cikti: list[str] = []
    govdeler: list[tuple[str, str]] = []
    i = 0
    while i < len(satirlar):
        satir = satirlar[i]
        cikti.append(satir)
        i += 1
        for eslesme in HEREDOC_DESENI.finditer(satir):
            tire, ayrac = eslesme.group(1), eslesme.group(3)
            govde: list[str] = []
            while i < len(satirlar):
                aday = satirlar[i].rstrip("\r")
                if tire:
                    aday = aday.lstrip("\t")
                i += 1
                if aday == ayrac:
                    break
                govde.append(satirlar[i - 1])
            govdeler.append((satir, "\n".join(govde)))
    return "\n".join(cikti), govdeler


def tokenlara_ayir(metin: str) -> list[str]:
    """Kabuk benzeri tokenlara ayirir; satir sonu komut ayiricisidir.

    Ters egik cizgi KACIS KARAKTERI SAYILMAZ (madde 1b): bu ortamda yollar
    `analysis\\h1\\KILIT.md` bicimiyle de yazilir ve posix kacisi onu
    `analysish1KILIT.md` tokenina cevirip eslesmeyi delerdi. Tirnak islemesi
    korunur; `\\;` gibi kacislar ayri token olarak gorunur, bu yalnizca
    siniflandirmayi temkinli yonde etkiler.
    """
    lex = shlex.shlex(metin, posix=True, punctuation_chars=";&|<>()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.escape = ""
    return list(lex)


def parcalara_bol(tokenlar: list[str]) -> list[list[str]]:
    """Token listesini komut ayiricilarindan boler."""
    parcalar: list[list[str]] = [[]]
    for token in tokenlar:
        if token in AYIRICILAR:
            parcalar.append([])
        else:
            parcalar[-1].append(token)
    return [p for p in parcalar if p]


def _yonlendirmeleri_ayir(parca: list[str]) -> tuple[list[str], list[str]]:
    """Parcadan yonlendirme hedeflerini ayirir. Doner: (argumanlar, hedefler)."""
    argumanlar: list[str] = []
    hedefler: list[str] = []
    i = 0
    while i < len(parca):
        token = parca[i]
        if token in YONLENDIRME and i + 1 < len(parca):
            hedefler.append(parca[i + 1])
            i += 2
            continue
        if token == ">&" and i + 1 < len(parca):
            if not parca[i + 1].isdigit() and parca[i + 1] != "-":
                hedefler.append(parca[i + 1])  # >&dosya
            i += 2
            continue
        if token in ("<", "<<", "<<<", "<&"):
            i += 2  # okuma yonlendirmesi; hedefi arguman sayilmaz
            continue
        argumanlar.append(token)
        i += 1
    return argumanlar, hedefler


def _asil_komut(argumanlar: list[str]) -> list[str]:
    """Ortam atamalarini ve sarmalayicilari atlar."""
    i = 0
    while i < len(argumanlar):
        token = argumanlar[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            i += 1
            continue
        if token in SARMALAYICILAR:
            i += 1
            continue
        break
    return argumanlar[i:]


def _konumsallar(argumanlar: list[str]) -> list[str]:
    """Secenek olmayan argumanlar (`--` sonrasindakiler dahil)."""
    sonuc: list[str] = []
    secenek_bitti = False
    for token in argumanlar:
        if secenek_bitti:
            sonuc.append(token)
        elif token == "--":
            secenek_bitti = True
        elif not token.startswith("-") or token == "-":
            sonuc.append(token)
    return sonuc


def _kapsayan(argumanlar: list[str]) -> str | None:
    for token in argumanlar:
        kalip = kapsar_mi(token)
        if kalip:
            return kalip
    return None


def _git_alt_komutu(argumanlar: list[str]) -> tuple[str | None, list[str]]:
    """`git [-C dir] [-c k=v] alt ...` -> (alt, alt komutun argumanlari)."""
    i = 1
    while i < len(argumanlar):
        token = argumanlar[i]
        if token in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token, argumanlar[i + 1 :]
    return None, []


def _red(kalip: str | None, neden: str, belirsiz: bool = False) -> Karar:
    return Karar(izin=False, kalip=kalip, neden=neden, belirsiz=belirsiz)


def _parca_degerlendir(parca: list[str]) -> Karar:
    """Tek bir komut parcasini degerlendirir."""
    argumanlar, hedefler = _yonlendirmeleri_ayir(parca)

    for hedef in hedefler:
        kalip = kapsar_mi(hedef)
        if kalip:
            return _red(kalip, f"yonlendirme kilitli dosyaya yaziyor: {hedef}")

    argumanlar = _asil_komut(argumanlar)
    if not argumanlar:
        return IZIN

    komut = argumanlar[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if komut.endswith(".exe"):
        komut = komut[:-4]
    geri = argumanlar[1:]
    anilan = _ad_geciyor_mu(" ".join(geri))

    # Cift tirnak icinde komut ikamesi: icerik ayristirilmadi, temkinli ol.
    ikameli = any(("$(" in t or "`" in t) and _ad_geciyor_mu(t) for t in geri)

    if komut == "git":
        alt, alt_arg = _git_alt_komutu(argumanlar)
        if alt is None:
            return IZIN
        if alt in GIT_AGAC_YAZMA:
            konum = _konumsallar(alt_arg)
            dal_olustur = (
                (alt == "checkout" and any(t in ("-b", "-B") for t in alt_arg) and len(konum) == 1)
                or (alt == "switch" and any(t in ("-c", "-C") for t in alt_arg) and len(konum) == 1)
            )
            if alt == "stash" and konum[:1] in (["list"], ["show"]):
                return IZIN
            if dal_olustur:
                return IZIN
            return _red(
                anilan or KILITLI[0],
                f"`git {alt}` calisma agacini degistirir ve kilitli dosyalara dokunabilir",
            )
        if alt == "reset":
            if any(t in ("--hard", "--merge", "--keep") for t in alt_arg):
                return _red(anilan or KILITLI[0], f"`git reset {' '.join(alt_arg)}` calisma agacini degistirir")
            return IZIN
        if alt in GIT_DOSYA_YAZMA:
            kalip = _kapsayan(_konumsallar(alt_arg))
            return _red(kalip, f"`git {alt}` kilitli dosyayi tasiyor/siliyor") if kalip else IZIN
        if alt in GIT_OKUMA:
            return IZIN
        if anilan:
            return _red(anilan, f"`git {alt}` sinifi belirlenemedi", belirsiz=True)
        return IZIN

    if komut == "sed":
        yerinde = any(
            t.startswith("--in-place") or (t.startswith("-") and not t.startswith("--") and "i" in t[1:])
            for t in geri
        )
        if yerinde:
            kalip = _kapsayan(_konumsallar(geri))
            if kalip:
                return _red(kalip, "`sed -i` kilitli dosyayi yerinde degistiriyor")
        elif ikameli:
            return _red(anilan, "komut ikamesi icinde kilitli dosya aniliyor", belirsiz=True)
        return IZIN

    if komut in ("awk", "gawk"):
        yerinde = any(t == "inplace" or t.startswith("-i") for t in geri)
        if yerinde:
            kalip = _kapsayan(_konumsallar(geri))
            if kalip:
                return _red(kalip, "`awk -i inplace` kilitli dosyayi yerinde degistiriyor")
        return IZIN

    if komut == "cp":
        konum = _konumsallar(geri)
        if konum:
            kalip = kapsar_mi(konum[-1])
            if kalip:
                return _red(kalip, "`cp` kilitli dosyanin uzerine yaziyor")
        return IZIN

    if komut in YAZMA_KOMUTLARI:
        kalip = _kapsayan(_konumsallar(geri)) or _kapsayan(geri)
        if kalip:
            return _red(kalip, f"`{komut}` kilitli dosyayi degistiriyor ya da siliyor")
        return IZIN

    if komut in OKUMA_KOMUTLARI:
        if ikameli:
            return _red(anilan, "komut ikamesi icinde kilitli dosya aniliyor", belirsiz=True)
        return IZIN

    # Yorumlayicilar (python, bash, node ...), dongu anahtar sozcukleri, find,
    # xargs ve taninmayan her sey: kilitli dosyayi aniyorsa temkinli red.
    if anilan:
        return _red(anilan, f"`{komut}` komutunun sinifi belirlenemedi", belirsiz=True)
    return IZIN


def bash_degerlendir(komut: str) -> Karar:
    """Bir Bash komutunun kilitli dosyalara yazma niyeti tasiyip tasimadigini soyler.

    Saf fonksiyon: dosya sistemine dokunmaz, komutu calistirmaz.
    """
    govdesiz, govdeler = heredoc_ayikla(komut)

    # Heredoc govdesi bir betige girdi oluyorsa (python - <<EOF) ve kilitli
    # dosyayi aniyorsa, betigin ne yapacagi bilinemez. Commit mesaji istisnadir.
    for sahip, govde in govdeler:
        kalip = _ad_geciyor_mu(govde)
        if kalip and not re.search(r"\bgit\s+(commit|tag)\b", sahip):
            return _red(kalip, "heredoc icerigi kilitli dosyayi aniyor; betik olarak calisabilir", belirsiz=True)

    try:
        tokenlar = tokenlara_ayir(govdesiz)
    except ValueError:
        kalip = _ad_geciyor_mu(govdesiz)
        if kalip:
            return _red(kalip, "komut ayristirilamadi (kapanmamis tirnak)", belirsiz=True)
        return IZIN

    for parca in parcalara_bol(tokenlar):
        karar = _parca_degerlendir(parca)
        if not karar.izin:
            return karar
    return IZIN


# --- PowerShell --------------------------------------------------------------

# Dosya icerigini DEGISTIREN cmdlet'ler. Argumanlardan biri kilitli dosyayi
# kapsiyorsa reddedilir.
PS_YAZMA = frozenset(
    {
        "set-content", "add-content", "out-file", "clear-content", "remove-item",
        "move-item", "rename-item", "new-item", "tee-object", "export-csv",
        "export-clixml", "set-itemproperty", "clear-item", "write-ps1xml",
    }
)

# Hedefi yalnizca VARIS yolu olan cmdlet'ler (kaynagin kilitli olmasi yazma degildir).
PS_KOPYALAMA = frozenset({"copy-item"})

# Dosya icerigini degistirmeyen cmdlet'ler.
PS_OKUMA = frozenset(
    {
        "get-content", "select-string", "get-childitem", "get-item", "test-path",
        "resolve-path", "join-path", "split-path", "measure-object", "select-object",
        "sort-object", "where-object", "foreach-object", "compare-object",
        "format-table", "format-list", "write-output", "write-host", "out-host",
        "out-null", "out-string", "get-location", "get-help", "get-date",
        "convertfrom-json", "convertto-json", "get-filehash", "import-csv",
    }
)

# PowerShell takma adlari (alias) -> gercek cmdlet.
PS_TAKMA_ADLAR = {
    "sc": "set-content", "set": "set-content", "ac": "add-content",
    "clc": "clear-content", "ri": "remove-item", "rm": "remove-item",
    "rmdir": "remove-item", "del": "remove-item", "erase": "remove-item",
    "rd": "remove-item", "mi": "move-item", "move": "move-item", "mv": "move-item",
    "ren": "rename-item", "rni": "rename-item", "rnp": "rename-itemproperty",
    "ni": "new-item", "cpi": "copy-item", "copy": "copy-item", "cp": "copy-item",
    "tee": "tee-object", "epcsv": "export-csv", "sp": "set-itemproperty",
    "gc": "get-content", "cat": "get-content", "type": "get-content",
    "sls": "select-string", "ls": "get-childitem", "dir": "get-childitem",
    "gci": "get-childitem", "gi": "get-item", "gl": "get-location",
    "echo": "write-output", "write": "write-output", "ipcsv": "import-csv",
    "select": "select-object", "sort": "sort-object", "where": "where-object",
    "foreach": "foreach-object", "measure": "measure-object",
}

# Komutun onune gelip asil cmdlet'i degistirmeyen PowerShell sarmalayicilari.
PS_SARMALAYICILAR = frozenset({"&", ".", "invoke-expression", "iex", "start-process", "sudo"})

# `-Destination`/`-LiteralPath`/`-Path` gibi adlandirilmis parametrelerin degeri
# zaten token olarak gorulur; ayrica VARIS parametresi adiyla aranir.
PS_VARIS_PARAMETRELERI = frozenset({"-destination", "-dest", "-literalpath", "-path", "-filepath", "-outfile"})


def _ps_cmdlet(ad: str) -> str:
    """Cmdlet adini normalize eder: yol, `.exe`, takma ad ve buyuk/kucuk harf."""
    temiz = ad.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if temiz.endswith(".exe"):
        temiz = temiz[:-4]
    return PS_TAKMA_ADLAR.get(temiz, temiz)


def _ps_varis(argumanlar: list[str]) -> list[str]:
    """`Copy-Item` gibi cmdlet'lerde VARIS yolu olabilecek argumanlar."""
    varis: list[str] = []
    for i, token in enumerate(argumanlar):
        if token.lower() in PS_VARIS_PARAMETRELERI and i + 1 < len(argumanlar):
            varis.append(argumanlar[i + 1])
    konum = _konumsallar(argumanlar)
    if konum:
        varis.append(konum[-1])
    return varis


def _ps_parca_degerlendir(parca: list[str]) -> Karar:
    """Tek bir PowerShell komut parcasini degerlendirir."""
    argumanlar, hedefler = _yonlendirmeleri_ayir(parca)

    for hedef in hedefler:
        kalip = kapsar_mi(hedef)
        if kalip:
            return _red(kalip, f"yonlendirme kilitli dosyaya yaziyor: {hedef}")

    i = 0
    while i < len(argumanlar) and (
        re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", argumanlar[i])
        or argumanlar[i].lower() in PS_SARMALAYICILAR
    ):
        i += 1
    argumanlar = argumanlar[i:]
    if not argumanlar:
        return IZIN

    cmdlet = _ps_cmdlet(argumanlar[0])
    geri = argumanlar[1:]
    anilan = _ad_geciyor_mu(" ".join(geri))

    if cmdlet in PS_YAZMA:
        kalip = _kapsayan(geri)
        if kalip:
            return _red(kalip, f"`{cmdlet}` kilitli dosyayi degistiriyor ya da siliyor")
        return IZIN

    if cmdlet in PS_KOPYALAMA:
        for aday in _ps_varis(geri):
            kalip = kapsar_mi(aday)
            if kalip:
                return _red(kalip, f"`{cmdlet}` kilitli dosyanin uzerine yaziyor")
        return IZIN

    if cmdlet in PS_OKUMA:
        return IZIN

    if anilan:
        return _red(anilan, f"`{cmdlet}` cmdlet'inin sinifi belirlenemedi", belirsiz=True)
    return IZIN


def powershell_degerlendir(komut: str) -> Karar:
    """Bir PowerShell komutunun kilitli dosyalara yazma niyetini soyler. Saf fonksiyon.

    Lehce farklari: ayiricilar `;`, `|`, satir sonu ve `&&`/`||` (PowerShell 7);
    here-string (`@'...'@`) govdesi bir betige girdi olabilir, bu yuzden kilitli
    dosyayi aniyorsa temkinli reddedilir.
    """
    for govde in re.findall(r"@[\"'](.*?)[\"']@", komut, flags=re.DOTALL):
        kalip = _ad_geciyor_mu(govde)
        if kalip:
            return _red(kalip, "here-string icerigi kilitli dosyayi aniyor; betik olarak calisabilir",
                        belirsiz=True)
    try:
        tokenlar = tokenlara_ayir(komut)
    except ValueError:
        kalip = _ad_geciyor_mu(komut)
        if kalip:
            return _red(kalip, "komut ayristirilamadi (kapanmamis tirnak)", belirsiz=True)
        return IZIN

    for parca in parcalara_bol(tokenlar):
        karar = _ps_parca_degerlendir(parca)
        if not karar.izin:
            return karar
    return IZIN


# --- Arac adindan lehceye ----------------------------------------------------

# Arac adi -> lehce. Bu sozluk BEYAZ LISTE DEGILDIR: burada olmayan bir arac da
# komut tasiyorsa denetlenir (her iki lehce de calisir). Liste testte yazilidir,
# boylece yeni bir kabuk araci eklendiginde fark edilir (madde 1a).
KABUK_ARACLARI = {
    "bash": "bash",
    "shell": "bash",
    "sh": "bash",
    "zsh": "bash",
    "powershell": "powershell",
    "pwsh": "powershell",
    "powershellcore": "powershell",
}

# Komutun bulunabilecegi `tool_input` alanlari.
KOMUT_ALANLARI = ("command", "cmd", "commands", "script", "scripts", "komut", "shell", "run",
                  "code", "snippet", "program", "args", "argv", "arguments", "input")

# KOD alanlari: bir kabuk komutu degil, calistirilacak PROGRAM metni tasirlar (`code`, `snippet`).
# Kabuk ayristirmasi bunlari siniflandiramaz (`open("X","w")` bir yonlendirme degildir), bu yuzden
# kilitli bir adi anan kod metni TEMKINLI reddedilir (madde 1e).
KOD_ALANLARI = ("code", "snippet", "program", "script", "scripts")

# Hedef yolun bulunabilecegi `tool_input` alanlari.
YOL_ALANLARI = ("file_path", "notebook_path", "path", "filePath")

# SALT OKUMA araclari: yol alanlari denetlenmez (denetci bulgusu P-B1).
#
# Madde 1a'da eslestirici `.*` yapildi, yani artik OKUMA araclari da hook'a ugruyor; yol dali ise
# aracin yazip yazmadigina bakmadigi icin `Read`/`Grep` cagrilari da reddediliyordu. Sonucu agirdi:
# metodoloji denetcisi `PREREGISTRATION.md`'yi OKUYAMIYOR, yani "on-kayittan sapma" basligini hic
# denetleyemiyordu (CLAUDE.md §5 o denetimi zorunlu kilar). CLAUDE.md §5 hook'un gorevini de
# "yazma ve duzenleme arac cagrilarini reddeder" diye tanimlar: okuma kilidin konusu degildir.
#
# Liste BEYAZ LISTE olarak degil, yalnizca YOL dalinda muafiyet olarak kullanilir: taninmayan bir
# arac yol tasiyorsa yine denetlenir (yazabilir), komut tasiyan her arac yine denetlenir.
OKUMA_ARACLARI = frozenset({"read", "grep", "glob", "ls", "notebookread", "readfile", "readmanyfiles"})


def komut_degerlendir(arac: str | None, komut: str) -> Karar:
    """Arac adina gore lehce secer ve komutu degerlendirir.

    Taninmayan arac adinda IKI lehce de denetlenir: bir kabuk aracinin adini
    bilmemek, komutunu denetlemeden gecirmek icin gerekce degildir. Birlestirme
    kurali:
      - bir lehce KESIN red veriyorsa (`belirsiz=False`) komut reddedilir;
      - iki lehce de yalnizca TEMKINLI red veriyorsa komut reddedilir;
      - bir lehce komutu TANIYIP izin veriyorsa (ör. `Get-Content` PowerShell'de
        salt okuma, bash'te taninmayan komut) diger lehcenin temkinli reddi
        dusurulur, cunku o red komutu tanimamaktan doguyor.
    """
    lehce = KABUK_ARACLARI.get((arac or "").strip().lower())
    if lehce == "bash":
        return bash_degerlendir(komut)
    if lehce == "powershell":
        return powershell_degerlendir(komut)
    kararlar = (bash_degerlendir(komut), powershell_degerlendir(komut))
    for karar in kararlar:
        if not karar.izin and not karar.belirsiz:
            return karar
    if any(karar.izin for karar in kararlar):
        return IZIN
    for karar in kararlar:
        if not karar.izin:
            return karar
    return IZIN


# --- Cikti -------------------------------------------------------------------


def _deny_yaz(gerekce: str) -> None:
    cevap = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": gerekce,
        }
    }
    print(json.dumps(cevap, ensure_ascii=False))


def reddet(kalip: str) -> None:
    """Write/Edit icin PreToolUse deny cevabini yazar."""
    _deny_yaz(
        f"{kalip} kilitli bir dosyadir ve dogrudan duzenlenemez. "
        f"Bu dosya proje metodolojisinin cekirdegidir (CLAUDE.md §3.2-3.4): "
        f"on-kayit, veri bolmesi ve onay kaydi sonradan degistirilemez. "
        f"Degisiklik ancak kullanicinin acik izniyle yapilir; izin verildiginde "
        f"{ACMA_DEGISKENI}=1 ortam degiskeni ayarlanarak kilit acilir. "
        f"Kullaniciya sormadan bu dosyayi degistirme."
    )


def bash_reddet(karar: Karar) -> None:
    """Kabuk komutlari (Bash, PowerShell, taninmayan kabuk araci) icin deny cevabi."""
    ek = (
        " Komutun sinifi kesin belirlenemedigi icin TEMKINLI reddedildi; bu bir "
        "yanlis pozitifse kullaniciya bildir, hook'u atlatmaya calisma."
        if karar.belirsiz
        else ""
    )
    _deny_yaz(
        f"Kabuk komutu kilitli bir dosyaya yazma niyeti tasiyor ({karar.kalip}): "
        f"{karar.neden}. Kilitli dosyalar yalnizca kullanicinin acik izniyle "
        f"({ACMA_DEGISKENI}=1) degistirilir (CLAUDE.md §3.2-3.4).{ek}"
    )


def main() -> int:
    try:
        ham = sys.stdin.read()
    except Exception:
        return 0

    # Kilit bilerek acilmissa hicbir sey yapma.
    if os.environ.get(ACMA_DEGISKENI) == "1":
        return 0

    try:
        girdi = json.loads(ham) if ham.strip() else {}
    except Exception:
        # Girdi ayristirilamadi. Bir koruma katmani burada SESSIZCE GECMEMELI.
        kalip = _ad_geciyor_mu(ham)
        if kalip:
            reddet(kalip)
        return 0

    arac = girdi.get("tool_name")
    arac_girdi = girdi.get("tool_input") or {}

    # Komut tasiyan her arac denetlenir (madde 1a): arac adi yalnizca lehce secer.
    #
    # BUTUN komut alanlari denetlenir (bulgu P-C4): onceden yalnizca ILK bulunan alan
    # degerlendiriliyordu, yani iki komut alani tasiyan bir girdide
    # (`{"command": "echo ok", "script": "rm CLAUDE.md"}`) ikincisi gecip gidiyordu. Liste biciminde
    # komut tasiyan araclar da (`{"command": ["sed", "-i", ..., "CLAUDE.md"]}`) hic denetlenmiyordu.
    okuma_araci = (arac or "").strip().lower() in OKUMA_ARACLARI

    # Girdinin TAMAMI gezilir (madde 1e): alanlar ic ice sozluk ve listelerde de olabilir ve
    # `main()` artik "bilmedigi" bir alani sessizce gecmez.
    #
    # Bulgu neydi: komut ve yol alanlari SABIT listelerdi, bu yuzden `destination`, `new_path`,
    # `code` ya da `commands` gibi bir alanda gelen kilitli yol ya da komut hicbir listede
    # bulunmadigi icin FAIL-OPEN geciyordu. Denetlenmeyen bir GIRIS, denetlenmemis bir komut
    # biciminden farklidir: PowerShell boşlugu gibi kanal duzeyinde bir aciklik.
    for yol_adi, alan, deger in _girdi_alanlari(arac_girdi):
        kucuk = (alan or "").lower()
        if kucuk in KOMUT_ALANLARI:
            if not _komut_dali(arac, deger, kod_alani=kucuk in KOD_ALANLARI):
                return 0
            continue
        if okuma_araci:
            # Salt okuma araclarinin yolu denetlenmez (bulgu P-B1): kilit yazmaya karsidir,
            # okumaya degil. Komut alanlari yukarida arac adina bakilmadan denetlendi.
            continue
        if kucuk in YOL_ALANLARI:
            kalip = kilitli_mi(deger) if isinstance(deger, str) and deger else None
            if kalip:
                reddet(kalip)
                return 0
            continue
        # BILINMEYEN alan (madde 1e). Iki olcut:
        #   1. deger TEK BASINA kilitli bir yolsa: bir hedef yol alanidir (`destination`,
        #      `new_path`, `target`), reddedilir;
        #   2. deger bir komut olarak KESIN red veriyorsa (temkinli degil) reddedilir.
        # Yalnizca TEMKINLI red veren bilinmeyen alan gecirilir: `description` gibi serbest metin
        # alanlari kilitli bir dosyanin adini anmakla yazma niyeti tasimaz ve yanlis pozitif
        # uretirdi (`command` alani ayrica ve tam olarak denetlenmistir).
        if isinstance(deger, str) and deger:
            kalip = kilitli_mi(deger.strip().strip('"\''))
            if kalip:
                reddet(kalip)
                return 0
        if not _komut_dali(arac, deger, yalnizca_kesin=True):
            return 0
    return 0


def _girdi_alanlari(deger, yol: str = ""):
    """`tool_input` icindeki butun (yol, alan adi, deger) uclulerini ic ice gezerek uretir."""
    if isinstance(deger, dict):
        for ad, ic in deger.items():
            alt = f"{yol}.{ad}" if yol else str(ad)
            if isinstance(ic, (dict, list, tuple)) and not _metin_listesi(ic):
                yield from _girdi_alanlari(ic, alt)
            else:
                yield alt, str(ad), ic
    elif isinstance(deger, (list, tuple)):
        for i, ic in enumerate(deger):
            yield from _girdi_alanlari(ic, f"{yol}[{i}]")


def _metin_listesi(deger) -> bool:
    """Liste komut biciminde mi (`["sed", "-i", ...]`): butun ogeleri metin ya da sayi."""
    return (isinstance(deger, (list, tuple)) and bool(deger)
            and all(isinstance(p, (str, int, float)) for p in deger))


def _komut_metinleri(deger) -> list[str]:
    """Degerin icinde komut olarak degerlendirilecek metin(ler).

    Liste iki bicimde gelebilir ve IKISI de denetlenir (madde 1e):
      - argv parcalari (`["sed", "-i", "...", "X"]`): tirnaklanarak tek metne cevrilir,
      - tam komut listesi (`["rm X", "echo y"]`): her oge kendi basina bir komuttur. Yalnizca
        birlestirilmis bicime bakmak yetmiyordu: `shlex.quote` butun komutu tek bir tokene
        cevirdigi icin `["rm X"]` hicbir yazma bicimine benzemiyordu.
    """
    if isinstance(deger, str) and deger:
        return [deger]
    if _metin_listesi(deger):
        metinler = [" ".join(shlex.quote(str(p)) for p in deger)]
        metinler += [p for p in deger if isinstance(p, str) and p]
        return metinler
    return []


def _komut_dali(arac: str | None, deger, *, kod_alani: bool = False, yalnizca_kesin: bool = False) -> bool:
    """Komut metnini degerlendirir. Reddedildiyse cevabi yazar ve False doner."""
    for komut in _komut_metinleri(deger):
        try:
            karar = komut_degerlendir(arac, komut)
        except Exception as hata:  # hook hatasi komutu sessizce gecirmemeli
            kalip = _ad_geciyor_mu(komut)
            karar = _red(kalip, f"hook hatasi: {type(hata).__name__}", belirsiz=True) if kalip else IZIN
        if karar.izin and kod_alani:
            kalip = _ad_geciyor_mu(komut)
            if kalip:
                karar = _red(kalip, "kod alani kilitli dosyanin adini aniyor; program metni kabuk "
                                    "kurallariyla siniflandirilamaz", belirsiz=True)
        if karar.izin or (yalnizca_kesin and karar.belirsiz):
            continue
        bash_reddet(karar)
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
