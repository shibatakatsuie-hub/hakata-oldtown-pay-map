"""build_data.py と geocode.py で共有する関数。標準ライブラリのみ。"""
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CATEGORIES = [
    "飲食",
    "宿泊",
    "小売・販売",
    "サービス",
    "美容・エステ",
    "ジュエリー・ファッション",
    "健康・医療",
    "その他",
]

# URL のクエリを残してよいもの（それ以外は追跡パラメータ除去のため落とす）
KEEP_QUERY_PATTERNS = ("hakataumauma.com", "matsukiyococokara-online.com", "facebook.com/profile.php")


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data, indent=1):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    tmp.replace(path)


def clean_text(s):
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip()


def normalize_address(s):
    """表示・照合用に住所を整える。例: '福岡県福岡市博多区博多駅東 1-1-29' -> '福岡市博多区博多駅東1-1-29'"""
    s = clean_text(s)
    s = re.sub(r"^福岡県", "", s)
    # 数字に挟まれたハイフン類を '-' に統一（ー・−・‐ など）
    s = re.sub(r"(?<=\d)[ー−‐‑–—－-](?=\d)", "-", s)
    # 日本語の直後の空白＋数字（'博多駅東 1-1-29'）は詰める
    s = re.sub(r"(?<=[^\x00-\x7f]) (?=\d)", "", s)
    return s


def normalize_phone(s):
    s = clean_text(s)
    return s if re.fullmatch(r"\d{2,4}-\d{2,4}-\d{4}", s) else None


def normalize_url(url):
    url = (url or "").strip()
    if not url:
        return None
    if not any(p in url for p in KEEP_QUERY_PATTERNS):
        url = re.split(r"[?#]", url)[0]
    return url


DAY_CHARS = "月火水木金土日"  # weekly の並び順（月曜始まり）
_DASH = r"[-~〜–—−ー]"
_TIME = r"(\d{1,2}):(\d{2})"


def _expand_days(spec):
    """'月-金' '土' '月・水・金' '毎日' → 曜日番号(0=月)のリスト。"""
    spec = spec.strip()
    if spec in ("毎日", "全日"):
        return list(range(7))
    days = []
    for part in re.split(r"[・,、]", spec):
        part = part.strip()
        m = re.fullmatch(f"([{DAY_CHARS}]){_DASH}([{DAY_CHARS}])", part)
        if m:
            a, b = DAY_CHARS.index(m.group(1)), DAY_CHARS.index(m.group(2))
            n = (b - a) % 7
            days += [(a + i) % 7 for i in range(n + 1)]
        elif len(part) == 1 and part in DAY_CHARS:
            days.append(DAY_CHARS.index(part))
        else:
            raise ValueError(f"曜日を解釈できません: '{part}'")
    return days


def parse_hours(text):
    """営業時間の簡易表記を 7要素の配列(月〜日)に変換する。

    書式:  月-金 11:00-14:00,17:00-22:00; 土 11:00-22:00; 日 休
      - 区切りは ';'、曜日と時間は半角スペース。時間帯は ',' 区切りで複数可。
      - '休' は定休日。深夜営業は '18:00-26:00' か '18:00-02:00'（終了が開始より小さい場合は翌日扱い）。
      - 書かれていない曜日は不明(None)。全曜日が不明なら ValueError。
    戻り値: [None | [] | [["11:00","14:00"], ...]] × 7
    """
    text = clean_text(text)
    if not text:
        return None
    week = [None] * 7
    for seg in re.split(r"[;；]", text):
        seg = seg.strip()
        if not seg:
            continue
        try:
            days_part, time_part = seg.split(" ", 1)
        except ValueError:
            raise ValueError(f"'曜日 時間' の形になっていません: '{seg}'")
        days = _expand_days(days_part)
        time_part = time_part.strip()
        if time_part in ("休", "定休", "定休日", "休み"):
            spans = []
        else:
            spans = []
            for t in re.split(r"[,、]", time_part):
                m = re.fullmatch(f"{_TIME}{_DASH}{_TIME}", t.strip())
                if not m:
                    raise ValueError(f"時間帯を解釈できません: '{t.strip()}'")
                h1, m1, h2, m2 = (int(x) for x in m.groups())
                if h1 > 27 or h2 > 29 or m1 > 59 or m2 > 59:
                    raise ValueError(f"時刻が範囲外です: '{t.strip()}'")
                spans.append([f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"])
        for d in days:
            if week[d] is not None:
                raise ValueError(f"{DAY_CHARS[d]}曜日が重複しています")
            week[d] = spans
    if all(d is None for d in week):
        raise ValueError("営業時間が空です")
    return week


def shop_id(prefix, name, address):
    h = hashlib.sha1(f"{name}|{address}".encode("utf-8")).hexdigest()[:6]
    return f"{prefix}-{h}"


def load_programs():
    return load_json(ROOT / "config" / "programs.json", [])


def id_prefix(program):
    return "".join(w[0] for w in program["id"].split("-"))  # hakata-oldtown-pay -> hop


def read_raw_shops(program):
    """raw CSV を読み、正規化した店舗 dict のリストを返す（座標は含まない）。"""
    path = ROOT / program["raw_csv"]
    shops = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = clean_text(row["name"])
            address = normalize_address(row["address"])
            tags = [clean_text(t) for t in (row.get("tags") or "").split(";") if clean_text(t)]
            shops.append(
                {
                    "id": shop_id(id_prefix(program), name, address),
                    "name": name,
                    "category": clean_text(row["category"]),
                    "tags": tags,
                    "address": address,
                    "phone": normalize_phone(row.get("phone")),
                    "website": normalize_url(row.get("website")),
                    "note": clean_text(row.get("note")) or None,
                    "hours_raw": clean_text(row.get("hours")),
                    "hours_note": clean_text(row.get("hours_note")) or None,
                    "hours_checked": clean_text(row.get("hours_checked")) or None,
                    "image_file": (row.get("image") or "").strip(),
                    "image_credit": clean_text(row.get("image_credit")),
                }
            )
    return shops
