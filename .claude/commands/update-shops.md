---
description: 公式サイトの利用可能店舗一覧から raw CSV を更新し、JSON を再生成して差分を報告する
argument-hint: [program-id（省略時は hakata-oldtown-pay）]
---

program-id は `$ARGUMENTS`（空なら `hakata-oldtown-pay`）。次の手順で更新してください。CLAUDE.md の方針に従うこと。

1. `config/programs.json` から対象の `source_url` と `raw_csv` を確認する。
2. `source_url` を WebFetch で取得し、全店舗の 店名・住所・電話・店舗サイトURL・カテゴリ・利用条件メモ を抽出する。
   - ページ内の掲載店舗数（「現在 N 店舗掲載中」など）と、抽出した件数が一致するか確認する。一致しなければ取りこぼしを探す。
   - 紹介文・写真は取り込まない。
   - 「本店のみ」「夜限定」などの注意書きは `note` に、コンビニ・ドラッグストアは `tags` に入れる。
3. 現在の CSV と比べ、追加・削除・変更された店舗を一覧にする（この時点ではまだ書き換えない）。
4. `raw/<program>.csv` を更新する（列: name, category, address, phone, website, note, tags, hours, hours_note, hours_checked, image, image_credit）。
   - 既存の店の `hours` / `hours_note` / `hours_checked` / `image` / `image_credit` は**そのまま残す**（公式一覧には載っていない、手入力・許諾済みの情報）。
   - 閉店・加盟終了した店の行を消すときは、対応する画像ファイルが他で使われていないか確認して報告する。
5. `python3 scripts/geocode.py` を実行する（新しい住所だけ問い合わせる）。通信できない環境では、実行できなかったと報告して手順を止めずに先へ進む。
6. `python3 scripts/build_data.py --strict` と `node tests/lib.test.js` を実行する。
7. `config/programs.json` の `source_retrieved_at` を今日の日付に更新して、手順 6 を再実行する。
8. 最後に、追加 N 件・削除 N 件・変更 N 件、座標が付かなかった店、確認が必要な点を短く報告する。コミットや push はしない。
