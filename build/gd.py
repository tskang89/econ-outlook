# -*- coding: utf-8 -*-
"""공동경제진단(Gemeinschaftsdiagnose) — 독일 전망.

왜 EU 집행위가 아니라 이것인가
  AMECO 는 집행위가 봄·가을에 내는 것이라 판이 묵는다. 2026-10-07 에
  AMECO 6월 판은 독일 2026년 성장률을 0.6% 로 두고 있었는데, 그 사이
  9월 24일에 나온 공동경제진단이 **1.3%** 로 올려 잡았다 — 0.7%p 차이다.
  2024년 실적도 AMECO 는 -0.5%, 공동경제진단은 0.0% 로 다르다(독일이
  국민계정을 개편했고 AMECO 6월 판이 그 전 숫자다).

  공동경제진단은 ifo·DIW·IfW·IWH·RWI 다섯 연구소가 연방정부 의뢰로
  내는 것이고, 독일에서 실제로 인용되는 기준이다. 소장님이 짚어 주셨다.

무엇을 받아 오는가
  보도자료 PDF 안의 '**Eckdaten der Prognose für Deutschland**' 표.
  해마다 같은 꼴로 나온다.

      2023 2024 2025 2026 2027 2028
      Bruttoinlandsprodukt1  -1,0 0,0 0,2 1,3 1,1 0,4
      Verbraucherpreise4      5,9 2,2 2,2 2,8 3,2 2,0

  본문 문장이 아니라 **표**를 읽는다. 문장은 판마다 말투가 바뀌지만 표는
  자리가 고정돼 있다(한국은행 쪽에서 문장을 읽다가 여러 번 데었다).

  물가는 독일 소비자물가(VPI)다. 다른 나라는 HICP 라 기준이 조금 다르다 —
  쪽 각주에 적어 둔다.

언제 바뀌는가
  봄(3~4월)·가을(9~10월) 두 번. 누리집 첫 쪽에서 가장 새 글을 찾아
  거기 걸린 PDF 를 받는다.
"""

from __future__ import annotations

import datetime
import io
import re

import requests

SITE = "https://gemeinschaftsdiagnose.de/"
UA = "Mozilla/5.0 (compatible; bok-ffm-outlook/1.0)"
TIMEOUT = 60

# 전망 글만 고른다. '…에 대한 의견서(Stellungnahme)' 나 사후평가는 아니다.
POST = re.compile(
    r"https://gemeinschaftsdiagnose\.de/(20\d\d)/(\d\d)/(\d\d)/"
    r"(gemeinschaftsdiagnose-(?:herbst|fruehjahr|fr%c3%bchjahr)-20\d\d[a-z0-9-]*)/",
    re.I)
PDF = re.compile(r'https://gemeinschaftsdiagnose\.de/[^"\']+?_PM_de\.pdf', re.I)

ROW = {
    "gdp": re.compile(r"Bruttoinlandsprodukt\s*\d?\s*((?:[-–−]?\d+,\d+\s+){4,})"),
    "cpi": re.compile(r"Verbraucherpreise\s*\d?\s*((?:[-–−]?\d+,\d+\s+){4,})"),
}
YEARS = re.compile(r"Eckdaten der Prognose für Deutschland\s+((?:20\d\d\s+){4,})")


class GDError(RuntimeError):
    """공동경제진단을 받지 못했다."""


def _get(url: str) -> requests.Response:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GDError(f"{url} — {type(exc).__name__}") from exc
    if r.status_code != 200:
        raise GDError(f"{url} — HTTP {r.status_code}")
    return r


def newest() -> tuple[str, datetime.date]:
    """가장 새 전망 글의 주소와 날짜."""
    posts = POST.findall(_get(SITE).text)
    if not posts:
        raise GDError("누리집에서 전망 글을 찾지 못했다 — 쪽 구조가 바뀌었나")
    y, m, d, slug = max(posts, key=lambda p: (p[0], p[1], p[2]))
    return (f"https://gemeinschaftsdiagnose.de/{y}/{m}/{d}/{slug}/",
            datetime.date(int(y), int(m), int(d)))


def _num(s: str) -> float:
    return float(s.replace("−", "-").replace("–", "-").replace(",", "."))


def forecast() -> dict:
    """{'issue': '2026년 9월', 'date': date, 'url': …, 'gdp': {연도: 값}, 'cpi': {…}}"""
    post, when = newest()
    pdfs = PDF.findall(_get(post).text)
    if not pdfs:
        raise GDError(f"보도자료 PDF 를 찾지 못했다 — {post}")

    try:
        import pypdf
    except ImportError as exc:                       # noqa: F841
        raise GDError("pypdf 가 없다 — requirements.txt 를 확인할 것") from None

    raw = _get(pdfs[0]).content
    try:
        pages = pypdf.PdfReader(io.BytesIO(raw)).pages
        text = re.sub(r"\s+", " ", "\n".join(p.extract_text() or "" for p in pages))
    except Exception as exc:                          # noqa: BLE001
        raise GDError(f"PDF 를 읽지 못했다 — {type(exc).__name__}") from exc

    ym = YEARS.search(text)
    if not ym:
        raise GDError("PDF 에서 'Eckdaten' 표의 연도 줄을 찾지 못했다")
    years = [int(y) for y in ym.group(1).split()]

    out: dict[str, dict[int, float]] = {}
    for kind, pat in ROW.items():
        m = pat.search(text)
        if not m:
            raise GDError(f"PDF 에서 {kind} 줄을 찾지 못했다")
        vals = [_num(v) for v in m.group(1).split()]
        if len(vals) < len(years):
            raise GDError(f"{kind} 줄의 숫자가 연도 수보다 적다 "
                          f"({len(vals)} < {len(years)})")
        out[kind] = dict(zip(years, vals[:len(years)]))

    return {"issue": f"{when.year}년 {when.month}월", "date": when,
            "url": post, "pdf": pdfs[0], **out}
