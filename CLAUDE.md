# CLAUDE.md — プレミアム商品券 加盟店マップ（非公式）

複数の券（博多旧市街PAY、中洲がんばっとう2026 など）を扱う、非公式の加盟店検索サイト。静的サイト（public/）+ JSON。サーバなし、無料運用、スマホ中心。

## 守ること

- 店舗データは **店名・住所・電話・店舗サイトURL・カテゴリ・利用条件メモ** の事実情報が基本。
  公式サイトの紹介文は転載しない。
- **営業時間**（`hours` 列）は、店舗の公式サイト・SNS、または店舗・名店会から得た情報だけを手入力し、`hours_checked` に確認日を入れる。
  **Google マップ/Places API の営業時間・写真は取得・保存しない**（規約上 place_id 以外は保存不可）。推測で営業時間を書かない。
- **画像**（`image` 列）は、許諾を得たものだけを `public/img/shops/` に置く。他サイトの画像を直リンクしない。`image_credit` に提供元・許諾の出所を必ず書く。
- 「非公式」「出典」「取得日」の表示を消さない。
- `public/data/*.json` は **直接編集しない**。元データは `raw/*.csv`、生成は `scripts/build_data.py`。
- 利用規約・許諾が未確認のデータは公開しない（`config/programs.json` の `license_status` を参照）。
- 座標を推測で書かない。`geocode.py` の結果か、`config/manual-coords.json` の手動指定だけを使う。
- 本番に影響する変更は、直接 main に入れずブランチ + PR にする。

## データの流れ

```
raw/<program>.csv  →  scripts/geocode.py  →  cache/geocode-cache.json
                   →  scripts/build_data.py [--strict]  →  public/data/*.json
```

CSV の列: `name, category, address, phone, website, note, tags, hours, hours_note, hours_checked, image, image_credit`（tags は `;` 区切り）
`hours` の書式: `月-金 11:00-14:00,17:00-22:00; 土 11:00-22:00; 日 休`（深夜は `18:00-26:00`）。詳細は README。
営業時間の手入力は `python3 scripts/hours_helper.py`（貼り付け→書式に変換→CSVへ保存）を使う。Google マップのページを自動で取得するスクリプトは作らない。
カテゴリは `scripts/common.py` の `CATEGORIES` のいずれか。コンビニは `tags` に「コンビニ」。
`note` には「本店のみ利用可」「夜限定」など利用条件を短く書く。

## 更新するとき

`/update-shops <program-id>` を使う（`.claude/commands/update-shops.md`）。
手動なら: CSV を更新 → `python3 scripts/geocode.py` → `python3 scripts/build_data.py --strict` → `node tests/lib.test.js`。

## 検証の目安

- 件数が前回から大きく変わった（±30%超）場合は、取り込みミスを疑って公式ページと突き合わせる。
- 座標が福岡市周辺の範囲外ならエラー（build_data.py が検出）。
- 同名・同住所の重複行はエラー。支店は店名に支店名を含める。

## 新しい券（プログラム）を足す

1. `config/programs.json` に項目を追加（`id`, `source_url`, `raw_csv`, `file`, `map_center`, `notice` など。利用期間が不明なら `valid_from`/`valid_to` は null）
2. `raw/<id>.csv` を作る（住所は市区から。電話は `092-123-4567` 形式）
3. `python3 scripts/geocode.py` → `python3 scripts/build_data.py --strict`。画面の「券・地域」と `?program=<id>` で切り替わる。
4. 公式ページから取れなかった情報（利用期間、電子版/冊子版の別 など）は、推測で埋めず、`notice` と `license_note` に「不明」と明記する。
