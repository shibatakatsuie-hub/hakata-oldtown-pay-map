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
                }
            )
    return shops
