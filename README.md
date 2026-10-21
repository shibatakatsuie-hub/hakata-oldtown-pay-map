# 博多旧市街PAY 加盟店マップ（非公式）

博多旧市街PAYの利用可能店舗を、スマホの地図で探せる静的サイトです。
サーバ不要（HTML + JavaScript + Leaflet + JSON）で、Cloudflare Pages の無料枠で動かせます。

> 本サイトは非公式の加盟店検索サービスです。発行者（御供所名店会）・運営事務局とは関係がありません。

## できること

- 店名・住所の検索、カテゴリ（飲食・宿泊・小売…）とコンビニの絞り込み
- 現在地から近い順の並び替え、500m / 1km / 2km 以内の絞り込み
- 店ごとの「Googleマップ」ボタン（店名＋住所で検索 → 営業時間・口コミ・写真を Google 側で確認）
- 「本店のみ利用可」「夜限定」などの利用条件メモの表示
- 非公式の明示・出典・取得日の表示

営業時間はデータに持ちません（公式の一覧に載っておらず、Google の営業時間を保存して再配布することも避けるため）。

## 構成

```
public/                  ← これをそのまま公開（Cloudflare Pages の出力ディレクトリ）
  index.html app.js style.css lib.js _headers
  data/index.json        ← 地域（プログラム）の一覧と出典情報。build_data.py が生成
  data/hakata-oldtown-pay.json   ← 店舗データ。build_data.py が生成
raw/hakata-oldtown-pay.csv       ← 店舗データの元（人とAIが編集する唯一のソース）
config/programs.json             ← 出典URL・利用期間・地図の初期位置など
config/manual-coords.json        ← 座標の手動上書き  {"<店舗id>": {"lat": 33.59, "lon": 130.41}}
cache/geocode-cache.json         ← 住所→座標のキャッシュ（geocode.py が生成）
scripts/                         ← build_data.py / geocode.py / common.py
tests/lib.test.js                ← 絞り込み・距離計算のテスト
CLAUDE.md, .claude/commands/     ← Claude Code 用の更新手順
```

## はじめかた（ローカル）

```bash
# 1. 住所 → 緯度経度（国土地理院の住所検索API。初回のみ。約76〜150秒）
python3 scripts/geocode.py

# 2. JSON を生成・検証
python3 scripts/build_data.py            # 公開前は --strict を付ける（座標漏れもエラーにする）

# 3. 確認
python3 -m http.server -d public 8000    # http://localhost:8000
node tests/lib.test.js
```

**初期状態では店舗に座標が入っていません**（作成環境から住所検索APIに接続できなかったため）。
手順 1 を実行するまで、地図にピンは出ず、一覧と Google マップ遷移だけが動きます。
住所の精度は街区（番地）レベルに丸められる場合があります。ずれが目立つ店は `config/manual-coords.json` で上書きしてください。

## Cloudflare Pages へ公開

1. GitHub にこのフォルダを push する
2. Cloudflare Pages で「Git を接続」→ リポジトリを選択
3. ビルドコマンド: なし（空欄） / ビルド出力ディレクトリ: `public`
4. 以降は push するたびに自動デプロイ

無料プランはビルド回数が月500回までなので、データ更新はまとめて push するのがおすすめです。

## データ更新の流れ

```
公式サイトの「利用可能店舗」→ raw/hakata-oldtown-pay.csv を更新
 → python3 scripts/geocode.py（新しい住所だけ問い合わせ）
 → python3 scripts/build_data.py --strict
 → git commit / push → 自動デプロイ
```

Claude Code では `/update-shops hakata-oldtown-pay` で、CSV の更新から差分確認までをまとめて実行できます（`.claude/commands/update-shops.md`）。

## 公開前チェックリスト

- [ ] 発行者（御供所名店会 / 080-4122-1923）へ、店舗情報の掲載について連絡・確認した
      （公式サイトの利用規約は商品券の利用者向けで、掲載情報の転載条件は記載が見当たりません。許諾の代わりにはなりません）
- [ ] 公式サイトの店舗情報（店名・住所・電話）以外を転載していない（紹介文・写真は転載しない方針です）
- [ ] 「非公式」「出典」「取得日」が画面に表示されている
- [ ] `python3 scripts/build_data.py --strict` が通る
- [ ] 利用期間（〜2026-12-31）後の扱い（公開終了 or 次回分への更新）を決めた

## 補足

- **地図タイル**: 既定は OpenStreetMap の公式タイルです。アクセスが増えると利用ポリシー上の問題になり得るため、`public/app.js` 冒頭の `TILE` を国土地理院タイル等に切り替えられます。
- **Leaflet は CDN（unpkg）から読み込み**ています。自前配信にしたい場合は、ローカルで `npm i leaflet@1.9.4 leaflet.markercluster@1.5.3` し、`dist/` の中身を `public/vendor/` にコピーして `index.html` の URL を書き換えてください。
- **カテゴリ**は公式の分類ではなく、このプロジェクトでの独自分類です（`scripts/common.py` の `CATEGORIES`）。
- 店舗の加盟開始日は店ごとに異なります。公式サイトも「利用準備が整っていない場合がある」と案内しているため、画面にも同じ注意を出しています。
