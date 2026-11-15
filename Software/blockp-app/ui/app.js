// Block P sign app. The same page runs on the sign's touch screen (/?screen=1: plays media, menu drops
// down on touch) and on phones/PCs (/: remote control). Everything goes through the server, so all
// screens stay in sync.
import { icon } from './icons.js';

const SCREEN = new URLSearchParams(location.search).has('screen');
document.body.classList.add(SCREEN ? 'screen' : 'remote');
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sheet = $('#sheet');

const app = {
  state: null, lib: { videos: [], albums: [] }, sys: null, layout: null, frame: null,
  view: 'home', libTab: 'videos', addKind: 'video', progress: { position: 0, duration: 0 },
};
let dragging = 0;            // sliders being dragged: don't redraw under the finger
let ledTick = 0;

// ---------- connection ----------
let ws, wsReady = false;
function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws`);
  ws.onopen = () => { wsReady = true; syncLightWatch(); };
  ws.onclose = () => { wsReady = false; setTimeout(connect, 1500); };
  ws.onmessage = e => onMessage(JSON.parse(e.data));
}
const send = obj => { if (wsReady) ws.send(JSON.stringify(obj)); };
const cmd = (type, extra = {}) => send({ type: 'cmd', cmd: { type, ...extra } });
let watching = false;
function syncLightWatch() {
  const want = isOpen() && (app.view === 'home' || app.view === 'lights');
  if (want !== watching || !wsReady) { watching = want; send({ type: 'watch_lights', on: want }); }
}

function onMessage(m) {
  if (m.type === 'state') {
    const first = !app.state;
    const wasConnecting = app.state?.wifi?.status === 'connecting';
    app.state = m.state;
    if (wasConnecting && app.state.wifi.status !== 'connecting') { loadSystem(); if (app.view === 'wifi') loadWifi(); }
    applyPlayback();
    document.body.classList.toggle('sleeping', !!app.state.sleeping);
    if (first) render(); else update();
  } else if (m.type === 'library') {
    app.lib = m.library;
    if (app.view === 'library' && !dragging) render(); else update();
  } else if (m.type === 'progress') {
    if (!SCREEN) { app.progress = m; updateNow(); }
  } else if (m.type === 'seek') {
    if (SCREEN && vid.src) vid.currentTime = m.t;
  } else if (m.type === 'lights') {
    app.frame = m.f;
    ledTick++;
    // The big preview on the Lights page draws every frame (15 fps); the small one in the control
    // centre draws less often, because each redraw inside the frosted sheet costs video frames.
    const every = window.BLOCKP_LED_EVERY ?? 4;     // ~4 fps: under 1% dropped video frames, measured
    $$('canvas.leds').forEach(c => { if (c.id === 'ltBig' || ledTick % every === 0) drawLights(c); });
  } else if (m.type === 'toast') {
    toast(m.text);
  }
}

// ---------- helpers ----------
const S = () => app.state.settings;
const get = path => path.split('.').reduce((o, k) => o?.[k], S());
function setSetting(path, value) {
  const patch = {};
  path.split('.').reduce((o, k, i, a) => (o[k] = i === a.length - 1 ? value : {}), patch);
  cmd('settings', { patch });
}
const fmt = s => {
  s = Math.max(0, Math.floor(s || 0));
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${x}` : `${m}:${x}`;
};
const clock = () => new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
const today = () => new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
function currentItem() {
  const p = app.state?.player;
  return p && p.mode === 'playing' ? p.queue[p.index] : null;
}
let toastTimer;
function toast(text) {
  const t = $('#toast');
  t.textContent = text;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
}
function confirmBox(title, text, ok = 'OK', danger = false) {
  return new Promise(res => {
    const d = document.createElement('div');
    d.className = 'dialog';
    d.innerHTML = `<div class="box glass"><b>${esc(title)}</b><p>${esc(text)}</p><div class="row">
      <button class="btn" data-a="0">Cancel</button><button class="btn ${danger ? 'danger' : 'primary'}" data-a="1">${esc(ok)}</button></div></div>`;
    d.addEventListener('click', e => {
      const a = e.target.closest('[data-a]');
      if (a || e.target === d) { d.remove(); res(a?.dataset.a === '1'); }
    });
    document.body.append(d);
  });
}

// ---------- playback (sign screen only) ----------
const vid = $('#vid'), idleVid = $('#idleVid'), idleImg = $('#idleImg'), photos = [$('#photoA'), $('#photoB')];
let loadedSerial = -1, photoFlip = 0, slide = { timer: null, left: 0, start: 0, index: -1 }, idleStyle = null;

function applyPlayback() {
  if (!SCREEN) return;
  const p = app.state.player, item = currentItem();
  if (p.serial !== loadedSerial) { loadedSerial = p.serial; load(item); }
  if (!item && idleStyle !== S().playback.idle_style) showIdle();
  if (item?.kind === 'video') { if (p.paused || app.state.sleeping) vid.pause(); else vid.play().catch(() => {}); }
  if (item?.kind === 'photo') { if (p.paused || app.state.sleeping) pauseSlide(); else resumeSlide(); }
  if (!item) { if (app.state.sleeping) idleVid.pause(); else if (idleStyle === 'animated') idleVid.play().catch(() => {}); }
  $('#idleClock').classList.toggle('show', !item && S().playback.idle_clock);
}

function load(item) {
  clearTimeout(slide.timer); slide.timer = null;
  if (!item) {
    vid.classList.remove('show'); vid.pause(); vid.removeAttribute('src'); vid.load();
    photos.forEach(p => p.classList.remove('show'));
    showIdle();
    return;
  }
  if (item.kind === 'video') {
    photos.forEach(p => p.classList.remove('show'));
    vid.src = item.url;
    vid.play().catch(() => {});
    caption(item);
  } else {
    vid.classList.remove('show'); vid.pause(); vid.removeAttribute('src');
    showPhoto(item);
  }
}

function showIdle() {
  idleStyle = S().playback.idle_style;
  if (idleStyle === 'animated') {
    if (!idleVid.src.endsWith('/idle.mp4')) idleVid.src = '/idle.mp4';
    idleVid.play().catch(() => {});
    idleVid.classList.add('show'); idleImg.classList.remove('show');
  } else {
    idleImg.src = '/idle.png';
    idleImg.classList.add('show'); idleVid.classList.remove('show'); idleVid.pause();
  }
}
idleVid.addEventListener('error', () => { idleStyle = 'still'; idleImg.src = '/idle.png'; idleImg.classList.add('show'); });

vid.addEventListener('playing', () => {
  vid.classList.add('show');
  idleVid.classList.remove('show'); idleImg.classList.remove('show'); idleVid.pause();
});
vid.addEventListener('ended', () => cmd('ended', { index: app.state.player.index }));
vid.addEventListener('error', () => {
  if (!vid.getAttribute('src')) return;
  toast('This video could not be played');
  cmd('ended', { index: app.state.player.index });
});

function showPhoto(item) {
  const el = photos[photoFlip], other = photos[1 - photoFlip];
  photoFlip = 1 - photoFlip;
  const img = new Image();
  img.onload = () => {
    el._img = img;                                // kept for the frozen-frost snapshot
    el.style.backgroundImage = `url("${item.url}")`;
    const kb = S().playback.ken_burns, secs = S().playback.slide_seconds;
    el.classList.remove('kb');
    if (kb) {
      const r = (a, b) => (a + Math.random() * (b - a)).toFixed(3);
      el.style.setProperty('--kb-s0', r(1.0, 1.04)); el.style.setProperty('--kb-s1', r(1.1, 1.15));
      el.style.setProperty('--kb-x0', r(-2, 2) + '%'); el.style.setProperty('--kb-x1', r(-2, 2) + '%');
      el.style.setProperty('--kb-y0', r(-2, 2) + '%'); el.style.setProperty('--kb-y1', r(-2, 2) + '%');
      el.style.setProperty('--kb-dur', (secs + 2) + 's');
      void el.offsetWidth;
      el.classList.add('kb');
    }
    el.classList.add('show'); other.classList.remove('show');
    idleVid.classList.remove('show'); idleImg.classList.remove('show'); idleVid.pause();
    slide = { timer: null, left: secs * 1000, start: 0, index: app.state.player.index };
    if (!app.state.player.paused && !app.state.sleeping) resumeSlide();
  };
  img.onerror = () => cmd('ended', { index: app.state.player.index });
  img.src = item.url;
}
function resumeSlide() {
  if (slide.timer || slide.left <= 0) return;
  slide.start = performance.now();
  slide.timer = setTimeout(() => { slide.timer = null; slide.left = 0; cmd('ended', { index: slide.index }); }, slide.left);
}
function pauseSlide() {
  if (!slide.timer) return;
  clearTimeout(slide.timer); slide.timer = null;
  slide.left -= performance.now() - slide.start;
}

let capTimer;
function caption(item) {
  if (!S().playback.show_titles) return;
  const c = $('#caption');
  $('.yr', c).textContent = item.year || '';
  $('.tt', c).textContent = item.title;
  c.classList.add('show');
  clearTimeout(capTimer);
  capTimer = setTimeout(() => c.classList.remove('show'), 5000);
}

if (SCREEN) setInterval(() => {
  const item = currentItem();
  if (item?.kind === 'video' && vid.duration) {
    app.progress = { position: vid.currentTime, duration: vid.duration };
    cmd('progress', app.progress);
  } else if (item?.kind === 'photo') {
    const total = S().playback.slide_seconds;
    const left = slide.timer ? slide.left - (performance.now() - slide.start) : slide.left;
    app.progress = { position: total - left / 1000, duration: total };
  }
  updateNow();
}, 1000);
// Pixel shift (see app.css): pick a new spot within 8 px every 4 minutes
function pixelShift() {
  const r = () => (Math.random() * 16 - 8).toFixed(1);
  const x = r(), y = r();
  $('#idleVid').style.transform = $('#idleImg').style.transform = `scale(1.02) translate(${x}px, ${y}px)`;
  $('#idleClock').style.transform = `translate(${x}px, ${y}px)`;
}
if (SCREEN) setInterval(pixelShift, 4 * 60 * 1000);
setInterval(() => {
  $('#idleClock').textContent = clock();
  $$('.js-clock').forEach(e => e.textContent = clock());
}, 1000);

// ---------- the drop-down menu ----------
const isOpen = () => !SCREEN || document.body.classList.contains('open');
let autoTimer;
function openSheet(view = 'home') {
  if (app.state?.sleeping || document.body.classList.contains('open')) return;
  go(view);                                   // build the page while it's still hidden...
  requestAnimationFrame(() => {               // ...then slide it down, so nothing rebuilds mid-animation
    document.body.classList.add('open');
    syncLightWatch();
    setTimeout(loadSystem, 400);              // refresh Wi-Fi/temperature after the slide finishes
  });
}
// Frozen frost for full pages (see app.css): draw whatever is showing into a 160x100 canvas
let frostTimer;
function frost() {
  const c = $('#frost'), ctx = c.getContext('2d');
  const photo = photos.find(p => p.classList.contains('show'));
  const src = vid.classList.contains('show') ? vid : photo?._img ? photo._img
    : idleVid.classList.contains('show') ? idleVid : idleImg;
  try { ctx.drawImage(src, 0, 0, c.width, c.height); } catch { /* nothing loaded yet */ }
}
function setFullPage(on) {
  if (!SCREEN) return;
  clearInterval(frostTimer);
  if (on) { frost(); frostTimer = setInterval(frost, 4000); }
  document.body.classList.toggle('fullpage', on);
}

function closeSheet() {
  if (!SCREEN) return;
  setFullPage(false);
  document.body.classList.remove('open');
  clearTimeout(autoTimer);
  syncLightWatch();
}
function bumpAuto() {
  clearTimeout(autoTimer);
  const secs = S().screen.auto_close;
  if (SCREEN && secs > 0) autoTimer = setTimeout(closeSheet, secs * 1000 * (app.view === 'home' ? 1 : 3));
}
function go(view) {
  app.view = view;
  setFullPage(view !== 'home');
  if (view === 'settings' || view === 'phone' || view === 'wifi') loadSystem();
  if (view === 'wifi' && !app.wifiLoading) loadWifi();
  render();
  bumpAuto();
  syncLightWatch();
}
// Open on a tap (finger up). Opening on finger-down made the lift count as a tap on the close layer.
$('#tapzone').addEventListener('click', () => openSheet('home'));
$('#scrim').addEventListener('click', closeSheet);
$('#sleepCover').addEventListener('click', () => cmd('sleep', { on: false }));
sheet.addEventListener('pointerdown', bumpAuto);
// swipe up on the sheet's handle (or anywhere near its bottom edge) to close
let swipe = null;
sheet.addEventListener('pointerdown', e => {
  const r = sheet.getBoundingClientRect();
  if (SCREEN && e.clientY > r.bottom - 50) swipe = { y: e.clientY, id: e.pointerId };
});
sheet.addEventListener('pointermove', e => {
  if (!swipe || e.pointerId !== swipe.id) return;
  const dy = Math.min(0, e.clientY - swipe.y);
  sheet.classList.add('dragging');
  sheet.style.transform = `translateY(${dy}px)`;
});
const endSwipe = e => {
  if (!swipe) return;
  const dy = e.clientY - swipe.y;
  swipe = null;
  sheet.classList.remove('dragging');
  sheet.style.transform = '';
  if (dy < -60) closeSheet();
};
sheet.addEventListener('pointerup', endSwipe);
sheet.addEventListener('pointercancel', endSwipe);

async function loadSystem() {
  try { app.sys = await (await fetch('/api/system')).json(); } catch { app.sys = null; }
  if (app.view === 'settings' || app.view === 'phone') render(); else update();
}

// ---------- rendering ----------
const TITLES = { library: 'Library', lights: 'Lights', settings: 'Settings', phone: 'Use your phone', add: 'Add',
  wifi: 'Wi-Fi', join: 'Join a network' };
function header() {
  const close = SCREEN ? `<button class="round" data-act="close">${icon('x')}</button>` : '';
  if (app.view === 'home') {
    const sys = app.sys;
    return `<div class="head"><div><div class="clock js-clock">${clock()}</div></div><div class="sub">${today()}</div>
      <div class="spacer"></div><div class="status" id="status"></div>${close}</div>`;
  }
  return `<div class="head"><button class="round" data-act="back">${icon('chevron-left')}</button>
    <div class="title">${TITLES[app.view] || ''}</div><div class="spacer"></div>
    <div class="clock js-clock" style="font-size:20px;color:var(--text-2)">${clock()}</div>${close}</div>`;
}

function render() {
  if (!app.state) return;
  const scroll = $('.body', sheet)?.scrollTop || 0;
  const views = { home: homeView, library: libraryView, lights: lightsView, settings: settingsView, phone: phoneView, add: addView,
    wifi: wifiView, join: joinView };
  sheet.classList.toggle('full', app.view !== 'home' && SCREEN);
  sheet.innerHTML = header() + `<div class="body">${(views[app.view] || homeView)()}</div>` + '<div class="handle"></div>';
  const body = $('.body', sheet);
  if (body) body.scrollTop = scroll;
  bind();
  update(true);
}

// fromRender: called at the end of render(), so only patch values; never re-render (that would loop)
function update(fromRender = false) {
  if (!app.state || dragging) return;
  if (app.view === 'home') { updateNow(); updateHome(); }
  else if (app.view === 'lights') updateLights();
  else if (app.view === 'settings') { if (!fromRender) render(); }
  else if (app.view === 'library') { if (!fromRender) updateLibrary(); }
  else if (app.view === 'wifi') { if (!fromRender) render(); }
}

// ----- home: control centre -----
function homeView() {
  const sq = (act, ic, label, extra = '') => `<button class="sq" data-act="${act}" ${extra}>${icon(ic)}<span>${label}</span></button>`;
  return `<div class="cc">
    <div class="tile now" id="now"></div>
    <div class="vs" id="vsBright"><div class="pct"></div><div class="fill"></div>${icon('sun')}</div>
    <div class="vs" id="vsVol"><div class="pct"></div><div class="fill"></div><span id="volIc">${icon('volume-2')}</span></div>
    <div class="tile lt" data-act="lights"><canvas class="leds" id="ltMini"></canvas>
      <button class="pw" id="ltPower" data-act="lightsPower">${icon('power')}</button><div class="nm" id="ltName"></div></div>
    ${sq('videos', 'film', 'Videos')}${sq('photos', 'image', 'Photos')}${sq('sleep', 'moon', 'Night')}
    ${sq('phone', 'smartphone', 'Phone')}${sq('settings', 'settings', 'Settings')}${sq('idle', 'house', 'Idle screen')}
  </div>`;
}

function updateNow() {
  const el = $('#now');
  if (!el || !app.state) return;
  const p = app.state.player, item = currentItem();
  const pr = SCREEN ? app.progress : (app.progress.duration ? app.progress : p);
  const frac = pr.duration ? Math.min(1, pr.position / pr.duration) : 0;
  const key = `${p.serial}:${p.paused}:${!!item}`;
  if (el.dataset.key !== key) {
    el.dataset.key = key;
    if (!item) {
      el.innerHTML = `<div class="lbl">Idle screen</div><div class="t">Purdue All-American Marching Band</div>
        <div class="grow"></div><div class="row"><button class="btn primary" data-act="playAll">${icon('play')}Play videos</button>
        <button class="btn" data-act="shufflePhotos">${icon('shuffle')}Photos</button></div>`;
    } else {
      const kind = item.kind === 'photo' ? 'Photo slideshow' : 'Now playing';
      el.innerHTML = `${item.thumb_url ? `<div class="bg" style="background-image:url('${esc(item.thumb_url)}')"></div>` : ''}
        <div class="lbl">${kind} · ${p.index + 1} of ${p.queue.length}</div>
        <div class="t">${esc(item.title)}</div>${item.year ? `<div class="y">${item.year}</div>` : ''}<div class="grow"></div>
        <div class="bar" id="nowBar"><i></i></div><div class="times"><span id="tPos"></span><span id="tDur"></span></div>
        <div class="transport"><button data-act="prev" ${p.index === 0 ? 'disabled' : ''}>${icon('skip-back')}</button>
          <button class="pp" data-act="toggle">${icon(p.paused ? 'play' : 'pause')}</button>
          <button data-act="next">${icon('skip-forward')}</button></div>`;
      bindSeek($('#nowBar'));
    }
  }
  const bar = $('#nowBar i', el);
  if (bar) {
    bar.style.width = (frac * 100).toFixed(1) + '%';
    $('#tPos').textContent = fmt(pr.position);
    $('#tDur').textContent = pr.duration ? '-' + fmt(pr.duration - pr.position) : '';
  }
}

function bindSeek(bar) {
  if (!bar) return;
  bar.addEventListener('click', e => {
    const item = currentItem(), d = (SCREEN ? app.progress : app.state.player).duration;
    if (item?.kind !== 'video' || !d) return;
    const r = bar.getBoundingClientRect();
    cmd('seek', { t: (e.clientX - r.left) / r.width * d });
  });
}

function updateHome() {
  const st = app.state, s = S();
  $('#vsBright')?._set?.(s.display.brightness);
  $('#vsVol')?._set?.(s.audio.muted ? 0 : s.audio.volume);
  const vi = $('#volIc');
  if (vi) vi.innerHTML = icon(s.audio.muted || s.audio.volume === 0 ? 'volume-x' : 'volume-2');
  $('#ltPower')?.classList.toggle('on', s.lights.on);
  const nm = $('#ltName');
  if (nm) nm.textContent = s.lights.on ? MODE_NAMES[s.lights.mode] || s.lights.mode : 'Off';
  const status = $('#status');
  if (status && app.sys) status.innerHTML = `<span>${icon('wifi')}${esc(app.sys.wifi || 'Wi-Fi')}</span>
    <span>${icon('thermometer')}${app.sys.temp_c ?? '--'}°C</span>`;
  drawLights($('#ltMini'));
}

// ----- library -----
function libraryView() {
  const tab = app.libTab;
  const seg = `<div class="seg"><button class="${tab === 'videos' ? 'on' : ''}" data-tab="videos">Videos</button>
    <button class="${tab === 'photos' ? 'on' : ''}" data-tab="photos">Photos</button></div>`;
  if (tab === 'videos') {
    const vids = app.lib.videos;
    const dls = app.state.downloads.map(d => `<div class="dl">${icon(d.status === 'failed' ? 'x' : 'download')}<div class="grow">
      <b>${esc(d.title)}</b><span>${d.status === 'failed' ? esc('Failed: ' + (d.error || '')) : `${esc(d.status)} ${Math.round(d.progress * 100)}%`}</span>
      ${d.status !== 'failed' ? `<div class="bar"><i style="width:${(d.progress * 100).toFixed(0)}%"></i></div>` : ''}</div>
      ${d.status === 'failed' ? `<button class="round" data-clear="${d.key}">${icon('x')}</button>` : ''}</div>`).join('');
    let groups = '';
    const byYear = {};
    vids.forEach(v => (byYear[v.year || 'Other'] ||= []).push(v));
    for (const y of Object.keys(byYear).sort((a, b) => (a === 'Other') - (b === 'Other') || b - a)) {
      groups += `<h3>${esc(y)}</h3><div class="grid">${byYear[y].map(videoCard).join('')}</div>`;
    }
    const empty = !vids.length ? `<div class="empty"><b>No videos yet</b>Add show videos from your phone: open Use your phone, or tap Add.</div>` : '';
    return `<div class="row">${seg}<div class="spacer" style="flex:1"></div>
      ${vids.length ? `<button class="btn primary" data-act="playAll">${icon('play')}Play all</button>
      <button class="btn" data-act="shuffleAll">${icon('shuffle')}Shuffle</button>` : ''}
      <button class="btn" data-act="addVideo">${icon('plus')}Add</button></div><div style="height:18px"></div>${dls}${empty}${groups}`;
  }
  const albums = app.lib.albums;
  const cards = albums.map(a => `<button class="card" data-album="${esc(a.name)}"><div class="th" style="background-image:url('${esc(a.cover || '')}')"></div>
    <div class="cap"><b>${esc(a.name)}</b><span>${a.count} photo${a.count === 1 ? '' : 's'}</span></div></button>`).join('');
  return `<div class="row">${seg}<div class="spacer" style="flex:1"></div>
    ${albums.length ? `<button class="btn primary" data-act="shufflePhotos">${icon('shuffle')}Shuffle all</button>` : ''}
    <button class="btn" data-act="addPhotos">${icon('plus')}Add</button></div><div style="height:18px"></div>
    ${albums.length ? `<div class="grid">${cards}</div>` : `<div class="empty"><b>No photos yet</b>Add photos from your phone: open Use your phone, or tap Add.</div>`}`;
}
function videoCard(v) {
  const cur = currentItem();
  const playing = cur?.kind === 'video' && cur.id === v.id;
  return `<div class="card" data-play="${esc(v.id)}" role="button"><div class="th" style="background-image:url('${esc(v.thumb_url || '')}')">
    ${v.duration ? `<span class="badge">${fmt(v.duration)}</span>` : ''}${playing ? '<span class="playing">PLAYING</span>' : ''}</div>
    <div class="cap"><b>${esc(v.title)}</b><span>${esc(v.year || '')}</span></div>
    <button class="more" data-more="${esc(v.id)}">${icon('pencil')}</button></div>`;
}
let libKey = '';
function updateLibrary() {
  const k = JSON.stringify([app.state.downloads, currentItem()?.id]);
  if (k !== libKey) { libKey = k; render(); }
}

// ----- lights -----
const MODE_NAMES = { solid: 'Solid', breathe: 'Breathe', shimmer: 'Shimmer', chase: 'Chase', wave: 'Wave',
  sparkle: 'Sparkle', march: 'March', rainbow: 'Rainbow' };
const EXTRA_COLORS = { amber: '#ff7a00', red: '#ff2a1a', blue: '#2a7bff', purple: '#9b3dff', green: '#20d060' };
function lightsView() {
  const l = S().lights, lay = app.layout || { colors: {}, modes: Object.keys(MODE_NAMES) };
  const colors = { ...lay.colors, ...EXTRA_COLORS };
  return `<div class="lightsPage"><div class="prev"><canvas class="leds" id="ltBig"></canvas></div><div>
    <div class="row"><button class="btn ${l.on ? 'gold' : ''}" data-act="lightsPower" id="lpBtn">${icon('power')}<span>${l.on ? 'On' : 'Off'}</span></button>
      ${app.state.lights_connected ? '' : '<span style="color:var(--text-2);font-size:15px">Preview only: the LED strip isn’t connected yet</span>'}</div>
    <h3>Effect</h3><div class="chips">${lay.modes.map(m => `<button class="chip" data-mode="${m}">${MODE_NAMES[m] || m}</button>`).join('')}</div>
    <h3>Color</h3><div class="swatches">${Object.entries(colors).map(([k, hex]) =>
      `<button class="sw" data-color="${k in lay.colors ? k : hex}" style="background:${hex}"></button>`).join('')}</div>
    <h3>Brightness</h3><div class="row"><div class="hs" id="hsLB"><div class="fill"></div><div class="lab">${icon('sun')}</div></div></div>
    <h3>Speed</h3><div class="row"><div class="hs" id="hsLS"><div class="fill"></div><div class="lab">${icon('sparkles')}</div></div></div>
  </div></div>`;
}
function updateLights() {
  const l = S().lights;
  $$('[data-mode]').forEach(b => b.classList.toggle('on', b.dataset.mode === l.mode));
  $$('[data-color]').forEach(b => b.classList.toggle('on', b.dataset.color === l.color));
  const pb = $('#lpBtn');
  if (pb) { pb.classList.toggle('gold', l.on); $('span', pb).textContent = l.on ? 'On' : 'Off'; }
  $('#hsLB')?._set?.(l.brightness);
  $('#hsLS')?._set?.(l.speed);
}

// Live LED preview. Kept cheap so video under the frosted menu never drops frames: the P shape is
// drawn once into a cached canvas, and each LED's glow is a small gradient fill (canvas shadow blur
// measured at 22% dropped video frames on the Pi; this costs almost nothing).
function drawLights(c) {
  const lay = app.layout;
  if (!c || !lay) return;
  const dpr = devicePixelRatio || 1, W = c.clientWidth, H = c.clientHeight;
  if (!W || !H) return;
  if (c.width !== Math.round(W * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); c._bg = null; }
  const pad = 10, h = Math.min(H - 2 * pad, (W - 2 * pad) / lay.aspect), w = h * lay.aspect;
  const ox = (W - w) / 2, oy = (H - h) / 2, X = x => ox + x * w, Y = y => oy + y * h;
  if (!c._bg) {
    const bg = c._bg = document.createElement('canvas');
    bg.width = c.width; bg.height = c.height;
    const b = bg.getContext('2d');
    b.setTransform(dpr, 0, 0, dpr, 0, 0);
    b.beginPath();
    lay.outline.forEach(([x, y], i) => i ? b.lineTo(X(x), Y(y)) : b.moveTo(X(x), Y(y)));
    b.closePath();
    b.fillStyle = '#0d0d0f'; b.fill();
    b.strokeStyle = 'rgba(255,255,255,.10)'; b.lineWidth = 1; b.stroke();
    const [sx, sy, sw, sh] = lay.screen;
    b.fillStyle = '#1d1d22';
    b.beginPath(); b.roundRect(X(sx), Y(sy), sw * w, sh * h, 3); b.fill();
  }
  const ctx = c.getContext('2d');
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, c.width, c.height);
  ctx.drawImage(c._bg, 0, 0);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const f = app.frame, r = Math.max(1.6, w / 95), gr = r * 3.2;
  lay.positions.forEach(([x, y], i) => {
    const R = f ? f[i * 3] : 40, G = f ? f[i * 3 + 1] : 30, B = f ? f[i * 3 + 2] : 10;
    const lum = Math.max(R, G, B), px = X(x), py = Y(y);
    if (!lum) { ctx.fillStyle = '#2a2a2e'; ctx.fillRect(px - r, py - r, 2 * r, 2 * r); return; }
    const k = 255 / lum, rgb = `${R * k | 0},${G * k | 0},${B * k | 0}`, a = lum / 255;
    const g = ctx.createRadialGradient(px, py, 0, px, py, gr);
    g.addColorStop(0, `rgba(${rgb},${(0.9 * a).toFixed(2)})`);
    g.addColorStop(0.35, `rgba(${rgb},${(0.35 * a).toFixed(2)})`);
    g.addColorStop(1, `rgba(${rgb},0)`);
    ctx.fillStyle = g;
    ctx.fillRect(px - gr, py - gr, 2 * gr, 2 * gr);
    ctx.fillStyle = `rgba(255,255,255,${(0.6 * a).toFixed(2)})`;
    ctx.beginPath(); ctx.arc(px, py, r * 0.55, 0, Math.PI * 2); ctx.fill();
  });
}

// ----- settings -----
function settingsView() {
  const s = S(), sys = app.sys;
  const tog = (label, path, sub = '') => `<div class="item"><div class="k">${label}${sub ? `<small>${sub}</small>` : ''}</div>
    <button class="toggle ${get(path) ? 'on' : ''}" data-tog="${path}"></button></div>`;
  const seg = (label, path, opts, sub = '') => `<div class="item"><div class="k">${label}${sub ? `<small>${sub}</small>` : ''}</div>
    <div class="seg">${opts.map(([v, t]) => `<button class="${String(get(path)) === String(v) ? 'on' : ''}" data-seg="${path}" data-v="${v}">${t}</button>`).join('')}</div></div>`;
  const time = (label, path) => `<div class="item"><div class="k">${label}</div><div class="stepper">
    <button data-step="${path}" data-d="-30">−</button><span class="v">${esc(get(path))}</span><button data-step="${path}" data-d="30">+</button></div></div>`;
  const info = (k, v) => `<div class="item"><div class="k">${k}</div><div class="v">${esc(v ?? '—')}</div></div>`;
  return `
    <h3>Display</h3><div class="group">
      <div class="item"><div class="k">Brightness</div><div class="hs" id="hsBright" style="max-width:420px"><div class="fill"></div><div class="lab">${icon('sun')}</div></div></div>
      ${seg('Screen direction', 'screen.rotation', [[180, 'Mounted'], [0, 'Bench']], 'Mounted is upside down to match the sign')}
      ${seg('Close the menu after', 'screen.auto_close', [[10, '10 s'], [15, '15 s'], [30, '30 s'], [0, 'Never']])}
    </div>
    <h3>Idle screen</h3><div class="group">
      ${seg('Style', 'playback.idle_style', [['animated', 'Animated'], ['still', 'Still']])}
      ${tog('Show the time', 'playback.idle_clock')}
    </div>
    <h3>Playback</h3><div class="group">
      ${seg('When the sign starts', 'playback.startup', [['idle', 'Idle'], ['videos', 'Videos'], ['shuffle_videos', 'Shuffle'], ['photos', 'Photos']])}
      ${seg('Each photo shows for', 'playback.slide_seconds', [[5, '5 s'], [8, '8 s'], [12, '12 s'], [20, '20 s']])}
      ${tog('Slow pan and zoom on photos', 'playback.ken_burns')}
      ${tog('Show the title when a video starts', 'playback.show_titles')}
    </div>
    <h3>Night schedule</h3><div class="group">
      ${tog('Turn off at night', 'schedule.enabled', 'The screen and lights go dark, and wake on touch')}
      ${time('Turn off at', 'schedule.off')}${time('Turn on at', 'schedule.on')}
    </div>
    <h3>Network</h3><div class="group">
      <div class="item"><div class="k">Wi-Fi<small>${esc(sys?.wifi || 'Not connected')}</small></div>
        <button class="btn" data-act="wifi">${icon('wifi')}Change network</button></div>
      ${info('Address', 'http://' + (sys?.hostname || 'blockp') + '.local')}${info('IP address', sys?.ip)}
    </div>
    <h3>System</h3><div class="group">
      ${info('Temperature', sys?.temp_c != null ? sys.temp_c + ' °C' : null)}
      ${info('Storage', sys ? `${sys.disk_used_gb} of ${sys.disk_total_gb} GB used` : null)}
      ${info('Library', sys ? `${sys.videos} videos, ${sys.albums} photo albums` : null)}
      ${info('Running for', sys ? sys.uptime_h + ' hours' : null)}
      ${info('Software', 'Block P ' + app.state.version)}
      <div class="item"><div class="row">
        <button class="btn" data-power="restart_screen">${icon('refresh-cw')}Restart screen</button>
        <button class="btn" data-power="reboot">${icon('rotate-cw')}Restart sign</button>
        <button class="btn danger" data-power="shutdown">${icon('power')}Shut down</button></div></div>
    </div>
    <h3>About</h3><div class="group"><div class="item"><div class="k"><small style="font-size:15px;line-height:1.5">
      Built for the Purdue “All-American” Marching Band keepsake sign. Inter typeface and Pinyon Script (SIL Open Font License),
      Lucide icons (ISC license). Formation photo: Wikimedia Commons, public domain.</small></div></div></div>
    <div style="height:20px"></div>`;
}

// ----- phone (QR) and add -----
function phoneView() {
  const host = (app.sys?.hostname || 'blockp') + '.local';
  const target = app.addKind === 'qr-add' ? `http://${host}/#add` : `http://${host}/`;
  return `<div class="qrWrap"><div class="qr"><img src="/api/qr.svg?u=${encodeURIComponent(target)}" alt="QR code"></div>
    <div class="qrText"><b>${app.addKind === 'qr-add' ? 'Add from your phone' : 'Control from your phone'}</b>
    <p>Point your phone’s camera at the code. Your phone needs to be on the same Wi-Fi as the sign.</p>
    <p>Or type <code>${esc(host)}</code></p>${app.sys?.ip ? `<p style="font-size:15px">If that doesn’t open, use http://${esc(app.sys.ip)}</p>` : ''}</div></div>`;
}
function addView() {
  return `<div class="seg" style="margin-bottom:22px"><button class="${app.addKind !== 'photos' ? 'on' : ''}" data-addk="video">Video link</button>
    <button class="${app.addKind === 'photos' ? 'on' : ''}" data-addk="photos">Photos</button></div>
    ${app.addKind === 'photos' ? `<div class="form"><input type="text" id="album" placeholder="Album name, for example 2024 Season">
      <input type="file" id="files" accept="image/*" multiple><button class="btn gold" data-act="upload">${icon('download')}Upload photos</button>
      <div id="upMsg" style="color:var(--text-2)"></div></div>`
    : `<div class="form"><input type="url" id="url" placeholder="YouTube link">
      <input type="text" id="vtitle" placeholder="Title (optional), for example 2023 Halftime: Hail Purdue">
      <input type="number" id="vyear" placeholder="Season year (optional)">
      <button class="btn gold" data-act="download">${icon('download')}Download to the sign</button>
      <div style="color:var(--text-2)">The video is saved on the sign, so it plays without the internet.</div></div>`}`;
}

// ----- Wi-Fi -----
app.wifiData = null;
app.join = { ssid: '', password: '', hidden: false, field: 'password', show: false };
app.kb = 'lower';
async function loadWifi() {
  app.wifiLoading = true;
  if (app.view === 'wifi') render();
  try { app.wifiData = await (await fetch('/api/wifi')).json(); } catch { /* keep the last list */ }
  app.wifiLoading = false;
  if (app.view === 'wifi') render();
}
function wifiView() {
  const w = app.state.wifi, d = app.wifiData;
  let status;
  if (w.status === 'connecting') status = `<div class="wstat"><div class="spin"></div>Connecting to ${esc(w.ssid)}…</div>`;
  else if (w.status === 'failed') status = `<div class="wstat bad">${icon('x')}${esc(w.message)}</div>`;
  else if (d?.current) status = `<div class="wstat">${icon('wifi')}<div>Connected to <b>${esc(d.current)}</b>
    ${app.sys?.ip ? `<div style="color:var(--text-2);font-size:15px">http://${esc(app.sys.hostname || 'blockp')}.local · ${esc(app.sys.ip)}</div>` : ''}</div></div>`;
  else status = `<div class="wstat bad">${icon('wifi')}Not connected to Wi-Fi. Everything on the sign still works; phones need Wi-Fi to reach it.</div>`;
  const nets = (d?.networks || []).map(n => {
    const strength = n.signal > 66 ? 1 : n.signal > 33 ? .7 : .4;
    return `<button class="item net" data-net="${esc(n.ssid)}"><span style="opacity:${strength}">${icon('wifi')}</span>
      <div class="k">${esc(n.ssid)}${n.connected ? '<small class="ok">Connected</small>' : n.saved ? '<small>Saved</small>' : ''}</div>
      ${n.secure ? `<span class="tag">${icon('lock')}</span>` : '<span class="tag">Open</span>'}
      ${n.connected ? `<span class="ok">${icon('check')}</span>` : icon('chevron-right')}</button>`;
  }).join('');
  const saved = (d?.saved || []).map(s => `<div class="item"><div class="k">${esc(s.ssid)}</div>
    <button class="btn danger" data-forget="${esc(s.name)}">${icon('trash-2')}Forget</button></div>`).join('');
  return `${status}
    ${SCREEN ? '' : '<p style="color:var(--text-2)">Your phone may lose its connection to the sign while it switches networks.</p>'}
    <div class="row" style="margin:26px 4px 12px"><h3 style="margin:0;flex:1">Networks nearby</h3>
      <button class="btn" data-act="wifiRefresh">${app.wifiLoading ? '<div class="spin" style="width:20px;height:20px"></div>' : icon('refresh-cw')}Refresh</button></div>
    <div class="group">${nets || `<div class="item"><div class="k" style="color:var(--text-2)">${app.wifiLoading ? 'Looking for networks…' : 'No networks found'}</div></div>`}
      <button class="item net" data-act="wifiOther">${icon('plus')}<div class="k">Other network…<small>For a network that hides its name</small></div>${icon('chevron-right')}</button></div>
    ${saved ? `<h3>Saved networks</h3><div class="group">${saved}</div>` : ''}<div style="height:20px"></div>`;
}

const KB = {
  lower: [[...'qwertyuiop'], [...'asdfghjkl'], ['shift', ...'zxcvbnm', 'back'], ['123', 'space', 'join']],
  upper: [[...'QWERTYUIOP'], [...'ASDFGHJKL'], ['shift', ...'ZXCVBNM', 'back'], ['123', 'space', 'join']],
  num: [[...'1234567890'], ['-', '/', ':', ';', '(', ')', '$', '&', '@', '"'], ['sym', '.', ',', '?', '!', "'", 'back'], ['abc', 'space', 'join']],
  sym: [[...'[]{}#%^*+='], ['_', '\\', '|', '~', '<', '>', '€', '£', '¥', '•'], ['123', '.', ',', '?', '!', "'", 'back'], ['abc', 'space', 'join']],
};
const KEY_LABEL = { shift: '⇧', back: '⌫', space: 'space', join: 'Join', '123': '123', sym: '#+=', abc: 'ABC' };
function keyboardHtml() {
  return KB[app.kb].map(row => `<div class="r">${row.map(k => {
    const cls = k === 'space' ? 'sp' : k === 'join' ? 'go' : KEY_LABEL[k] ? 'w2' : '';
    const on = k === 'shift' && app.kb === 'upper' ? ' on' : '';
    return `<button class="${cls}${on}" data-key="${esc(k)}">${esc(KEY_LABEL[k] || k)}</button>`;
  }).join('')}</div>`).join('');
}
function fieldHtml(name, label, placeholder) {
  const j = app.join, v = j[name];
  const shown = name === 'password' && !j.show ? '•'.repeat(v.length) : v;
  if (!SCREEN) return `<div class="field"><span class="lab">${label}</span>
    <input type="${name === 'password' && !j.show ? 'password' : 'text'}" data-input="${name}" value="${esc(v)}" placeholder="${esc(placeholder)}"
      style="border:0;background:none;padding:0;font-size:20px"></div>`;
  return `<div class="field ${j.field === name ? 'on' : ''}" data-field="${name}"><span class="lab">${label}</span>
    <span class="val">${v ? esc(shown) : `<span class="ph">${esc(placeholder)}</span>`}</span></div>`;
}
function joinView() {
  const j = app.join;
  return `<div class="join"><div class="fields">
    ${j.hidden ? fieldHtml('ssid', 'Network', 'Network name') : `<div class="field"><span class="lab">Network</span><span class="val"><b>${esc(j.ssid)}</b></span></div>`}
    ${fieldHtml('password', 'Password', j.secure === false ? 'No password needed' : 'Password')}
    <div class="row"><button class="btn" data-act="togglePw">${icon(j.show ? 'eye-off' : 'eye')}${j.show ? 'Hide password' : 'Show password'}</button>
      ${SCREEN ? '' : `<button class="btn gold" data-act="wifiJoin">${icon('wifi')}Join</button>`}</div></div>
    ${SCREEN ? `<div class="kb" id="kb">${keyboardHtml()}</div>` : ''}</div>`;
}
function refreshJoin() {
  const f = $('.join .fields');
  if (!f) return;
  const j = app.join;
  $$('[data-field]', f).forEach(el => {
    const name = el.dataset.field, v = j[name];
    el.classList.toggle('on', j.field === name);
    $('.val', el).innerHTML = v ? esc(name === 'password' && !j.show ? '•'.repeat(v.length) : v)
      : `<span class="ph">${esc(name === 'ssid' ? 'Network name' : 'Password')}</span>`;
  });
}
function pressKey(k) {
  const j = app.join, before = app.kb;
  if (k === 'shift') app.kb = app.kb === 'upper' ? 'lower' : 'upper';
  else if (k === '123') app.kb = 'num';
  else if (k === 'sym') app.kb = 'sym';
  else if (k === 'abc') app.kb = 'lower';
  else if (k === 'back') j[j.field] = j[j.field].slice(0, -1);
  else if (k === 'join') return joinWifi();
  else {
    j[j.field] += k === 'space' ? ' ' : k;
    if (app.kb === 'upper') app.kb = 'lower';          // shift applies to one letter, like a phone
  }
  if (app.kb !== before) $('#kb').innerHTML = keyboardHtml();
  refreshJoin();
}
function joinWifi() {
  const j = app.join;
  if (!j.ssid.trim()) return toast('Type the network name first');
  if (j.secure !== false && !j.saved && j.password.length < 8) return toast('Wi-Fi passwords are at least 8 characters');
  cmd('wifi_connect', { ssid: j.ssid.trim(), password: j.password, hidden: j.hidden });
  j.password = '';
  go('wifi');
}
function startJoin(n) {
  app.join = { ssid: n?.ssid || '', password: '', hidden: !n, field: n ? 'password' : 'ssid', show: false,
    secure: n ? n.secure : true, saved: !!n?.saved };
  app.kb = 'lower';
  if (n && (!n.secure || n.saved)) { cmd('wifi_connect', { ssid: n.ssid }); return go('wifi'); }   // no typing needed
  go('join');
}

// ---------- wiring up controls ----------
function bindSlider(el, { min = 0, max = 100, vertical = false, live, commit, tap, pct = true }) {
  if (!el) return;
  const fill = $('.fill', el), label = $('.pct', el);
  let drag = false, cur = 0, last = 0, moved = false, startX = 0, startY = 0;
  const show = v => {
    const f = (v - min) / (max - min) * 100;
    if (vertical) fill.style.height = f + '%'; else fill.style.width = f + '%';
    if (label && pct) label.textContent = Math.round(v) + '%';
    el.classList.toggle('low', f < 18);
  };
  const move = e => {
    if (tap && !moved) return;            // could still be a tap: don't jump the value yet
    const r = el.getBoundingClientRect();
    let f = vertical ? 1 - (e.clientY - r.top) / r.height : (e.clientX - r.left) / r.width;
    f = Math.max(0, Math.min(1, f));
    cur = min + f * (max - min);
    show(cur);
    const now = performance.now();
    if (now - last > 90) { last = now; live?.(cur); }
  };
  el.addEventListener('pointerdown', e => {
    drag = true; moved = false; startX = e.clientX; startY = e.clientY; dragging++;
    el.setPointerCapture(e.pointerId); el.classList.add('drag'); move(e); e.stopPropagation();
  });
  el.addEventListener('pointermove', e => {
    if (!drag) return;
    if (Math.abs(e.clientX - startX) + Math.abs(e.clientY - startY) > 6) moved = true;
    move(e);
  });
  const end = () => {
    if (!drag) return;
    drag = false; dragging = Math.max(0, dragging - 1); el.classList.remove('drag');
    if (tap && !moved) tap(); else commit?.(cur, moved);
  };
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
  el._set = v => { if (!drag) show(v); };
}

function bind() {
  const s = S();
  sheet.onclick = async e => {
    const t = e.target.closest('[data-act],[data-tab],[data-play],[data-more],[data-album],[data-mode],[data-color],[data-tog],[data-seg],[data-step],[data-power],[data-clear],[data-addk],[data-net],[data-forget],[data-field]');
    if (!t) return;
    const d = t.dataset;
    if (d.net) {
      const n = app.wifiData?.networks.find(x => x.ssid === d.net);
      if (n && !n.connected && app.state.wifi.status !== 'connecting') startJoin(n);
      return;
    }
    if (d.forget) {
      if (await confirmBox('Forget this network?', 'The sign won’t join it on its own anymore.', 'Forget', true)) {
        cmd('wifi_forget', { name: d.forget });
        setTimeout(loadWifi, 800);
      }
      return;
    }
    if (d.field) { app.join.field = d.field; return refreshJoin(); }
    if (d.more) { e.stopPropagation(); return videoMenu(d.more); }
    if (d.play) { cmd('play_video', { id: d.play, continue: true }); return closeSheet(); }
    if (d.album) { cmd('play_album', { name: d.album }); return closeSheet(); }
    if (d.tab) { app.libTab = d.tab; return render(); }
    if (d.mode) return cmd('lights', { mode: d.mode, on: true });
    if (d.color) return cmd('lights', { color: d.color, on: true });
    if (d.tog) return setSetting(d.tog, !get(d.tog));
    if (d.seg) {
      const v = isNaN(+d.v) ? d.v : +d.v;
      if (d.seg === 'screen.rotation') return cmd('rotate', { degrees: v });
      return setSetting(d.seg, v);
    }
    if (d.step) {
      const [h, m] = get(d.step).split(':').map(Number);
      const mins = ((h * 60 + m + +d.d) % 1440 + 1440) % 1440;
      return setSetting(d.step, `${String(mins / 60 | 0).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`);
    }
    if (d.power) {
      const words = { restart_screen: ['Restart the screen?', 'The menu and video reload. It takes a few seconds.', 'Restart'],
        reboot: ['Restart the sign?', 'It comes back on its own in about 30 seconds.', 'Restart'],
        shutdown: ['Shut down the sign?', 'Unplug it and plug it back in to turn it on again.', 'Shut down'] }[d.power];
      if (await confirmBox(...words, d.power === 'shutdown')) cmd('power', { action: d.power });
      return;
    }
    if (d.clear) return cmd('clear_download', { key: d.clear });
    if (d.addk) { app.addKind = d.addk; return render(); }
    switch (d.act) {
      case 'close': return closeSheet();
      case 'back': return go({ add: 'library', join: 'wifi', wifi: 'settings' }[app.view] || 'home');
      case 'wifi': return go('wifi');
      case 'wifiRefresh': return loadWifi();
      case 'wifiOther': return startJoin(null);
      case 'wifiJoin': return joinWifi();
      case 'togglePw': app.join.show = !app.join.show; return render();
      case 'toggle': return cmd('toggle');
      case 'prev': return cmd('prev');
      case 'next': return cmd('next');
      case 'idle': cmd('stop'); return closeSheet();
      case 'playAll': cmd('play_videos'); return closeSheet();
      case 'shuffleAll': cmd('play_videos', { shuffle: true }); return closeSheet();
      case 'shufflePhotos': cmd('play_album', { shuffle: true }); return closeSheet();
      case 'videos': app.libTab = 'videos'; return go('library');
      case 'photos': app.libTab = 'photos'; return go('library');
      case 'lights': return go('lights');
      case 'lightsPower': e.stopPropagation(); return cmd('lights', { on: !s.lights.on });
      case 'sleep': closeSheet(); return cmd('sleep', { on: true });
      case 'phone': app.addKind = 'qr'; return go('phone');
      case 'settings': return go('settings');
      case 'addVideo': app.addKind = SCREEN ? 'qr-add' : 'video'; return go(SCREEN ? 'phone' : 'add');
      case 'addPhotos': app.addKind = SCREEN ? 'qr-add' : 'photos'; return go(SCREEN ? 'phone' : 'add');
      case 'download': {
        const url = $('#url').value.trim();
        if (!url) return toast('Paste a video link first');
        cmd('download', { url, title: $('#vtitle').value.trim(), year: +$('#vyear').value || null });
        app.libTab = 'videos'; return go('library');
      }
      case 'upload': return upload();
    }
  };
  bindSlider($('#vsBright'), { vertical: true, min: 1, live: v => cmd('brightness', { value: v }), commit: v => cmd('brightness', { value: v }) });
  bindSlider($('#vsVol'), { vertical: true, live: v => cmd('volume', { value: v }), commit: v => cmd('volume', { value: v }),
    tap: () => cmd('mute') });
  bindSlider($('#hsBright'), { min: 1, pct: false, live: v => cmd('brightness', { value: v }), commit: v => cmd('brightness', { value: v }) });
  bindSlider($('#hsLB'), { pct: false, live: v => cmd('lights', { brightness: Math.round(v) }), commit: v => cmd('lights', { brightness: Math.round(v) }) });
  bindSlider($('#hsLS'), { min: 0.25, max: 3, pct: false, live: v => cmd('lights', { speed: +v.toFixed(2) }), commit: v => cmd('lights', { speed: +v.toFixed(2) }) });
  $('#hsBright')?._set?.(s.display.brightness);
  if (app.view === 'home' && !app.sys) loadSystem();
  // on-screen keyboard: act on finger-down so fast typing keeps up
  $('#kb')?.addEventListener('pointerdown', e => {
    const k = e.target.closest('[data-key]');
    if (!k) return;
    e.preventDefault();
    bumpAuto();
    pressKey(k.dataset.key);
  });
  $$('[data-input]').forEach(i => i.addEventListener('input', () => { app.join[i.dataset.input] = i.value; }));
}

async function videoMenu(id) {
  const v = app.lib.videos.find(x => x.id === id);
  if (!v) return;
  const d = document.createElement('div');
  d.className = 'dialog';
  d.innerHTML = `<div class="box glass"><b>${esc(v.title)}</b><p>${esc(v.year || '')}</p>
    ${SCREEN ? '' : `<div class="form" style="margin-bottom:16px;text-align:left"><input type="text" id="eTitle" value="${esc(v.title)}">
      <input type="number" id="eYear" value="${esc(v.year || '')}" placeholder="Season year"></div>`}
    <div class="row"><button class="btn" data-a="cancel">Close</button>${SCREEN ? '' : '<button class="btn primary" data-a="save">Save</button>'}
    <button class="btn danger" data-a="del">${icon('trash-2')}Delete</button></div></div>`;
  d.addEventListener('click', async e => {
    const a = e.target.closest('[data-a]')?.dataset.a;
    if (!a && e.target !== d) return;
    if (a === 'save') cmd('edit_video', { id, title: $('#eTitle', d).value, year: $('#eYear', d).value });
    if (a === 'del') { d.remove(); if (await confirmBox('Delete this video?', v.title, 'Delete', true)) cmd('delete_video', { id }); return; }
    d.remove();
  });
  document.body.append(d);
}

async function upload() {
  const files = $('#files').files, msg = $('#upMsg');
  if (!files.length) return toast('Choose photos first');
  const fd = new FormData();
  fd.append('album', $('#album').value.trim() || 'Photos');
  [...files].forEach(f => fd.append('file', f, f.name));
  msg.textContent = `Uploading ${files.length} photo${files.length === 1 ? '' : 's'}…`;
  try {
    const r = await (await fetch('/api/upload', { method: 'POST', body: fd })).json();
    msg.textContent = `Added ${r.saved}.`;
  } catch { msg.textContent = 'Upload failed. Try again.'; }
}

// ---------- start ----------
fetch('/api/lights/layout').then(r => r.json()).then(l => { app.layout = l; update(); });
if (!SCREEN && location.hash === '#add') { app.view = 'add'; app.addKind = 'video'; }
connect();
