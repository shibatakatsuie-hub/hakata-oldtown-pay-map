#!/usr/bin/env python3
"""営業時間を貼り付けて CSV に入れる対話ツール。

使い方:
  python3 scripts/hours_helper.py                  # 営業時間が未入力の店を順に聞く
  python3 scripts/hours_helper.py --open           # 店ごとに Googleマップを自分のブラウザで開く
  python3 scripts/hours_helper.py --name 大博軒    # 店名の一部で1軒だけ
  python3 scripts/hours_helper.py --redo           # 入力済みの店も聞き直す
  python3 scripts/hours_helper.py --text "月曜日 11:00～14:00 火曜日 定休日 ..."   # 変換結果を表示するだけ

流れ（1軒ごと）:
  1. 店名とGoogleマップのURLが表示される → 自分で開いて営業時間の表を見る
  2. 表（月曜日〜日曜日）をコピーして貼り付ける → 7日ぶんそろうと自動で確定
     （一部の曜日だけのときは、空行を2回続けて入力すると確定）
  3. 変換結果を確認して Enter で保存（hours_checked に今日の日付が入る）
  s=スキップ  q=終了（途中まで保存済み）

注意: Googleマップの内容を自動で取得するツールではありません。ご自身で見た営業時間を
入力しやすくするだけのものです。1店ごとに確認し、写真などは取り込みません。
"""
import argparse
import csv
import sys
import webbrowser
from datetime import date

from common import ROOT, load_programs, shop_id, id_prefix, clean_text, normalize_address
from hours_text import HoursTextError, convert, is_complete_week

COLUMNS = ["name", "category", "address", "phone", "website", "note", "tags",
           "hours", "hours_note", "hours_checked", "image", "image_credit"]


def google_url(name, address):
    from urllib.parse import quote
    return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{name} {address}")


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    cols = list(rows[0].keys()) if rows else COLUMNS
    for c in COLUMNS:
        if c not in cols:
            cols.append(c)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: (r.get(c) or "") for c in cols})
    tmp.replace(path)


def read_block(prompt):
    """営業時間の貼り付けを読む。

    - 月〜日の7日ぶんが読み取れた時点で自動で確定（曜日の間に空行があってもよい）
    - 一部の曜日だけのときは、空行を2回続けて入力すると確定
    - 1行目が s / q ならそのコマンドを返す。EOF は 'q'（貼り付け済みがあればその内容）
    """
    print(prompt)
    lines = []
    blank_run = 0
    while True:
        try:
            line = input("> " if not lines else "  ")
        except EOFError:
            return "\n".join(lines) if lines else "q"
        if not lines and line.strip().lower() in ("s", "q"):
            return line.strip().lower()
        if line.strip() == "":
            blank_run += 1
            if lines and blank_run >= 2:
                return "\n".join(lines)
            continue
        blank_run = 0
        lines.append(line)
        if is_complete_week("\n".join(lines)):
            return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="営業時間を貼り付けて CSV に入れる")
    ap.add_argument("--program", default=None, help="program id（省略時は先頭）")
    ap.add_argument("--name", default=None, help="店名の一部（その店だけ）")
    ap.add_argument("--redo", action="store_true", help="入力済みの店も対象にする")
    ap.add_argument("--open", action="store_true", help="Googleマップをブラウザで開く")
    ap.add_argument("--text", default=None, help="文面を変換して表示するだけ（CSVは変更しない）")
    args = ap.parse_args()

    if args.text is not None:
        try:
            print(convert(args.text))
        except HoursTextError as e:
            print(f"変換できません: {e}", file=sys.stderr)
            sys.exit(1)
        return

    programs = load_programs()
    program = next((p for p in programs if p["id"] == args.program), programs[0]) if programs else None
    if not program:
        sys.exit("config/programs.json に program がありません。")
    path = ROOT / program["raw_csv"]
    rows = read_rows(path)
    for r in rows:
        for c in COLUMNS:
            r.setdefault(c, "")

    targets = [r for r in rows
               if (args.redo or not (r["hours"] or "").strip())
               and (not args.name or args.name in r["name"])]
    if not targets:
        print("対象の店がありません（すべて入力済みです。聞き直すなら --redo）。")
        return

    done = skipped = 0
    print(f"{program['name']}: 対象 {len(targets)} 店。途中で q を入力すると終了します（保存済みの分は残ります）。\n")
    for i, r in enumerate(targets, 1):
        url = google_url(r["name"], r["address"])
        print(f"━━ [{i}/{len(targets)}] {r['name']}  {r['address']}")
        print(f"   {url}")
        if args.open:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        while True:
            text = read_block("営業時間の表を貼り付け（7日ぶんで自動確定。一部の曜日だけなら空行を2回 / s=スキップ q=終了）:")
            if text == "q":
                print(f"\n終了します。保存 {done} 店 / スキップ {skipped} 店。")
                print("次に: python3 scripts/build_data.py --strict")
                return
            if text == "s":
                skipped += 1
                print("  → スキップ\n")
                break
            try:
                hours = convert(text)
            except HoursTextError as e:
                print(f"  ✗ {e}\n  もう一度貼り付けてください（s=スキップ）。")
                continue
            print(f"  → {hours}")
            note = input("  補足（L.O.・祝日休みなど。なければ Enter）: ").strip() if sys.stdin.isatty() else ""
            ok = input("  保存しますか？ [Enter=保存 / n=やり直し]: ").strip().lower() if sys.stdin.isatty() else ""
            if ok == "n":
                continue
            r["hours"] = hours
            r["hours_note"] = clean_text(note) if note else r.get("hours_note", "")
            r["hours_checked"] = date.today().isoformat()
            write_rows(path, rows)
            done += 1
            print("  ✓ 保存しました\n")
            break

    print(f"完了。保存 {done} 店 / スキップ {skipped} 店。")
    print("次に: python3 scripts/build_data.py --strict")


if __name__ == "__main__":
    main()
