# -*- coding: utf-8 -*-
"""미국·중국·일본 전망 — IMF World Economic Outlook.

DataMapper 로 받는다. 키가 필요 없고 전망 연도까지 함께 준다. 차트팩이 이미
같은 창구로 정부부채·재정수지를 받고 있다.

    NGDP_RPCH   실질 GDP 성장률 (%)
    PCPIPCH     소비자물가 상승률 (연평균, %)

둘 다 **상승률 그대로** 나온다. AMECO 와 달리 전년비를 낼 일이 없다.
"""

from __future__ import annotations

import time

import requests

BASE = "https://www.imf.org/external/datamapper/api/v1/{ind}/{areas}"
TIMEOUT = 60
RETRIES = 3

# 한국도 함께 받는다. 다만 한국은 **과거 실적만** 쓰고 전망 두 해는 한국은행
# 값으로 덮는다(make.py). 소장님 지시가 '한국 → 한국은행 조사국 전망'이고,
# 과거 실적치는 '편한 걸로'였다.
AREAS = {"US": "USA", "CN": "CHN", "JP": "JPN", "KR": "KOR"}
GDP = "NGDP_RPCH"
CPI = "PCPIPCH"


class ImfError(RuntimeError):
    pass


def series(indicator: str) -> dict[str, dict[str, float]]:
    url = BASE.format(ind=indicator, areas="/".join(AREAS.values()))
    last = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT)
        except requests.RequestException as exc:
            last = exc
        else:
            if r.status_code == 200:
                try:
                    doc = r.json()
                except ValueError as exc:
                    last = f"JSON 아님 ({exc})"
                else:
                    got = (doc.get("values") or {}).get(indicator) or {}
                    if got:
                        return {a: {y: float(v) for y, v in rows.items()
                                    if v is not None}
                                for a, rows in got.items()}
                    last = "값이 비었다"
            else:
                last = f"HTTP {r.status_code}"
        time.sleep(2 * (attempt + 1))
    raise ImfError(f"IMF {indicator}: {last}")


def outlook(years: list[str]) -> dict[str, dict[str, list[float | None]]]:
    """{블록: {'gdp'|'cpi': [연도별 값]}}."""
    gdp, cpi = series(GDP), series(CPI)
    out = {}
    for blk, area in AREAS.items():
        out[blk] = {
            "gdp": [gdp.get(area, {}).get(y) for y in years],
            "cpi": [cpi.get(area, {}).get(y) for y in years],
        }
    return out
