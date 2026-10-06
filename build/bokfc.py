# -*- coding: utf-8 -*-
"""한국은행 전망 — 보도자료 본문에서 캐낸다.

세 번 막히고 네 번째에 길이 났다(2026-10-06).

  보도자료 **목록**   자바스크립트로 그려진다. requests 로는 글이 한 건도
                    안 보인다. 브라우저로는 보인다.
  RSS               없다. rss.do 는 500 을 낸다.
  PDF 첨부          열 필요가 없었다 — 본문에 숫자가 그대로 있다.
  관련 뉴스/자료     **이것이 길이다.** 글마다 아래에 붙고 서버가 그려 보낸다.

그래서 아는 글 하나를 닻으로 삼아 '관련 뉴스/자료' 에 실린 더 큰 글 번호로
타고 올라간다. 새 전망이 나오면 저절로 잡히고, 안 나왔으면 닻 그대로다.
찾은 번호는 state 에 적어 두어 다음 빌드의 닻이 된다 — 닻이 앞으로 나아간다.

**문구가 판마다 다르다.** 둘 다 받는다.

    2025년 11월   GDP성장률 금년 1.0%, 내년 1.8%
                 소비자물가 상승률은 금년, 내년 모두 2.1%
    2026년 8월    국내경제는 올해 3.3%, 내년 2.9%
                 소비자물가는 올해 2.7%, 내년 2.3%

'금년/올해'가 전망 첫 해, '내년'이 둘째 해다. 보고서 제목의 연도가 기준이다 —
2026년 8월 판이면 첫 해가 2026, 둘째 해가 2027 이다.
"""

from __future__ import annotations

import re

import requests

VIEW = ("https://www.bok.or.kr/portal/bbs/B0000502/view.do"
        "?menuNo=201265&nttId={n}")
# 닻. 2025년 11월 전망 보도자료. 여기서부터 타고 올라간다.
ANCHOR = 10094816
HOPS = 6               # 한 빌드에서 타고 올라갈 횟수 상한
TIMEOUT = 40
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

_TITLE = re.compile(r"경제전망\((\d{4})년\s*(\d{1,2})월\)")
_GROW = re.compile(r"(?:GDP\s*성장률|국내경제는)[^□]{0,30}?(?:금년|올해)\s*"
                   r"([\d.]+)\s*%[^□]{0,20}?내년\s*([\d.]+)\s*%")
# '금년, 내년 모두 2.1%' 꼴을 먼저 본다. 두 해가 같을 때 쓰는 말이라
# 숫자가 하나뿐이고, 아래 두 숫자짜리 규칙으로는 엉뚱한 값을 집는다.
_CPI_SAME = re.compile(r"소비자물가[^□]{0,30}?(?:금년|올해)\s*,?\s*내년\s*모두\s*"
                       r"([\d.]+)\s*%")
_CPI_TWO = re.compile(r"소비자물가[^□]{0,30}?(?:금년|올해)\s*([\d.]+)\s*%"
                      r"[^□]{0,20}?내년\s*([\d.]+)\s*%")


class BokError(RuntimeError):
    pass


def _page(nid: int) -> tuple[str, str]:
    r = requests.get(VIEW.format(n=nid), headers={"User-Agent": UA},
                     timeout=TIMEOUT)
    if r.status_code != 200:
        raise BokError(f"한국은행 {nid}: HTTP {r.status_code}")
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text)
                  .replace("&nbsp;", " ").replace("&middot;", "·"))
    return r.text, flat


def _issue(html: str) -> tuple[int, int] | None:
    m = re.search(r"<title>\s*([^<|]+)", html)
    if not m:
        return None
    t = _TITLE.search(m.group(1))
    return (int(t.group(1)), int(t.group(2))) if t else None


def latest(anchor: int | None = None) -> dict:
    """가장 새 경제전망 보도자료를 찾아 수치를 돌려준다."""
    nid = anchor or ANCHOR
    best = None
    seen: set[int] = set()
    for _ in range(HOPS):
        html, flat = _page(nid)
        issue = _issue(html)
        if issue and (best is None or issue > best["issue"]):
            best = {"issue": issue, "nttId": nid, "flat": flat}
        seen.add(nid)
        # '관련 뉴스/자료' 에 실린 더 큰 번호 가운데 경제전망인 것으로 옮긴다.
        nxt = sorted({int(x) for x in re.findall(r"nttId=(\d+)", html)
                      if int(x) > nid} - seen, reverse=True)
        moved = False
        for cand in nxt:
            try:
                chtml, _ = _page(cand)
            except BokError:
                continue
            if _issue(chtml):
                nid, moved = cand, True
                break
            seen.add(cand)
        if not moved:
            break

    if best is None:
        raise BokError("한국은행: 경제전망 보도자료를 찾지 못했다")

    flat = best["flat"]
    g = _GROW.search(flat)
    same = _CPI_SAME.search(flat)
    two = _CPI_TWO.search(flat)
    if not g or not (same or two):
        raise BokError(f"한국은행 {best['nttId']}: 본문에서 수치를 읽지 못했다 "
                       f"— 문구가 바뀌었을 수 있다")
    cpi = ((float(same.group(1)), float(same.group(1))) if same
           else (float(two.group(1)), float(two.group(2))))
    year0 = best["issue"][0]
    return {
        "issue": f"{best['issue'][0]}년 {best['issue'][1]}월",
        "nttId": best["nttId"],
        "url": VIEW.format(n=best["nttId"]),
        "years": [str(year0), str(year0 + 1)],
        "gdp": [float(g.group(1)), float(g.group(2))],
        "cpi": [cpi[0], cpi[1]],
    }
