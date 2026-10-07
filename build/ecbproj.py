# -*- coding: utf-8 -*-
"""ECB 스태프 거시경제 전망 — 유로지역.

왜 EU 집행위가 아니라 이것인가
  유로지역 통화정책을 결정하는 곳이 내는 전망이고, 분기마다(3·6·9·12월)
  새로 낸다. AMECO 는 봄·가을 두 번이라 그 사이에 묵는다. 2026-10-07 에
  AMECO 6월 판은 유로지역 2027년 성장률을 1.2% 로 두고 있었는데 9월 ECB
  전망은 1.4% 였다. 물가도 2.3% 대 2.5% 로 갈렸다. 소장님이 짚어 주셨다.

무엇을 받아 오는가
  '지난 거시경제 전망' 쪽 하나에 판마다 표가 쌓여 있다. 표에
  `<caption>September 2026 (annual percentage changes)</caption>` 처럼
  판이 붙어 있어 가장 새 것을 고를 수 있다.

  한 판에 표가 여럿인 때가 있다 — 기준선 다음에 시나리오(완만·심각)가
  따라붙는다. **맨 앞 것이 기준선**이므로 첫 줄만 쓴다.

  실적은 여기서 받지 않는다. ECB 표는 전망이 시작되는 해부터라 과거가
  짧다. 지난 해들은 AMECO 를 그대로 쓰고, **전망 두 해만 덮는다** —
  한국은행을 쓰는 방식과 같다.
"""

from __future__ import annotations

import datetime
import html
import re

import requests

URL = "https://www.ecb.europa.eu/mopo/devel/ecana/html/table.en.html"
UA = "Mozilla/5.0 (compatible; bok-ffm-outlook/1.0)"
TIMEOUT = 60

TABLE = re.compile(r"<table.*?</table>", re.S)
CAPTION = re.compile(r"<caption[^>]*>(.*?)</caption>", re.S)
ROW = re.compile(r"<tr.*?</tr>", re.S)
CELL = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S)
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


class ProjError(RuntimeError):
    """ECB 전망을 받지 못했다."""


def _text(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def _cells(row: str) -> list[str]:
    return [t for t in (_text(c) for c in CELL.findall(row)) if t]


def forecast() -> dict:
    """{'issue': '2026년 9월', 'date': date, 'gdp': {연도: 값}, 'cpi': {…}}"""
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ProjError(f"{type(exc).__name__}") from exc
    if r.status_code != 200:
        raise ProjError(f"HTTP {r.status_code}")

    best: tuple[datetime.date, str] | None = None
    for tb in TABLE.findall(r.text):
        cap = CAPTION.search(tb)
        if not cap:
            continue
        m = re.match(r"([A-Z][a-z]+)\s+(20\d\d)", _text(cap.group(1)))
        if not m or m.group(1) not in MONTHS:
            continue
        when = datetime.date(int(m.group(2)), MONTHS[m.group(1)], 1)
        if best is None or when > best[0]:
            best = (when, tb)
    if best is None:
        raise ProjError("판이 붙은 표를 찾지 못했다 — 쪽 구조가 바뀌었나")

    when, tb = best
    years: list[int] = []
    out: dict[str, dict[int, float]] = {}
    for row in ROW.findall(tb):
        cells = _cells(row)
        if not cells:
            continue
        if all(re.fullmatch(r"20\d\d", c) for c in cells):
            years = [int(c) for c in cells]
            continue
        key = {"HICP": "cpi", "Real GDP": "gdp"}.get(cells[0])
        if not key or key in out or not years:      # 첫 줄만 — 뒤는 시나리오
            continue
        vals = []
        for c in cells[1:1 + len(years)]:
            try:
                vals.append(float(c.replace("−", "-").replace("–", "-")))
            except ValueError:
                vals.append(None)
        out[key] = {y: v for y, v in zip(years, vals) if v is not None}

    missing = {"gdp", "cpi"} - set(out)
    if missing:
        raise ProjError(f"{when:%Y-%m} 표에서 {', '.join(sorted(missing))} 줄을 "
                        f"찾지 못했다")
    return {"issue": f"{when.year}년 {when.month}월", "date": when, **out}
