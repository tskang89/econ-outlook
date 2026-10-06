# -*- coding: utf-8 -*-
"""index.html 을 만든다 — 주요국 성장률·물가 전망 한 장.

조간 브리핑 참고자료에 걸리는 쪽이다. 주 1회(월요일) 돈다.

**매주 새로 그리지 않는다.** 각 기관이 새 전망을 냈을 때만 쪽을 다시 쓴다.
전망은 분기에 한 번쯤 바뀌는 것이라, 날짜만 바뀐 쪽을 매주 올리면 '새 전망이
나왔나' 싶어 열어 보게 된다. 그래서 수치와 판(vintage)을 state 에 적어 두고
지난주와 같으면 아무것도 쓰지 않는다.

출처가 나라마다 다르다. 섞어 쓰는 것이 아니라 **각 나라를 가장 잘 아는 곳**을
고른 것이다. 화면에 어디서 왔는지 줄마다 적는다.

  유로지역·독일·프랑스·이탈리아·스페인   EU 집행위 (AMECO)
  미국·중국·일본                     IMF World Economic Outlook
  한국                              한국은행 경제전망 (과거 실적은 IMF)
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import ameco                                                   # noqa: E402
import bokfc                                                   # noqa: E402
import imffc                                                   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template.html"
OUTPUT = ROOT / "index.html"
STATE = ROOT / "data" / "state.json"

# 과거 3개년 + 올해·내년. 올해는 달력이 아니라 **마지막 실적 연도 다음**으로
# 잡아야 맞는데, 연초에는 작년 실적이 아직 안 나와 흔들린다. 그래서 달력을
# 쓰고, 어느 해가 전망인지는 기관이 준 값으로 가른다.
def axis(today: datetime.date) -> list[str]:
    return [str(today.year - 3 + i) for i in range(5)]


# 차례. 주요국 경제 차트팩의 탭 차례(미국·중국·유로지역·일본·한국)와 같게
# 두되, 유로 회원국을 유로지역 바로 밑에 붙인다. 두 쪽을 오가며 보는 것이라
# 같은 차례라야 눈이 헤매지 않는다.
ROWS = [
    ("US", "미국", "imf"),
    ("CN", "중국", "imf"),
    ("EA", "유로지역", "ameco"),
    ("DE", "독일", "ameco"),
    ("FR", "프랑스", "ameco"),
    ("IT", "이탈리아", "ameco"),
    ("ES", "스페인", "ameco"),
    ("JP", "일본", "imf"),
    ("KR", "한국", "bok"),
]
SRC_LABEL = {"ameco": "EU 집행위", "imf": "IMF WEO", "bok": "한국은행"}


def log(msg: str = "") -> None:
    print(msg, flush=True)


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def collect(years: list[str]) -> tuple[dict, dict, list[str]]:
    data: dict[str, dict] = {}
    meta: dict = {}
    warn: list[str] = []

    try:
        lv = ameco.levels([str(int(years[0]) - 1)] + years)
        for blk in ameco.AREAS:
            data[blk] = {
                "gdp": ameco.pct_change(lv[blk].get("gdp", {}), years),
                "cpi": ameco.pct_change(lv[blk].get("cpi", {}), years),
            }
        meta["ameco"] = ameco.vintage()
        log(f"  EU 집행위 AMECO  {len(ameco.AREAS)}곳  판 {meta['ameco']}")
    except ameco.AmecoError as exc:
        warn.append(f"EU 집행위 전망을 받지 못했다 — {exc}")
        log(f"  [실패] AMECO — {exc}")

    try:
        got = imffc.outlook(years)
        data.update(got)
        log(f"  IMF WEO        {len(got)}곳")
    except imffc.ImfError as exc:
        warn.append(f"IMF 전망을 받지 못했다 — {exc}")
        log(f"  [실패] IMF — {exc}")

    try:
        bok = bokfc.latest(meta.get("bokAnchor"))
        meta["bok"] = bok["issue"]
        meta["bokUrl"] = bok["url"]
        meta["bokAnchor"] = bok["nttId"]
        # 한국의 전망 두 해만 덮는다. 과거 실적은 IMF 값을 그대로 둔다.
        row = data.setdefault("KR", {"gdp": [None] * len(years),
                                     "cpi": [None] * len(years)})
        for i, y in enumerate(years):
            if y in bok["years"]:
                j = bok["years"].index(y)
                row["gdp"][i] = bok["gdp"][j]
                row["cpi"][i] = bok["cpi"][j]
        meta["bokYears"] = bok["years"]
        log(f"  한국은행        {bok['issue']} (nttId {bok['nttId']}) "
            f"성장 {bok['gdp']} 물가 {bok['cpi']}")
    except bokfc.BokError as exc:
        warn.append(f"한국은행 전망을 받지 못했다 — {exc}")
        log(f"  [실패] 한국은행 — {exc}")

    return data, meta, warn


def fmt(v) -> str:
    return "–" if v is None else f"{v:+.1f}".replace("+", "") if v < 0 else f"{v:.1f}"


def table(data: dict, years: list[str], kind: str, meta: dict) -> str:
    head = "".join(f"<th>{y[2:]}</th>" for y in years)
    rows = []
    for blk, name, src in ROWS:
        vals = (data.get(blk) or {}).get(kind) or [None] * len(years)
        cells = []
        for i, v in enumerate(vals):
            fore = _is_forecast(blk, years[i], meta)
            cls = ' class="f"' if fore else ""
            cells.append(f"<td{cls}>{fmt(v)}</td>")
        rows.append(
            f'<tr><th scope="row">{esc(name)}'
            f'<span class="src">{SRC_LABEL[src]}</span></th>'
            + "".join(cells) + "</tr>")
    return (f'<table><thead><tr><th scope="col">국가</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def _is_forecast(blk: str, year: str, meta: dict) -> bool:
    """전망 연도인가. 뒤 두 해를 전망으로 본다 — 한국은 한국은행이 밝힌 해."""
    if blk == "KR" and meta.get("bokYears"):
        return year in meta["bokYears"]
    return year in meta.get("foreYears", [])


NOTE = """<b>읽는 법</b> 색이 든 칸이 <b>전망</b>이고 나머지는 실적입니다.
모두 연간, 전년 대비 %입니다.
<br><br>
<b>출처가 나라마다 다릅니다.</b> 섞어 쓴 것이 아니라 각 나라를 가장 잘 아는
곳을 고른 것입니다. 표의 국가 이름 아래에 어디서 왔는지 적었습니다.
<ul>
<li><b>유로지역·독일·프랑스·이탈리아·스페인</b> — EU 집행위 AMECO.
집행위가 봄·가을에 내는 European Economic Forecast 가 그대로 들어가는
데이터베이스입니다.</li>
<li><b>미국·중국·일본</b> — IMF World Economic Outlook.</li>
<li><b>한국</b> — 한국은행 경제전망. 전망 두 해만 한국은행 값이고, 과거
실적은 IMF 값을 썼습니다.</li>
</ul>
<b>AMECO 는 수준 계열만 줍니다.</b> 성장률·물가상승률은 전년비로 계산한
것이라 집행위가 공표한 숫자와 <b>끝자리 반올림이 다를 수 있습니다.</b>
같은 계열에서 낸 것이라 값이 어긋나지는 않습니다. IMF 와 한국은행은 상승률을
그대로 싣습니다.
<br><br>
<b>물가의 정의가 조금씩 다릅니다.</b> 유로지역 쪽은 조화소비자물가지수(HICP),
미국·중국·일본·한국은 각국 소비자물가입니다. 나라 사이 수준을 견줄 때는
이것을 감안해 주십시오.
<br><br>
<b>새 전망이 나왔을 때만 다시 그립니다.</b> 주 1회 확인하되 수치가 지난주와
같으면 쪽을 건드리지 않습니다 — 날짜만 바뀐 쪽이 올라오면 새 전망이 나온
줄로 읽히기 때문입니다."""


def build(today: datetime.date, state: dict) -> tuple[str | None, dict]:
    years = axis(today)
    log(f"전망 수집 — {years[0]}~{years[-1]}")
    data, meta, warn = collect(years)
    if not data:
        raise RuntimeError("세 출처를 모두 받지 못했다 — 쪽을 쓰지 않는다")

    # 뒤 두 해를 전망으로 본다. 한국은 한국은행이 밝힌 해를 따로 쓴다.
    meta["foreYears"] = years[-2:]

    fingerprint = json.dumps({"years": years, "data": data,
                              "ameco": meta.get("ameco"),
                              "bok": meta.get("bok")},
                             ensure_ascii=False, sort_keys=True)
    changed = fingerprint != state.get("fingerprint")
    state = {"fingerprint": fingerprint, "bokAnchor": meta.get("bokAnchor"),
             "checked": today.isoformat(),
             "updated": (today.isoformat() if changed
                         else state.get("updated"))}
    if not changed:
        log("\n지난 판과 같다 — 쪽을 다시 쓰지 않는다.")
        return None, state

    stamp = (f'{meta.get("bok") or "?"} 한국은행 · '
             f'EU 집행위 AMECO {meta.get("ameco") or "?"} · IMF WEO')
    warn_html = ""
    if warn:
        warn_html = ('<div class="warn"><b>일부를 받지 못했습니다.</b> '
                     + " / ".join(esc(w) for w in warn) + "</div>")

    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("__STAMP__", esc(stamp))
    page = page.replace("__UPDATED__", esc(state["updated"] or today.isoformat()))
    page = page.replace("__WARN__", warn_html)
    page = page.replace("__GDP__", table(data, years, "gdp", meta))
    page = page.replace("__CPI__", table(data, years, "cpi", meta))
    page = page.replace("__NOTE__", NOTE)
    page = page.replace("__OPS__", ops_blob(today, years, data, meta, warn))
    log(f"\n바뀌었다 — 쪽을 새로 쓴다 ({len(ROWS)}개국)")
    return page, state


def ops_blob(today, years, data, meta, warn) -> str:
    ops = {
        "built": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "asOf": today.isoformat(),
        "years": years,
        "bok": meta.get("bok"),
        "ameco": meta.get("ameco"),
        "rows": {blk: data.get(blk, {}) for blk, _n, _s in ROWS},
        "warn": [" ".join(w.split()) for w in warn],
    }
    return json.dumps(ops, ensure_ascii=False).replace("<", "\\u003c")


def main() -> int:
    ap = argparse.ArgumentParser(description="주요국 성장률·물가 전망")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 만들어만 본다")
    ap.add_argument("--force", action="store_true", help="같아도 새로 쓴다")
    ap.add_argument("--date", help="기준일을 바꿔 본다 (YYYY-MM-DD)")
    args = ap.parse_args()

    today = (datetime.date.fromisoformat(args.date) if args.date
             else datetime.date.today())
    state = {}
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
    if args.force:
        state = {k: v for k, v in state.items() if k != "fingerprint"}

    page, new_state = build(today, state)
    if args.check:
        log("--check: 파일을 쓰지 않았다.")
        return 0
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    if page is None:
        return 0
    OUTPUT.write_text(page, encoding="utf-8")
    log(f"index.html 갱신 — {len(page):,}자")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
