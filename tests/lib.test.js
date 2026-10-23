// 実行: node tests/lib.test.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Lib = require('../public/lib.js');

// 距離: 博多駅 ↔ 天神駅 はおよそ 2.0〜2.6 km
const d = Lib.haversineMeters(33.5898, 130.4207, 33.5910, 130.3990);
assert.ok(d > 1900 && d < 2300, 'distance ' + d);
assert.equal(Lib.haversineMeters(33.5, 130.4, 33.5, 130.4), 0);

// Google マップ URL: 店名+住所を URL エンコード
const url = Lib.googleMapsUrl({ name: '焼鳥 たんべ', address: '福岡市博多区上呉服町10-29 1F' });
assert.ok(url.startsWith('https://www.google.com/maps/search/?api=1&query='));
assert.equal(decodeURIComponent(url.split('query=')[1]), '焼鳥 たんべ 福岡市博多区上呉服町10-29 1F');

assert.equal(Lib.formatDistance(4), '10 m');
assert.equal(Lib.formatDistance(347), '350 m');
assert.equal(Lib.formatDistance(1260), '1.3 km');

const shops = [
  { id: 'a', name: 'セブン-イレブン 博多駅前1丁目店', category: '小売・販売', tags: ['コンビニ'], address: '福岡市博多区博多駅前1丁目13番1号', lat: 33.5900, lon: 130.4200 },
  { id: 'b', name: '焼鳥 たんべ', category: '飲食', tags: [], address: '福岡市博多区上呉服町10-29 1F', lat: 33.5920, lon: 130.4090 },
  { id: 'c', name: 'オートザッケ', category: 'サービス', tags: [], address: '福岡市博多区上呉服町6-31', lat: null, lon: null },
  { id: 'd', name: '梨庵', category: '飲食', tags: [], address: '福岡市博多区御供所町3-17-5', lat: 33.5885, lon: 130.4150 }
];

// 原点なし: データ順のまま、座標なしも残る
let rows = Lib.selectShops(shops, { query: '', facet: { type: 'all' }, radiusM: null, origin: null });
assert.deepEqual(rows.map(r => r.shop.id), ['a', 'b', 'c', 'd']);
assert.ok(rows.every(r => r.distance === null));

// 半角カナ・全角英数の正規化と複数語（AND）の検索
rows = Lib.selectShops(shops, { query: 'ｾﾌﾞﾝ 博多駅前１', facet: { type: 'all' }, radiusM: null, origin: null });
assert.deepEqual(rows.map(r => r.shop.id), ['a']);

// カテゴリ・タグ
rows = Lib.selectShops(shops, { query: '', facet: { type: 'category', value: '飲食' }, radiusM: null, origin: null });
assert.deepEqual(rows.map(r => r.shop.id), ['b', 'd']);
rows = Lib.selectShops(shops, { query: '', facet: { type: 'tag', value: 'コンビニ' }, radiusM: null, origin: null });
assert.deepEqual(rows.map(r => r.shop.id), ['a']);

// 原点あり: 近い順、座標なしは末尾
const origin = { lat: 33.5885, lon: 130.4150 };
rows = Lib.selectShops(shops, { query: '', facet: { type: 'all' }, radiusM: null, origin });
assert.equal(rows[0].shop.id, 'd');
assert.equal(rows[rows.length - 1].shop.id, 'c');
assert.ok(rows[0].distance < rows[1].distance);

// 距離フィルタ: 座標なしは除外される
rows = Lib.selectShops(shops, { query: '', facet: { type: 'all' }, radiusM: 1000, origin });
assert.ok(rows.every(r => r.distance !== null && r.distance <= 1000));
assert.ok(!rows.some(r => r.shop.id === 'c'));

// ファセット件数
const facets = Lib.buildFacets(shops);
assert.equal(facets[0].count, 4);
assert.equal(facets.find(f => f.value === '飲食').count, 2);
assert.equal(facets.find(f => f.type === 'tag' && f.value === 'コンビニ').count, 1);

// ---- 営業時間（日本時間で判定。2026-10-21 は水曜、10-22 は木曜）----
const at = s => new Date(s + '+09:00');
const wk = { // 月〜日: 平日昼夜2部、土は深夜2時まで、日は定休、火は不明
  weekly: [
    [['11:00', '14:00'], ['17:00', '22:00']], null,
    [['11:00', '14:00'], ['17:00', '22:00']], [['11:00', '14:00'], ['17:00', '22:00']],
    [['11:00', '14:00'], ['17:00', '22:00']], [['18:00', '26:00']], []
  ], note: 'L.O. 30分前', checked_at: '2026-10-01'
};
assert.deepEqual(Lib.jstParts(at('2026-10-21T12:30:00')), { day: 2, min: 750 });
// 端末が UTC でも日本時間で判定する（UTC 03:30 = JST 12:30）
assert.deepEqual(Lib.jstParts(new Date('2026-10-21T03:30:00Z')), { day: 2, min: 750 });

assert.deepEqual(Lib.openStatus(wk, at('2026-10-21T12:30:00')), { state: 'open', closesAt: '14:00' });
assert.deepEqual(Lib.openStatus(wk, at('2026-10-21T15:00:00')), { state: 'closed' });
assert.deepEqual(Lib.openStatus(wk, at('2026-10-21T14:00:00')), { state: 'closed' }, '終了時刻ちょうどは閉店');
assert.deepEqual(Lib.openStatus(wk, at('2026-10-21T11:00:00')), { state: 'open', closesAt: '14:00' }, '開始時刻ちょうどは営業中');
assert.deepEqual(Lib.openStatus(wk, at('2026-10-20T12:00:00')), { state: 'unknown' }, '火曜は不明');
assert.deepEqual(Lib.openStatus(wk, at('2026-10-25T12:00:00')), { state: 'closed' }, '日曜は定休');
// 土曜 18:00-26:00 → 日曜 01:00 はまだ営業中、日曜 03:00 は閉店
assert.deepEqual(Lib.openStatus(wk, at('2026-10-24T23:00:00')), { state: 'open', closesAt: '02:00' });
assert.deepEqual(Lib.openStatus(wk, at('2026-10-25T01:00:00')), { state: 'open', closesAt: '02:00' });
assert.deepEqual(Lib.openStatus(wk, at('2026-10-25T03:00:00')), { state: 'closed' });
assert.deepEqual(Lib.openStatus(null, at('2026-10-21T12:00:00')), { state: 'unknown' });

assert.equal(Lib.todayText(wk, at('2026-10-21T12:00:00')), '11:00〜14:00 / 17:00〜22:00');
assert.equal(Lib.todayText(wk, at('2026-10-25T12:00:00')), '定休日');
assert.equal(Lib.todayText(wk, at('2026-10-20T12:00:00')), '不明');
assert.equal(Lib.todayText(null), '');
const rows7 = Lib.weekRows(wk, at('2026-10-21T12:00:00'));
assert.equal(rows7.length, 7);
assert.equal(rows7[5].text, '18:00〜翌2:00');
assert.deepEqual(rows7.filter(r => r.today).map(r => r.label), ['水']);
assert.equal(Lib.formatSpans([['00:00', '24:00']]), '00:00〜24:00', '24:00 は翌0:00 と表示しない');
assert.equal(Lib.formatSpans([['18:00', '26:30']]), '18:00〜翌2:30');

// ---- 日時の指定（30分単位）----
assert.equal(Lib.jstYMD(new Date('2026-10-21T16:00:00Z')), '2026-10-22', 'UTC 16:00 は日本では翌日 01:00');
assert.equal(Lib.floorTo30(at('2026-10-22T12:47:00')), '12:30');
assert.equal(Lib.floorTo30(at('2026-10-22T00:05:00')), '00:00');
assert.equal(Lib.floorTo30(at('2026-10-22T23:59:00')), '23:30');
const custom = Lib.makeJstDate('2026-10-24', '23:30'); // 土曜 23:30
assert.equal(Lib.formatWhen(custom), '10/24(土) 23:30');
assert.equal(Lib.dayLabel(custom), '10/24(土)');
assert.deepEqual(Lib.openStatus(wk, custom), { state: 'open', closesAt: '02:00' }, '土曜の深夜営業');
assert.deepEqual(Lib.openStatus(wk, Lib.makeJstDate('2026-10-25', '00:30')), { state: 'open', closesAt: '02:00' }, '日曜0:30は前日の続き');
assert.deepEqual(Lib.openStatus(wk, Lib.makeJstDate('2026-10-25', '02:00')), { state: 'closed' });
assert.equal(Lib.todayText(wk, custom), '18:00〜翌2:00');
assert.equal(Lib.makeJstDate('2026-13-45', '10:00'), null);
assert.equal(Lib.makeJstDate('', '10:00'), null);
assert.equal(Lib.makeJstDate('2026-10-24', '9:00'), null);
// 営業中フィルタ: 営業時間不明の店は含めない
const hoursShops = [
  Object.assign({}, shops[0], { hours: wk }),
  Object.assign({}, shops[1], { hours: null }),
];
rows = Lib.selectShops(hoursShops, { query: '', facet: { type: 'all' }, radiusM: null, origin: null, openNow: true, now: at('2026-10-21T12:30:00') });
assert.deepEqual(rows.map(r => r.shop.id), ['a']);
rows = Lib.selectShops(hoursShops, { query: '', facet: { type: 'all' }, radiusM: null, origin: null, openNow: true, now: at('2026-10-21T15:00:00') });
assert.equal(rows.length, 0);
// 指定日時での絞り込み
rows = Lib.selectShops(hoursShops, { query: '', facet: { type: 'all' }, radiusM: null, origin: null, openNow: true, now: custom });
assert.deepEqual(rows.map(r => r.shop.id), ['a']);
rows = Lib.selectShops(hoursShops, { query: '', facet: { type: 'all' }, radiusM: null, origin: null, openNow: true, now: Lib.makeJstDate('2026-10-25', '12:00') });
assert.equal(rows.length, 0, '日曜昼は定休日');

// 実データの整合性（public/data が生成済みの場合のみ）
const dataPath = path.join(__dirname, '..', 'public', 'data', 'hakata-oldtown-pay.json');
if (fs.existsSync(dataPath)) {
  const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
  assert.equal(data.length, 76);
  assert.equal(new Set(data.map(s => s.id)).size, data.length);
  data.forEach(s => {
    assert.ok(s.name && s.address && s.category, 'required fields: ' + s.id);
    assert.ok(Lib.googleMapsUrl(s).includes('query='));
  });
}

console.log('lib.test.js: all assertions passed');
