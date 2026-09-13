#!/usr/bin/env python3
"""Kilitli dosyalara yazmayi engelleyen PreToolUse hook'u.

Amac: F2'de ilk kez getiri hesaplanacak. Metodolojinin sessizce delinmemesi icin
on-kayit, veri bolmesi, onay kaydi ve proje anayasasi dosyalari yalnizca
kullanicinin acik izniyle degistirilebilir (CLAUDE.md §3.2-3.4).

Calisma bicimi:
  - Write / Edit / NotebookEdit: hedef dosya yolu kilitliyse reddeder.
  - Bash: komut metni kilitli bir dosyaya YAZMA niyeti tasiyorsa reddeder
    (yonlendirme, sed -i, mv, cp hedefi, rm, truncate, tee, agac degistiren git
    alt komutlari). Salt okuma komutlari (cat, git log, git show, grep, head,
    tail ...) gecer. Sinifi belirlenemeyen ve kilitli dosyayi anan komutlar
    TEMKINLI olarak reddedilir; gerekce bunu acikca soyler.
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

# Kilitli dosyalar, proje kokune gore.
KILITLI = (
    "PREREGISTRATION.md",
    "data/split.csv",
    "data/universe.csv",
    "ONAY_KAYDI.md",
    "CLAUDE.md",
)

ACMA_DEGISKENI = "SHORT_LAB_KILIT_ACIK"

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
    try:
        mutlak = Path(yol).resolve()
        for kalip in KILITLI:
            if mutlak == (KOK / kalip).resolve():
                return kalip
    except Exception:
        pass

    duz = yol.replace("\\", "/").lower().rstrip("/")
    for kalip in KILITLI:
        hedef = kalip.lower()
        if duz == hedef or duz.endswith("/" + hedef):
            return kalip
    return None


def _ad_geciyor_mu(metin: str) -> str | None:
    """Metinde kilitli bir dosyanin adi geciyor mu? (buyuk-kucuk harf duyarsiz)"""
    kucuk = metin.lower()
    for kalip in KILITLI:
        if kalip.rsplit("/", 1)[-1].lower() in kucuk:
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
    duz = arguman.replace("\\", "/").strip()
    if "=" in duz and not duz.startswith("-"):  # dd of=..., --file=...
        duz = duz.split("=", 1)[1]
    elif duz.startswith("--") and "=" in duz:
        duz = duz.split("=", 1)[1]
    kucuk = duz.lower()

    # 1) Dosyanin kendisi: tam goreli yol ya da ayni dosya adi
    for kalip in KILITLI:
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
    """Kabuk benzeri tokenlara ayirir; satir sonu komut ayiricisidir."""
    lex = shlex.shlex(metin, posix=True, punctuation_chars=";&|<>()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
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
    """Bash icin PreToolUse deny cevabini yazar."""
    ek = (
        " Komutun sinifi kesin belirlenemedigi icin TEMKINLI reddedildi; bu bir "
        "yanlis pozitifse kullaniciya bildir, hook'u atlatmaya calisma."
        if karar.belirsiz
        else ""
    )
    _deny_yaz(
        f"Bash komutu kilitli bir dosyaya yazma niyeti tasiyor ({karar.kalip}): "
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

    if arac == "Bash":
        komut = arac_girdi.get("command")
        if not isinstance(komut, str) or not komut:
            return 0
        try:
            karar = bash_degerlendir(komut)
        except Exception as hata:  # hook hatasi komutu sessizce gecirmemeli
            kalip = _ad_geciyor_mu(komut)
            if kalip:
                bash_reddet(_red(kalip, f"hook hatasi: {type(hata).__name__}", belirsiz=True))
            return 0
        if not karar.izin:
            bash_reddet(karar)
        return 0

    for alan in ("file_path", "notebook_path", "path"):
        deger = arac_girdi.get(alan)
        if isinstance(deger, str) and deger:
            kalip = kilitli_mi(deger)
            if kalip:
                reddet(kalip)
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
