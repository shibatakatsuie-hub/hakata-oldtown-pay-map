"""営業時間の文面（Googleマップなどで見た表記）→ CSV の hours 列の書式へ変換する。標準ライブラリのみ。

受け付ける例:
  月曜日            月曜日 11:00～14:00, 17:00～22:00      Monday 11:00 AM – 2:00 PM
  11:00～14:00      火曜日 定休日                          Tuesday Closed
  17:00～22:00      水曜日(祝日) 24 時間営業               午前11:00～午後2:00
  ...（曜日の見出しの次に時間が来る形式、1行に並んだ形式のどちらも可）

出力: 月-金 11:00-14:00,17:00-22:00; 土 11:00-22:00; 日 休
"""
import re
import unicodedata

from common import DAY_CHARS, parse_hours

_EN_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DAY_MARK = re.compile(
    r"(?P<jp>[月火水木金土日])曜日?(?:\s*[（(][^）)]*[）)])?"
    r"|\b(?P<en>" + "|".join(_EN_DAYS) + r")\b",
    re.I,
)
_RANGE = re.compile(
    r"(?P<m1>午前|午後)?\s*(?P<h1>\d{1,2}):(?P<n1>\d{2})\s*(?P<a1>[AaPp]\.?[Mm]\.?)?"
    r"\s*[～~〜–—−\-]\s*"
    r"(?P<m2>午前|午後|翌)?\s*(?P<h2>\d{1,2}):(?P<n2>\d{2})\s*(?P<a2>[AaPp]\.?[Mm]\.?)?"
)
_CLOSED = re.compile(r"定休|休業|休み|closed|休$", re.I)
_ALL_DAY = re.compile(r"24\s*時間|24\s*hours", re.I)


class HoursTextError(ValueError):
    pass


def _normalize_times(text):
    """'18時00分' '18時30分' '18時' '18時半' → '18:00' '18:30' '18:00' '18:30'（'24時間' は触らない）。"""
    text = re.sub(r"(\d{1,2})\s*時\s*(\d{1,2})\s*分", lambda m: f"{m[1]}:{int(m[2]):02d}", text)
    text = re.sub(r"(\d{1,2})\s*時\s*半", r"\1:30", text)
    return re.sub(r"(\d{1,2})\s*時(?![間\d])", r"\1:00", text)


def is_complete_week(text):
    """月〜日の7日ぶんがすべて読み取れる文面か（貼り付けの自動確定の判定に使う）。"""
    try:
        return all(d is not None for d in parse_text(text))
    except HoursTextError:
        return False


def _to24(h, ampm):
    """ampm: 'am' / 'pm' / None。None のときは 24時間表記としてそのまま。"""
    if ampm is None:
        return h
    return (h % 12) + (12 if ampm == "pm" else 0)


def _marker(jp, en):
    if jp == "午前":
        return "am"
    if jp == "午後":
        return "pm"
    if en:
        return "am" if en.lower().startswith("a") else "pm"
    return None


def _spans_from_body(body):
    body = body.strip()
    if _ALL_DAY.search(body):
        return [["00:00", "24:00"]]
    spans = []
    for m in _RANGE.finditer(body):
        m1, m2 = _marker(m["m1"], m["a1"]), _marker(m["m2"], m["a2"])
        if m1 is None and m2 is not None:
            m1 = m2  # '5:00 – 10:00 PM' のように前側が省略された表記
        h1, h2 = _to24(int(m["h1"]), m1), _to24(int(m["h2"]), m2)
        spans.append([f"{h1:02d}:{m['n1']}", f"{h2:02d}:{m['n2']}"])
    if spans:
        return spans
    if _CLOSED.search(body):
        return []
    return None  # 読み取れない


def parse_text(text):
    """文面 → [None|[]|[[start,end],...]] × 7（月〜日）。読めない・重複・曜日なしは HoursTextError。"""
    text = _normalize_times(unicodedata.normalize("NFKC", text or ""))
    marks = list(_DAY_MARK.finditer(text))
    if not marks:
        raise HoursTextError("曜日（月曜日…日曜日）が見つかりません。曜日の行も一緒に貼り付けてください。")
    week = [None] * 7
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        day = DAY_CHARS.index(m["jp"]) if m["jp"] else _EN_DAYS.index(m["en"].lower())
        spans = _spans_from_body(text[m.end():end])
        if spans is None:
            label = DAY_CHARS[day] + "曜日"
            raise HoursTextError(f"{label}の時間を読み取れません: 「{text[m.end():end].strip()[:30]}」")
        if week[day] is not None:
            raise HoursTextError(f"{DAY_CHARS[day]}曜日が2回出てきます。貼り付けた内容を確認してください。")
        week[day] = spans
    return week


def _runs(days):
    runs, cur = [], [days[0]]
    for d in days[1:]:
        if d == cur[-1] + 1:
            cur.append(d)
        else:
            runs.append(cur)
            cur = [d]
    runs.append(cur)
    return runs


def _day_spec(days):
    parts = []
    for r in _runs(sorted(days)):
        if len(r) >= 3:
            parts.append(f"{DAY_CHARS[r[0]]}-{DAY_CHARS[r[-1]]}")
        else:
            parts += [DAY_CHARS[d] for d in r]
    return "・".join(parts)


def format_week(week):
    """週の配列 → hours 列の書式。同じ時間の曜日はまとめる。"""
    groups = {}
    for d, spans in enumerate(week):
        if spans is None:
            continue
        key = "休" if not spans else ",".join(f"{a}-{b}" for a, b in spans)
        groups.setdefault(key, []).append(d)
    if len(groups) == 1 and sum(len(v) for v in groups.values()) == 7:
        return "毎日 " + next(iter(groups))
    return "; ".join(f"{_day_spec(days)} {key}" for key, days in groups.items())


def convert(text):
    """文面 → hours 列の文字列。CSV に入れる前に、実際の読み込み処理で解釈できるか往復検証する。"""
    week = parse_text(text)
    out = format_week(week)
    if parse_hours(out) != week:
        raise HoursTextError("変換結果の検証に失敗しました（内部エラー）: " + out)
    return out
