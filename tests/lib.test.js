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
