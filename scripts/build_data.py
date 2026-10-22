#!/usr/bin/env python3
"""raw CSV + 座標キャッシュ → public/data/*.json を生成して検証する。

使い方:
  python3 scripts/build_data.py            # 生成。座標未取得は警告のみ
  python3 scripts/build_data.py --strict   # 警告もエラー扱い（公開前チェック用）
"""
import argparse
import re
import sys
from datetime import date

from common import CATEGORIES, ROOT, load_json, load_programs, parse_hours, read_raw_shops, save_json

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


def build_hours(s, errors):
    """CSV の hours 列 → {weekly, note, checked_at}。空なら None（画面には出さない）。"""
    if not s["hours_raw"]:
        if s["hours_note"]:
            errors.append(f"hours_note だけがあり hours が空: {s['name']}")
        return None
    try:
        weekly = parse_hours(s["hours_raw"])
    except ValueError as e:
        errors.append(f"営業時間の書式エラー: {s['name']}: {e}")
        return None
    if not s["hours_checked"] or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["hours_checked"]):
        errors.append(f"hours_checked（確認日 YYYY-MM-DD）が必要です: {s['name']}")
    return {"weekly": weekly, "note": s["hours_note"], "checked_at": s["hours_checked"]}


def build_image(s, errors, warnings):
    """CSV の image 列（ファイル名）→ {src, credit}。許諾の出所（credit）を必須にする。"""
    name = s["image_file"]
    if not name:
        if s["image_credit"]:
            warnings.append(f"image_credit だけがあり image が空: {s['name']}")
        return None
    if "/" in name or ".." in name or not re.fullmatch(r"[\w.-]+\.(jpg|jpeg|png|webp)", name, re.I):
        errors.append(f"image はファイル名のみ（jpg/png/webp）で指定してください: {s['name']}: {name}")
        return None
    path = ROOT / "public" / "img" / "shops" / name
    if not path.exists():
        errors.append(f"画像ファイルがありません: public/img/shops/{name}（{s['name']}）")
        return None
    if not s["image_credit"]:
        errors.append(f"image_credit（撮影者・提供元・許諾の出所）が必要です: {s['name']}")
        return None
    kb = path.stat().st_size / 1024
    if kb > 300:
        warnings.append(f"画像が大きすぎます（{kb:.0f}KB。300KB以下を推奨）: {name}")
    return {"src": f"img/shops/{name}", "credit": s["image_credit"]}


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

        s["hours"] = build_hours(s, errors)
        s["image"] = build_image(s, errors, warnings)

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
        {k: s[k] for k in ("id", "name", "category", "tags", "address", "phone", "website", "note", "hours", "image", "lat", "lon", "geocode")}
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
