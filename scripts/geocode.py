#!/usr/bin/env python3
"""住所 → 緯度経度（国土地理院 住所検索API）。結果は cache/geocode-cache.json に保存する。

使い方:
  python3 scripts/geocode.py              # 未取得の住所だけ問い合わせる
  python3 scripts/geocode.py --retry      # 以前に失敗した住所も再度問い合わせる
  python3 scripts/geocode.py --sleep 1.5  # 問い合わせ間隔（秒）

メモ:
  - 住居表示レベルの一致は保証されない。町丁目〜街区レベルに丸められることがある。
    ずれが目立つ店は config/manual-coords.json に {"<shop id>": {"lat": .., "lon": ..}} で上書きする。
  - APIの利用条件は国土地理院の案内を確認すること。短時間に大量アクセスしない。
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

from common import ROOT, load_json, load_programs, read_raw_shops, save_json

API = "https://msearch.gsi.go.jp/address-search/AddressSearch?q="
CACHE_PATH = ROOT / "cache" / "geocode-cache.json"
USER_AGENT = "hakata-oldtown-pay-map/0.1 (personal project; geocoding with 1 req/sec)"


def candidates(address):
    """精度の高い順に検索クエリ候補を作る。

    '福岡市博多区上呉服町10-29 1F' → 福岡県福岡市博多区上呉服町10-29 → 福岡県福岡市博多区上呉服町10
    """
    base = re.split(r"[\s(（]", address)[0]
    base = re.sub(r"(\d+)丁目(?=\d)", r"\1-", base)  # 2丁目19-29 -> 2-19-29
    base = re.sub(r"(\d+)番(?=\d)", r"\1-", base)    # 13番1号 -> 13-1号
    base = base.replace("号", "").replace("丁目", "")
    if not base.startswith("福岡県"):
        base = "福岡県" + base
    m = re.match(r"^(\D+?)(\d+(?:-\d+)*)$", base)
    if not m:
        return [base]
    head, nums = m.group(1), m.group(2).split("-")
    return [head + "-".join(nums[:n]) for n in range(len(nums), 0, -1)]


def town_name(query):
    m = re.search(r"区(.+?)\d", query)
    return m.group(1) if m else ""


def ward_name(query):
    """'福岡県福岡市中央区春吉1-7' → '福岡市中央区'。区が読めなければ '福岡市'。"""
    m = re.search(r"福岡市(.+?区)", query)
    return "福岡市" + m.group(1) if m else "福岡市"


def pick(features, query):
    """API結果から、同じ市区・同じ町名を含む最初の候補を選ぶ（別の区の同名地名を拾わない）。"""
    town = town_name(query)
    ward = ward_name(query)
    for f in features or []:
        title = (f.get("properties") or {}).get("title", "")
        coords = (f.get("geometry") or {}).get("coordinates")
        if ward in title and town in title and coords and len(coords) >= 2:
            return {"lat": round(coords[1], 6), "lon": round(coords[0], 6), "matched_title": title}
    return None


def fetch(query, timeout=15):
    req = urllib.request.Request(API + urllib.parse.quote(query), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retry", action="store_true", help="失敗済みの住所も再試行")
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    cache = load_json(CACHE_PATH, {})
    failed = load_json(ROOT / "cache" / "geocode-failed.json", [])
    addresses = []
    for program in load_programs():
        for s in read_raw_shops(program):
            if s["address"] not in addresses:
                addresses.append(s["address"])

    todo = [a for a in addresses if a not in cache and (args.retry or a not in failed)]
    print(f"対象 {len(addresses)} 住所のうち、未取得 {len(todo)} 件を問い合わせます。")
    consecutive_errors = 0
    newly_failed = []
    for i, addr in enumerate(todo, 1):
        found = None
        for q in candidates(addr):
            try:
                found = pick(fetch(q), q)
                consecutive_errors = 0
            except Exception as e:  # ネットワーク/JSON エラー
                consecutive_errors += 1
                print(f"  通信エラー: {e}", file=sys.stderr)
                if consecutive_errors >= 3:
                    print("3回連続で通信に失敗したため中断します。ここまでの結果は保存済みです。", file=sys.stderr)
                    save_json(CACHE_PATH, cache)
                    sys.exit(2)
            time.sleep(args.sleep)
            if found:
                found.update({"query": q, "method": "gsi", "at": date.today().isoformat()})
                break
        if found:
            cache[addr] = found
            print(f"  [{i}/{len(todo)}] OK   {addr} → {found['matched_title']}")
            save_json(CACHE_PATH, cache)
        else:
            newly_failed.append(addr)
            print(f"  [{i}/{len(todo)}] FAIL {addr}")

    save_json(ROOT / "cache" / "geocode-failed.json", sorted(set(newly_failed)))
    print(f"完了: 成功 {len(todo) - len(newly_failed)} / 失敗 {len(newly_failed)}")
    if newly_failed:
        print("失敗した住所は config/manual-coords.json に手動で座標を入れるか、住所表記を見直してください。")
    print("次に: python3 scripts/build_data.py")


if __name__ == "__main__":
    main()
