/* 博多旧市街PAY 加盟店マップ — 画面まわり。距離計算や絞り込みは lib.js */
(function () {
  'use strict';

  // 地図タイル。アクセスが増えたら国土地理院などへ切り替える（README 参照）。
  var TILE = {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    maxZoom: 19
  };
  // 国土地理院タイルの例:
  // url: 'https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', maxZoom: 18,
  // attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener noreferrer">地理院タイル</a>'

  var CATEGORY_COLORS = {
    '飲食': '#d9480f',
    '宿泊': '#6741d9',
    '小売・販売': '#1971c2',
    'サービス': '#2b8a3e',
    '美容・エステ': '#c2255c',
    'ジュエリー・ファッション': '#a61e4d',
    '健康・医療': '#0b7285',
    'その他': '#5c6b7a'
  };
  var SHEET_ORDER = ['peek', 'half', 'full'];

  var state = {
    program: null,
    shops: [],
    facet: { type: 'all', value: '' },
    query: '',
    radiusM: null,
    origin: null,
    distances: {}
  };
  var els = {};
  var map = null;
  var cluster = null;
  var markersById = {};
  var userMarker = null;
  var toastTimer = null;
  var searchTimer = null;

  /* ---------- 小さな DOM ヘルパー ---------- */
  function h(tag, props, children) {
    var e = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      var v = props[k];
      if (k === 'class') { e.className = v; }
      else if (k === 'text') { e.textContent = v; }
      else if (k.slice(0, 2) === 'on') { e.addEventListener(k.slice(2), v); }
      else if (v !== null && v !== undefined && v !== false) { e.setAttribute(k, v); }
    });
    (children || []).forEach(function (c) {
      if (c) { e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); }
    });
    return e;
  }

  function colorOf(category) { return CATEGORY_COLORS[category] || CATEGORY_COLORS['その他']; }

  function toast(msg) {
    els.toast.textContent = msg;
    els.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { els.toast.classList.remove('show'); }, 4200);
  }

  function getJSON(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) { throw new Error(url + ' → HTTP ' + r.status); }
      return r.json();
    });
  }

  function formatDateJa(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? m[1] + '年' + Number(m[2]) + '月' + Number(m[3]) + '日' : (iso || '');
  }

  /* ---------- 地図 ---------- */
  function initMap(program) {
    if (typeof L === 'undefined') {
      toast('地図ライブラリを読み込めませんでした。一覧のみ表示します。');
      return;
    }
    var center = program.map_center || [33.59, 130.41];
    map = L.map('map', { zoomControl: true, attributionControl: false, tap: true }).setView(center, program.map_zoom || 15);
    L.control.attribution({ position: 'topright', prefix: false }).addTo(map);
    L.tileLayer(TILE.url, { attribution: TILE.attribution, maxZoom: TILE.maxZoom }).addTo(map);
    cluster = L.markerClusterGroup({ maxClusterRadius: 40, showCoverageOnHover: false, spiderfyOnMaxZoom: true });
    map.addLayer(cluster);
  }

  function buildPopup(shop) {
    var d = state.distances[shop.id];
    return h('div', {}, [
      h('p', { class: 'pop-name', text: shop.name }),
      h('p', { class: 'pop-meta', text: shop.category + (d != null ? ' ・ ' + Lib.formatDistance(d) : '') }),
      h('a', { class: 'btn primary', href: Lib.googleMapsUrl(shop), target: '_blank', rel: 'noopener noreferrer', text: 'Googleマップで開く' })
    ]);
  }

  function renderMarkers(rows) {
    markersById = {};
    if (!cluster) { return; }
    cluster.clearLayers();
    var layers = [];
    rows.forEach(function (r) {
      var s = r.shop;
      if (!Lib.hasCoords(s)) { return; }
      var m = L.circleMarker([s.lat, s.lon], {
        radius: 9, color: '#ffffff', weight: 2, fillColor: colorOf(s.category), fillOpacity: 1
      });
      m.bindPopup(function () { return buildPopup(s); });
      m.on('popupopen', function () { highlight(s.id, true); });
      m.on('popupclose', function () { highlight(null); });
      markersById[s.id] = m;
      layers.push(m);
    });
    cluster.addLayers(layers);
  }

  function fitToMarkers() {
    if (!map || !cluster) { return; }
    var b = cluster.getBounds();
    if (state.origin && state.radiusM) { b = b.isValid() ? b.extend([state.origin.lat, state.origin.lon]) : b; }
    if (b.isValid()) { map.fitBounds(b.pad(0.15), { maxZoom: 17, animate: true }); }
  }

  /* ---------- 一覧 ---------- */
  function highlight(id, scroll) {
    var prev = els.list.querySelector('.shop.active');
    if (prev) { prev.classList.remove('active'); }
    if (!id) { return; }
    var li = els.list.querySelector('[data-id="' + id + '"]');
    if (!li) { return; }
    li.classList.add('active');
    if (scroll && els.sheet.dataset.state !== 'peek') { li.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
  }

  function focusShop(shop) {
    var m = markersById[shop.id];
    if (!m || !map) { return; }
    setSheet('peek');
    cluster.zoomToShowLayer(m, function () { map.panTo(m.getLatLng()); m.openPopup(); });
  }

  function shopItem(row) {
    var s = row.shop;
    var hasPin = Lib.hasCoords(s);
    var meta = [
      h('span', {}, [h('span', { class: 'dot', style: 'background:' + colorOf(s.category) }), s.category])
    ];
    if (!hasPin) { meta.push(h('span', { class: 'badge', text: '地図未登録' })); }

    var actions = [
      h('a', { class: 'btn primary', href: Lib.googleMapsUrl(s), target: '_blank', rel: 'noopener noreferrer', text: 'Googleマップ' })
    ];
    if (s.phone) { actions.push(h('a', { class: 'btn', href: 'tel:' + s.phone, text: '電話' })); }
    actions.push(h('button', {
      class: 'btn', type: 'button', text: '地図で見る', disabled: hasPin ? null : 'disabled',
      onclick: function () { focusShop(s); }
    }));
    if (s.website) {
      actions.push(h('a', { class: 'btn', href: s.website, target: '_blank', rel: 'noopener noreferrer', text: '店舗サイト' }));
    }

    return h('li', { class: 'shop', 'data-id': s.id }, [
      h('div', { class: 'shop-head' }, [
        h('h3', { class: 'shop-name', text: s.name }),
        row.distance != null ? h('span', { class: 'dist', text: Lib.formatDistance(row.distance) }) : null
      ]),
      h('p', { class: 'meta' }, meta),
      h('p', { class: 'addr', text: s.address }),
      s.note ? h('p', { class: 'note', text: '※' + s.note }) : null,
      h('div', { class: 'actions' }, actions)
    ]);
  }

  function renderList(rows) {
    els.list.textContent = '';
    if (!rows.length) {
      els.list.appendChild(h('li', { class: 'empty', text: '条件に合う店舗がありません。' }));
      return;
    }
    var frag = document.createDocumentFragment();
    rows.forEach(function (r) { frag.appendChild(shopItem(r)); });
    els.list.appendChild(frag);
  }

  /* ---------- 絞り込みの反映 ---------- */
  function render(fit) {
    var rows = Lib.selectShops(state.shops, {
      query: state.query, facet: state.facet, radiusM: state.radiusM, origin: state.origin
    });
    state.distances = {};
    rows.forEach(function (r) { if (r.distance != null) { state.distances[r.shop.id] = r.distance; } });

    var total = state.shops.length;
    els.count.textContent = (rows.length === total ? total + '店舗' : rows.length + ' / ' + total + '店舗') +
      (state.origin ? '（現在地から近い順）' : '');
    renderList(rows);
    renderMarkers(rows);
    if (fit) { fitToMarkers(); }
  }

  function renderChips() {
    els.chips.textContent = '';
    Lib.buildFacets(state.shops).forEach(function (f) {
      var active = state.facet.type === f.type && state.facet.value === f.value;
      els.chips.appendChild(h('button', {
        class: 'chip', type: 'button', 'aria-pressed': active ? 'true' : 'false',
        onclick: function () { state.facet = { type: f.type, value: f.value }; renderChips(); render(true); }
      }, [f.label, h('span', { class: 'n', text: String(f.count) })]));
    });
  }

  /* ---------- 下のシート ---------- */
  function setSheet(name) {
    els.sheet.dataset.state = name;
    els.handle.setAttribute('aria-expanded', name === 'peek' ? 'false' : 'true');
  }

  function cycleSheet() {
    var i = SHEET_ORDER.indexOf(els.sheet.dataset.state);
    setSheet(SHEET_ORDER[(i + 1) % SHEET_ORDER.length]);
  }

  /* ---------- 現在地 ---------- */
  function locate() {
    if (!navigator.geolocation) { toast('この端末・ブラウザでは現在地を取得できません。'); return; }
    els.locate.disabled = true;
    els.locate.textContent = '取得中…';
    navigator.geolocation.getCurrentPosition(function (pos) {
      state.origin = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      els.locate.disabled = false;
      els.locate.textContent = '現在地 ✓';
      els.locate.setAttribute('aria-pressed', 'true');
      els.radius.disabled = false;
      showUserMarker();
      render(false);

      var c = state.program.map_center;
      var far = c && Lib.haversineMeters(state.origin.lat, state.origin.lon, c[0], c[1]) > 20000;
      if (far) {
        toast('現在地が対象エリアから離れています。距離は現在地からの直線距離です。');
      } else if (map) {
        map.setView([state.origin.lat, state.origin.lon], 16);
      }
    }, function (err) {
      els.locate.disabled = false;
      els.locate.textContent = state.origin ? '現在地 ✓' : '現在地';
      var msg = { 1: '位置情報の利用が許可されていません。ブラウザの設定をご確認ください。',
                  2: '現在地を取得できませんでした。電波の良い場所でお試しください。',
                  3: '現在地の取得がタイムアウトしました。もう一度お試しください。' };
      toast(msg[err.code] || '現在地を取得できませんでした。');
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
  }

  function showUserMarker() {
    if (!map) { return; }
    var ll = [state.origin.lat, state.origin.lon];
    if (userMarker) { userMarker.setLatLng(ll); return; }
    userMarker = L.circleMarker(ll, { radius: 8, color: '#ffffff', weight: 3, fillColor: '#2f80ed', fillOpacity: 1, interactive: false }).addTo(map);
  }

  /* ---------- このサイトについて ---------- */
  function fillAbout(program) {
    var dl = document.getElementById('about-source');
    dl.textContent = '';
    function row(label, node) { dl.appendChild(h('dt', { text: label })); dl.appendChild(h('dd', {}, [node])); }
    row('出典', h('a', { href: program.source_url, target: '_blank', rel: 'noopener noreferrer', text: program.source_name }));
    row('情報取得日', document.createTextNode(formatDateJa(program.source_retrieved_at)));
    row('発行者', document.createTextNode(program.issuer));
    row('利用期間', document.createTextNode(formatDateJa(program.valid_from) + ' 〜 ' + formatDateJa(program.valid_to)));
    document.getElementById('official-link').href = program.official_url;
  }

  /* ---------- 起動 ---------- */
  function init() {
    ['q', 'locate', 'radius', 'chips', 'sheet', 'sheet-handle', 'count', 'list', 'toast', 'about', 'about-btn'].forEach(function (id) {
      els[id.replace(/-(\w)/g, function (_, c) { return c.toUpperCase(); })] = document.getElementById(id);
    });
    els.handle = els.sheetHandle;

    els.handle.addEventListener('click', cycleSheet);
    els.locate.addEventListener('click', locate);
    els.aboutBtn.addEventListener('click', function () { els.about.showModal(); });
    els.radius.addEventListener('change', function () {
      state.radiusM = els.radius.value ? Number(els.radius.value) : null;
      render(true);
    });
    els.q.addEventListener('input', function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () { state.query = els.q.value; render(true); }, 250);
    });

    getJSON('data/index.json').then(function (idx) {
      var wanted = new URLSearchParams(location.search).get('program');
      var program = idx.programs.filter(function (p) { return p.id === wanted; })[0] || idx.programs[0];
      state.program = program;
      document.title = program.name + ' 加盟店マップ（非公式）';
      fillAbout(program);
      initMap(program);
      return getJSON('data/' + program.file);
    }).then(function (shops) {
      state.shops = shops;
      renderChips();
      render(true);
      var missing = shops.filter(function (s) { return !Lib.hasCoords(s); }).length;
      var dev = location.hostname === 'localhost' || location.hostname === '127.0.0.1' || /[?&]debug=1/.test(location.search);
      if (missing && dev) {
        toast('座標が未設定の店舗が ' + missing + ' 件あります。scripts/geocode.py → build_data.py を実行してください。');
      }
    }).catch(function (e) {
      els.count.textContent = '読み込みに失敗しました';
      els.list.textContent = '';
      els.list.appendChild(h('li', { class: 'empty', text: '店舗データを読み込めませんでした。通信状況をご確認のうえ、再読み込みしてください。' }));
      setSheet('half');
      if (window.console) { console.error(e); }
    });
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
