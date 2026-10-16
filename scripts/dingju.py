#!/usr/bin/env python3
"""
家传手抄本《袁天罡大六壬定局秘书》六张查表：按出生信息查出原书的诗文与页码。

    python3 dingju.py --birth "1990-06-15 08:30" --gender male --longitude 116.41
    python3 dingju.py --birth "1990-06-15 08:30" --gender female --json
    python3 dingju.py --selftest

依赖：pip install lunar_python（6tail 的农历库，年柱以立春换年、月柱按节气）。

出生时间填出生地的钟表时间。给了 --longitude 就按真太阳时排（经度时差 + 均时差），
不给就直接用钟表时间。均时差用常见的三角近似式，误差约半分钟，只在刻与刻、时辰与时辰
的交界处才可能有影响。
"""
import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from lunar_python import Solar
except ImportError:
    sys.exit("缺少依赖：pip install lunar_python")

DIZHI = "子丑寅卯辰巳午未申酉戌亥"
KE_NAMES = ["上刻", "中刻", "下刻"]
T = json.loads((Path(__file__).resolve().parent.parent / "data" / "tables.json").read_text(encoding="utf-8"))


def equation_of_time(d: date) -> float:
    """均时差（分钟，视太阳时 − 平太阳时）。"""
    b = 2 * math.pi * (d.timetuple().tm_yday - 81) / 364
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def true_solar(clock: datetime, longitude: float, tz_hours: float) -> datetime:
    return clock + timedelta(minutes=(longitude - tz_hours * 15) * 4 + equation_of_time(clock.date()))


def shichen_ke(h: int, mi: int) -> str:
    """原书只分上、中、下三刻而未说分法，这里把一个时辰（两小时）三等分，各 40 分钟；子时自 23:00 起。"""
    return KE_NAMES[((h * 60 + mi + 60) % 120) // 40]


def huayuan_index(month: int, hour_zhi: int) -> int:
    """花园宫：正月长生在寅，此后每月顺移一位。"""
    return (hour_zhi - (month + 1)) % 12


def jiuyao_of(xusui: int, gender: str) -> str:
    cycle = T["jiuYaoFemale"] if gender == "female" else T["jiuYaoMale"]
    return cycle[(xusui - 1) % 9]


def read(chart: datetime, gender: str, sect: int, today: date) -> dict:
    """chart 是排盘所用的时刻（真太阳时或钟表时）。"""
    solar = Solar.fromYmdHms(chart.year, chart.month, chart.day, chart.hour, chart.minute, 0)
    ec = solar.getLunar().getEightChar()
    ec.setSect(sect)
    year_gz = ec.getYear()
    hour_zhi = DIZHI.index(ec.getTime()[1])

    # 晚子时按「日柱进为次日」排时，农历日也跟着进一日
    lunar = (solar.next(1) if sect == 1 and chart.hour == 23 else solar).getLunar()
    month = abs(lunar.getMonth())

    lunar_now = Solar.fromYmd(today.year, today.month, today.day).getLunar()
    now_gz = lunar_now.getYearInGanZhiByLiChun()
    xusui = lunar_now.getYear() - lunar.getYear() + 1
    entry = T["benMingQin"][year_gz]

    return {
        "chart_time": chart.strftime("%Y-%m-%d %H:%M"),
        "benming": {"ganzhi": year_gz, "nayin": ec.getYearNaYin(), "qin": entry["qin"],
                    "verse": entry["trait"], "page": entry["page"], "note": entry.get("note")},
        "chushi": {"lunar_day": f"{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
                   **T["chuShiRi"][(lunar.getDay() - 1) % 6]},
        "shichen": {"zhi": DIZHI[hour_zhi], "ke": shichen_ke(chart.hour, chart.minute),
                    **T["shiChenXing"][hour_zhi]},
        "huayuan": {"month": month, "zhi": DIZHI[hour_zhi], **T["huaYuanGong"][huayuan_index(month, hour_zhi)]},
        "liunian": {"ganzhi": now_gz, "xusui": xusui,
                    "shen": T["liuNianShen"][(DIZHI.index(now_gz[1]) - DIZHI.index(year_gz[1])) % 12],
                    "yao": T["jiuYao"][jiuyao_of(xusui, gender)]},
    }


def to_markdown(r: dict) -> str:
    def block(label, result, v, page, note=None, extra=None):
        lines = [f"### {label}：{result}", "", f"> {v}", "", f"原书第 {page} 页" + (f"。{note}" if note else "")]
        if extra:
            lines += ["", extra]
        return "\n".join(lines)

    b, c, s, h, ln = r["benming"], r["chushi"], r["shichen"], r["huayuan"], r["liunian"]
    parts = [
        f"## 《{T['title']}》查表　（排盘时刻 {r['chart_time']}）",
        block("六十甲子生人", f"{b['ganzhi']}{b['nayin']}生人，乃为{b['qin']}", b["verse"], b["page"], b.get("note")),
        block(f"出世吉日（农历{c['lunar_day']}）", c["name"], c["verse"], c["page"], c.get("note")),
        block("生时初中末定命", f"{s['zhi']}时{s['ke']} · {s['name']}", s["verse"], s["page"], s.get("note")),
        block("男女花园宫（子息）", f"{h['month']}月{h['zhi']}时 · {h['name']}宫", h["verse"], h["page"], h.get("note")),
        block(f"{ln['ganzhi']}年流年", ln["shen"]["name"], ln["shen"]["verse"], ln["shen"]["page"], ln["shen"].get("note")),
        block(f"{ln['ganzhi']}年值命星（虚岁 {ln['xusui']}）", ln["yao"]["name"], ln["yao"]["verse"], ln["yao"]["page"],
              ln["yao"].get("note"), f"原书禳法：{ln['yao']['rite']}"),
        "---\n民间命书原文照录，供民俗文化与家族文献参考，不作任何决定的依据。"
        "〔〕为整理者校订，□ 为原书难辨之字；上中下刻按一个时辰三等分推算（原书未说分法）。",
    ]
    return "\n\n".join(parts)


def selftest() -> int:
    """期望值一律取自原书自己的表（页码见注），与循禽纪 App 的 verify 第 [14] 组相同。"""
    fails = []

    def check(name, cond, got=""):
        print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f" — got {got}"))
        if not cond:
            fails.append(name)

    std = ["甲乙丙丁戊己庚辛壬癸"[i % 10] + DIZHI[i % 12] for i in range(60)]
    check("六十甲子生人 60 条、按甲子顺序", list(T["benMingQin"]) == std)
    today = date(2026, 10, 14)
    chu = lambda y, m, d: read(datetime(y, m, d, 12, 0), "male", 2, today)["chushi"]  # noqa: E731
    check("出世吉日（P19）：农历初九 → 天父日", chu(1955, 2, 1)["name"] == "天父日", chu(1955, 2, 1))
    check("出世吉日（P19）：农历廿三 → 天帝日", chu(1990, 6, 15)["name"] == "天帝日", chu(1990, 6, 15))
    hy = lambda m, z: T["huaYuanGong"][huayuan_index(m, z)]["name"]  # noqa: E731
    check("花园宫（P73）：正月寅时长生、正月子时胎、五月辰时胎",
          (hy(1, 2), hy(1, 0), hy(5, 4)) == ("长生", "胎", "胎"), (hy(1, 2), hy(1, 0), hy(5, 4)))
    check("花园宫（P73）：十二月丑时长生、十二月午时衰", (hy(12, 1), hy(12, 6)) == ("长生", "衰"), (hy(12, 1), hy(12, 6)))
    born = datetime(1990, 6, 15, 8, 30)
    ln = lambda y: read(born, "male", 2, date(y, 7, 1))["liunian"]  # noqa: E731
    check("查流年例（P156）：庚午生人丙午年虚岁 37 → 太岁", (ln(2026)["xusui"], ln(2026)["shen"]["name"]) == (37, "太岁"))
    check("查流年例（P156）：其后丁未太阳、戊申丧门", (ln(2027)["shen"]["name"], ln(2028)["shen"]["name"]) == ("太阳", "丧门"))
    pairs = [(56, "土星", "火星"), (60, "火星", "罗睺"), (72, "木星", "水星"), (70, "计都", "太阳"), (28, "罗睺", "计都")]
    bad = [a for a, m, f in pairs if (jiuyao_of(a, "male"), jiuyao_of(a, "female")) != (m, f)]
    check("值命星与原书行年表（P170–171）抽样一致", not bad, bad)
    check("三刻：08:30 下刻、23:30 上刻、00:00 中刻",
          (shichen_ke(8, 30), shichen_ke(23, 30), shichen_ke(0, 0)) == ("下刻", "上刻", "中刻"))
    eot = equation_of_time(date(2026, 11, 3))
    check("均时差：11 月初约 +16 分", 15.5 < eot < 17, round(eot, 2))
    print(f"\n{'✅' if not fails else '❌'} {10 - len(fails)} / 10 通过")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="《袁天罡大六壬定局秘书》六张查表")
    ap.add_argument("--birth", help="出生地钟表时间，如 1990-06-15 08:30")
    ap.add_argument("--gender", choices=["male", "female"], help="值命星男女起星不同")
    ap.add_argument("--longitude", type=float, help="出生地经度（东经为正）；给出则按真太阳时排")
    ap.add_argument("--tz", type=float, default=8, help="出生时当地时区，默认 UTC+8")
    ap.add_argument("--sect", type=int, choices=[1, 2], default=2,
                    help="晚子时（23–24 点）：2＝日柱仍算当日（默认），1＝日柱算次日")
    ap.add_argument("--today", help="以哪一天定流年与虚岁，默认今天，如 2027-03-01")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--selftest", action="store_true", help="按原书自己的表做自检")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.birth or not a.gender:
        ap.error("需要 --birth 与 --gender")
    clock = datetime.strptime(a.birth.strip().replace("T", " "), "%Y-%m-%d %H:%M")
    chart = true_solar(clock, a.longitude, a.tz) if a.longitude is not None else clock
    today = datetime.strptime(a.today, "%Y-%m-%d").date() if a.today else date.today()
    r = read(chart, a.gender, a.sect, today)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else to_markdown(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
