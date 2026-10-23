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

  /* ---------- 営業時間 ---------- */
  var DAY_JA = ['月', '火', '水', '木', '金', '土', '日'];

  function toMin(hhmm) {
    var p = hhmm.split(':');
    return Number(p[0]) * 60 + Number(p[1]);
  }

  /** 日本時間の日付 'YYYY-MM-DD' */
  function jstYMD(date) {
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
  }

  /** 日本時間の日付と時刻から Date を作る。形式が不正なら null。 */
  function makeJstDate(ymd, time) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(ymd || '') || !/^\d{2}:\d{2}$/.test(time || '')) { return null; }
    var d = new Date(ymd + 'T' + time + ':00+09:00');
    return isNaN(d.getTime()) ? null : d;
  }

  /** 日本時間の時刻を30分単位に切り下げた 'HH:MM'（例 12:47 → 12:30）。 */
  function floorTo30(date) {
    var t = jstParts(date);
    return hhmm(t.min - (t.min % 30));
  }

  /** '10/24(土)' */
  function dayLabel(date) {
    var p = jstYMD(date).split('-');
    return Number(p[1]) + '/' + Number(p[2]) + '(' + DAY_JA[jstParts(date).day] + ')';
  }

  /** '10/24(土) 23:30' */
  function formatWhen(date) {
    return dayLabel(date) + ' ' + hhmm(jstParts(date).min);
  }

  /** 端末のタイムゾーンに関係なく日本時間の {day: 0=月..6=日, min: 0..1439} を返す。 */
  function jstParts(date) {
    var parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Tokyo', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(date);
    var get = function (t) { return parts.filter(function (p) { return p.type === t; })[0].value; };
    var dayIdx = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 }[get('weekday')];
    return { day: dayIdx, min: Number(get('hour')) * 60 + Number(get('minute')) };
  }

  function spanEnd(s, e) { return e <= s ? e + 1440 : e; } // 終了が開始以前なら翌日扱い

  function fmtSpan(span) {
    // '26:00' は '翌2:00' と表示
    var end = toMin(span[1]);
    var endText = end > 1440 ? '翌' + String(Math.floor((end - 1440) / 60)) + ':' + span[1].split(':')[1] : span[1];
    return span[0] + '〜' + endText;
  }

  function formatSpans(spans) {
    if (spans === null || spans === undefined) { return '不明'; }
    if (!spans.length) { return '定休日'; }
    return spans.map(fmtSpan).join(' / ');
  }

  /**
   * 営業中かどうか。hours = {weekly: [7要素], note, checked_at} | null
   * 戻り値: {state: 'open'|'closed'|'unknown', closesAt?: 'HH:MM'}
   * 今日の曜日が不明(null)なら unknown。昨日の深夜営業（26:00 など）の続きも見る。
   */
  function openStatus(hours, now) {
    if (!hours || !hours.weekly) { return { state: 'unknown' }; }
    var t = jstParts(now || new Date());
    var today = hours.weekly[t.day];
    var yesterday = hours.weekly[(t.day + 6) % 7];
    var i, s, e;
    if (yesterday) {
      for (i = 0; i < yesterday.length; i++) {
        s = toMin(yesterday[i][0]); e = spanEnd(s, toMin(yesterday[i][1]));
        if (e > 1440 && t.min < e - 1440) { return { state: 'open', closesAt: hhmm(e - 1440) }; }
      }
    }
    if (today === null || today === undefined) { return { state: 'unknown' }; }
    for (i = 0; i < today.length; i++) {
      s = toMin(today[i][0]); e = spanEnd(s, toMin(today[i][1]));
      if (t.min >= s && t.min < e) { return { state: 'open', closesAt: hhmm(e % 1440 === 0 && e > 0 ? 1440 : e % 1440) }; }
    }
    return { state: 'closed' };
  }

  function hhmm(min) {
    return String(Math.floor(min / 60)).padStart(2, '0') + ':' + String(min % 60).padStart(2, '0');
  }

  /** 本日の営業時間の表示文字列（例: '11:00〜14:00 / 17:00〜22:00'、'定休日'、'不明'）。 */
  function todayText(hours, now) {
    if (!hours || !hours.weekly) { return ''; }
    return formatSpans(hours.weekly[jstParts(now || new Date()).day]);
  }

  /** 週間表示用 [{label:'月', text:'...', today:boolean}] */
  function weekRows(hours, now) {
    var today = jstParts(now || new Date()).day;
    return hours.weekly.map(function (spans, i) {
      return { label: DAY_JA[i], text: formatSpans(spans), today: i === today };
    });
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
      if (opts.openNow && openStatus(shop.hours, opts.now).state !== 'open') { return; }
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
    buildFacets: buildFacets,
    openStatus: openStatus,
    todayText: todayText,
    weekRows: weekRows,
    formatSpans: formatSpans,
    jstParts: jstParts,
    jstYMD: jstYMD,
    makeJstDate: makeJstDate,
    floorTo30: floorTo30,
    dayLabel: dayLabel,
    formatWhen: formatWhen
  };

  root.Lib = api;
  if (typeof module === 'object' && module.exports) { module.exports = api; }
})(typeof window !== 'undefined' ? window : globalThis);
