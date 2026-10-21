#!/usr/bin/env python3
"""raw CSV + 座標キャッシュ → public/data/*.json を生成して検証する。

使い方:
  python3 scripts/build_data.py            # 生成。座標未取得は警告のみ
  python3 scripts/build_data.py --strict   # 警告もエラー扱い（公開前チェック用）
"""
import argparse
import sys
from datetime import date

from common import CATEGORIES, ROOT, load_json, load_programs, read_raw_shops, save_json

# 福岡市周辺の緯度経度範囲。外れた座標はジオコーディング誤りとみなす
BBOX = {"lat": (33.40, 33.80), "lon": (130.20, 130.60)}
MAX_COUNT_CHANGE = 0.30  # 前回出力から件数が3割以上変わったら警告


def apply_coords(shop, cache, manual):
    """手動指定 > キャッシュ の順で座標を付ける。"""
    m = manual.get(shop["id"])
    if m:
        return m["lat"], m["lon"], {"method": "manual"}
    c = cache.get(shop["address"])
    if c:
        return c["lat"], c["lon"], {"method": c.get("method", "gsi"), "query": c.get("query")}
    return None, None, None


def build(program, strict):
    errors, warnings = [], []
    shops = read_raw_shops(program)
    cache = load_json(ROOT / "cache" / "geocode-cache.json", {})
    manual = load_json(ROOT / "config" / "manual-coords.json", {})

    seen = set()
    for s in shops:
        if not s["name"] or not s["address"]:
            errors.append(f"必須項目が空: {s['name'] or s['id']}")
        if s["category"] not in CATEGORIES:
            errors.append(f"未定義のカテゴリ '{s['category']}': {s['name']}")
        if s["id"] in seen:
            errors.append(f"id 重複（同名・同住所の重複行）: {s['name']}")
        seen.add(s["id"])

        lat, lon, geo = apply_coords(s, cache, manual)
        s["lat"], s["lon"], s["geocode"] = lat, lon, geo
        if lat is None:
            warnings.append(f"座標未設定: {s['name']}（{s['address']}）")
        elif not (BBOX["lat"][0] <= lat <= BBOX["lat"][1] and BBOX["lon"][0] <= lon <= BBOX["lon"][1]):
            errors.append(f"座標が福岡市周辺の範囲外: {s['name']} ({lat}, {lon})")

    out_path = ROOT / "public" / "data" / program["file"]
    prev = load_json(out_path, [])
    if prev and abs(len(shops) - len(prev)) / len(prev) > MAX_COUNT_CHANGE:
        warnings.append(f"件数が前回 {len(prev)} → {len(shops)} と大きく変化")

    if errors or (strict and warnings):
        return None, errors, warnings

    ordered = [
        {k: s[k] for k in ("id", "name", "category", "tags", "address", "phone", "website", "note", "lat", "lon", "geocode")}
        for s in shops
    ]
    save_json(out_path, ordered)
    return ordered, errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="警告もエラー扱いにする")
    args = ap.parse_args()

    index = []
    failed = False
    for program in load_programs():
        shops, errors, warnings = build(program, args.strict)
        print(f"[{program['id']}]")
        for e in errors:
            print(f"  ERROR  {e}")
        for w in warnings[:10]:
            print(f"  WARN   {w}")
        if len(warnings) > 10:
            print(f"  WARN   ...ほか {len(warnings) - 10} 件")
        if shops is None:
            failed = True
            continue
        with_coords = sum(1 for s in shops if s["lat"] is not None)
        print(f"  OK     {len(shops)} 店舗（座標あり {with_coords}）→ public/data/{program['file']}")
        meta = {
            k: program[k]
            for k in (
                "id", "name", "issuer", "area", "source_name", "source_url", "official_url",
                "source_retrieved_at", "valid_from", "valid_to", "file", "map_center", "map_zoom",
            )
        }
        meta["shop_count"] = len(shops)
        meta["generated_at"] = date.today().isoformat()
        index.append(meta)

    if failed:
        print("エラーがあるため index.json は更新しませんでした。", file=sys.stderr)
        sys.exit(1)
    save_json(ROOT / "public" / "data" / "index.json", {"programs": index})
    print("public/data/index.json を更新しました。")


if __name__ == "__main__":
    main()
