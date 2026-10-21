/* 画面に依存しない関数。ブラウザでは window.Lib、Node では require() で使える。 */
(function (root) {
  'use strict';

  var EARTH_RADIUS_M = 6371000;

  function toRad(d) { return d * Math.PI / 180; }

  /** 2点間の距離（メートル）。Haversine 式。 */
  function haversineMeters(lat1, lon1, lat2, lon2) {
    var dLat = toRad(lat2 - lat1);
    var dLon = toRad(lon2 - lon1);
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  /** 店名＋住所で Google マップ検索を開く URL（営業時間・電話・口コミが出る）。 */
  function googleMapsUrl(shop) {
    return 'https://www.google.com/maps/search/?api=1&query=' +
      encodeURIComponent(shop.name + ' ' + shop.address);
  }

  function formatDistance(m) {
    if (m < 1000) { return Math.max(10, Math.round(m / 10) * 10) + ' m'; }
    return (m / 1000).toFixed(1) + ' km';
  }

  function hasCoords(shop) {
    return typeof shop.lat === 'number' && typeof shop.lon === 'number';
  }

  function normalizeText(s) {
    return String(s || '').normalize('NFKC').toLowerCase();
  }

  function matchesQuery(shop, tokens) {
    if (!tokens.length) { return true; }
    var hay = normalizeText([shop.name, shop.address, shop.category].concat(shop.tags || []).join(' '));
    return tokens.every(function (t) { return hay.indexOf(t) !== -1; });
  }

  function matchesFacet(shop, facet) {
    if (!facet || facet.type === 'all') { return true; }
    if (facet.type === 'category') { return shop.category === facet.value; }
    if (facet.type === 'tag') { return (shop.tags || []).indexOf(facet.value) !== -1; }
    return true;
  }

  /**
   * 絞り込みと並び替え。
   * opts: { query: string, facet: {type,value}, radiusM: number|null, origin: {lat,lon}|null }
   * 戻り値: [{ shop, distance }]  distance は origin があり座標のある店だけ数値、それ以外は null。
   * origin があるときは近い順（座標なしは末尾）。ないときはデータの並び順。
   */
  function selectShops(shops, opts) {
    var tokens = normalizeText(opts.query).split(/\s+/).filter(Boolean);
    var origin = opts.origin || null;
    var rows = [];
    shops.forEach(function (shop) {
      if (!matchesFacet(shop, opts.facet) || !matchesQuery(shop, tokens)) { return; }
      var distance = null;
      if (origin && hasCoords(shop)) {
        distance = haversineMeters(origin.lat, origin.lon, shop.lat, shop.lon);
      }
      if (opts.radiusM) {
        if (distance === null || distance > opts.radiusM) { return; }
      }
      rows.push({ shop: shop, distance: distance });
    });
    if (origin) {
      rows.sort(function (a, b) {
        if (a.distance === null && b.distance === null) { return 0; }
        if (a.distance === null) { return 1; }
        if (b.distance === null) { return -1; }
        return a.distance - b.distance;
      });
    }
    return rows;
  }

  /** 画面上部のチップ用に、カテゴリ・タグごとの件数を数える。 */
  function buildFacets(shops) {
    var cat = {};
    var tag = {};
    shops.forEach(function (s) {
      cat[s.category] = (cat[s.category] || 0) + 1;
      (s.tags || []).forEach(function (t) { tag[t] = (tag[t] || 0) + 1; });
    });
    var facets = [{ type: 'all', value: '', label: '全て', count: shops.length }];
    Object.keys(cat).sort(function (a, b) { return cat[b] - cat[a]; }).forEach(function (k) {
      facets.push({ type: 'category', value: k, label: k, count: cat[k] });
    });
    Object.keys(tag).sort(function (a, b) { return tag[b] - tag[a]; }).forEach(function (k) {
      facets.push({ type: 'tag', value: k, label: k, count: tag[k] });
    });
    return facets;
  }

  var api = {
    haversineMeters: haversineMeters,
    googleMapsUrl: googleMapsUrl,
    formatDistance: formatDistance,
    hasCoords: hasCoords,
    selectShops: selectShops,
    buildFacets: buildFacets
  };

  root.Lib = api;
  if (typeof module === 'object' && module.exports) { module.exports = api; }
})(typeof window !== 'undefined' ? window : globalThis);
