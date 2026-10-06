# -*- coding: utf-8 -*-
"""EU 집행위 전망 — AMECO 데이터베이스에서 받는다.

집행위는 봄·가을에 'European Economic Forecast' 를 내는데, 그 수치가 그대로
들어가는 기계 판독 창구가 AMECO 다. 보고서 PDF 를 뜯는 것보다 훨씬 덜 깨진다.

    https://ec.europa.eu/economy_finance/db_indicators/ameco/documents/ameco0.zip

7MB 짜리 zip 안에 장별로 AMECO1.TXT ~ AMECO18.TXT 가 들어 있다. 세미콜론으로
나뉘고 머리글이 `CODE;COUNTRY;SUB-CHAPTER;TITLE;UNIT;1960;1961;…` 이다.
코드는 `DEU.1.1.0.0.OVGD` 처럼 `나라.…계열` 꼴이다.

**수준 계열만 준다.** 성장률·물가상승률을 직접 주는 칸이 없어 전년비를 여기서
낸다. 집행위가 공표한 성장률과 끝자리 반올림이 다를 수 있다 — 화면 각주에
그렇게 적는다. 값 자체는 같은 수준 계열에서 나온 것이라 어긋나지 않는다.

앞선 해(전망 연도)도 함께 들어 있다. 그것이 이 쪽의 목적이다.
"""

from __future__ import annotations

import io
import re
import zipfile

import requests

URL = ("https://ec.europa.eu/economy_finance/db_indicators/ameco/documents/"
       "ameco{part}.zip")
TIMEOUT = 180
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

# 받을 나라. 키는 화면 블록 이름, 값은 AMECO 나라 코드.
AREAS = {"EA": "EA20", "DE": "DEU", "FR": "FRA", "IT": "ITA", "ES": "ESP"}

# (계열 코드, 들어 있는 파일). 둘 다 수준이라 전년비는 코드에서 낸다.
#   OVGD   실질 GDP(2020년 기준가격)
#   ZCPIH  조화소비자물가지수(HICP, 2015=100)
SERIES = {"gdp": ("OVGD", "AMECO6.TXT"), "cpi": ("ZCPIH", "AMECO2.TXT")}


class AmecoError(RuntimeError):
    pass


def _fetch() -> zipfile.ZipFile:
    r = requests.get(URL.format(part=0), headers={"User-Agent": UA},
                     timeout=TIMEOUT)
    if r.status_code != 200 or len(r.content) < 500_000:
        raise AmecoError(f"AMECO 내려받기 실패 (HTTP {r.status_code}, "
                         f"{len(r.content):,}바이트)")
    try:
        return zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile as exc:
        raise AmecoError(f"AMECO zip 이 깨졌다: {exc}") from exc


def _rows(z: zipfile.ZipFile, member: str):
    lines = z.read(member).decode("utf-8", "ignore").splitlines()
    head = lines[0].split(";")
    years = [y.strip() for y in head[5:]]
    for line in lines[1:]:
        f = line.split(";")
        if len(f) < 6:
            continue
        yield f[0], f[1], f[4].strip(), years, f[5:]


def levels(years_wanted: list[str]) -> dict[str, dict[str, dict[str, float]]]:
    """{블록: {'gdp'|'cpi': {연도: 수준}}}.

    한 나라에 같은 계열이 단위만 달리해 여러 줄 있다(유로·자국통화 등).
    **첫 줄만 쓴다** — 전년비를 낼 것이라 단위가 무엇이든 비율은 같다.
    다만 통화 단위가 바뀐 해가 끼면 비율이 어긋나므로, 자국통화 줄을
    고르되 없으면 처음 잡히는 것을 쓴다.
    """
    z = _fetch()
    out: dict[str, dict[str, dict[str, float]]] = {
        blk: {} for blk in AREAS}
    need = {code: name for name, (code, _f) in SERIES.items()}
    for name, (code, member) in SERIES.items():
        for blk, geo in AREAS.items():
            picked = None
            for row_code, _country, unit, years, vals in _rows(z, member):
                if not row_code.startswith(geo + "."):
                    continue
                if not row_code.endswith("." + code):
                    continue
                got = {}
                for y, v in zip(years, vals):
                    v = v.strip()
                    if y in years_wanted and v not in ("NA", ""):
                        try:
                            got[y] = float(v)
                        except ValueError:
                            pass
                if len(got) > len(picked or {}):
                    picked = got
            if picked:
                out[blk][name] = picked
    if not any(out[b].get("gdp") for b in out):
        raise AmecoError("AMECO: 실질 GDP 를 한 나라도 읽지 못했다")
    return out


def pct_change(level: dict[str, float], years: list[str]) -> list[float | None]:
    """전년비(%). 앞 해 값이 없으면 None."""
    out = []
    for y in years:
        prev = str(int(y) - 1)
        a, b = level.get(y), level.get(prev)
        out.append(None if a is None or not b else (a / b - 1) * 100)
    return out


def vintage() -> str | None:
    """AMECO 파일이 마지막으로 바뀐 날. 전망 판을 가늠하는 데 쓴다."""
    try:
        r = requests.head(URL.format(part=0), headers={"User-Agent": UA},
                          timeout=60, allow_redirects=True)
        return (r.headers.get("Last-Modified") or "")[:16] or None
    except requests.RequestException:
        return None
