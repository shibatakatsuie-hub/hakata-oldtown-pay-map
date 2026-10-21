# CLAUDE.md — 博多旧市街PAY 加盟店マップ

非公式の加盟店検索サイト。静的サイト（public/）+ JSON。サーバなし、無料運用、スマホ中心。

## 守ること

- 店舗データは **店名・住所・電話・店舗サイトURL・カテゴリ・利用条件メモ** の事実情報だけを持つ。
  公式サイトの紹介文・写真は転載しない。営業時間も持たない（Google マップで確認してもらう）。
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

CSV の列: `name, category, address, phone, website, note, tags`（tags は `;` 区切り）
カテゴリは `scripts/common.py` の `CATEGORIES` のいずれか。コンビニは `tags` に「コンビニ」。
`note` には「本店のみ利用可」「夜限定」など利用条件を短く書く。

## 更新するとき

`/update-shops <program-id>` を使う（`.claude/commands/update-shops.md`）。
手動なら: CSV を更新 → `python3 scripts/geocode.py` → `python3 scripts/build_data.py --strict` → `node tests/lib.test.js`。

## 検証の目安

- 件数が前回から大きく変わった（±30%超）場合は、取り込みミスを疑って公式ページと突き合わせる。
- 座標が福岡市周辺の範囲外ならエラー（build_data.py が検出）。
- 同名・同住所の重複行はエラー。支店は店名に支店名を含める。

## 新しい地域（プログラム）を足す

1. `config/programs.json` に項目を追加（`id`, `source_url`, `raw_csv`, `file`, `map_center` など）
2. `raw/<id>.csv` を作る
3. `python3 scripts/build_data.py`。画面は `?program=<id>` で切り替わる。
