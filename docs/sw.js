/* iro/sumi 共通 Service Worker v2.1 — 2026-08-28
   このファイルはシリーズ共通の正典。編集したら apply_sw.py で5本へ配り直すこと。

   v1 で起きた事故(2026-08-28):
     (1) 応答を res.ok で確かめずにキャッシュしていたため 404 やエラーページも保存された
     (2) キャッシュ名が固定(-v1)で、sw.js のバイト列も毎回同じだったため
         ブラウザが更新を検知せず、古い entry が永久に残った
     (3) 通信が一瞬でも失敗するとキャッシュへフォールバックし、(2)のせいで
         かなり古い版が返り、以後それが表示され続けた
   → GitHub Pages の一時的な404をきっかけに、家計簿とタスクで実際に発生した。

   設計上の要点:
     - ネットワーク優先。鮮度を最優先する
     - 成功応答だけをキャッシュする(404/500 を入れない)
     - ネットワークに届いたが 404/500 だったときもキャッシュへ退避する。これが本丸の対策
     - VERSION が本文に埋まるので、リリースごとに sw.js のバイト列が必ず変わる。
       ブラウザの更新検知はバイト差分で駆動されるため、これが根本的な遮断装置になる
     - Cache Storage は SW スコープ単位ではなく「オリジン単位」で共有される。
       5本は同一の eggyolk049.github.io にあるため、削除は必ず自分の接頭辞に限定する */

const VERSION = '2026-09-02-ed62b239bc';
const SLUG    = 'sumi-tokei';
const PREFIX  = SLUG + '-';
const CACHE   = PREFIX + VERSION;
const SHELL   = './';

/* ネットワーク待ちの上限(ms)。超えたらキャッシュで先に応答し、
   ネットワークは中断せず完走させてキャッシュだけ更新する。 */
const NET_TIMEOUT_MS = 4000;

/* 旧SW時代の、新しい接頭辞に一致しないキャッシュ名。数リリース後に空へ戻してよい。 */
const LEGACY = [];

/* ---------- install ----------
   catch を付けないのが要点。SHELL の取得に失敗したら install を失敗させ、
   ブラウザに「古くても壊れていない現行SW」を使い続けさせる。次回の更新チェックで再試行される。
   ここで握り潰すと、Pages が404の最中に空のキャッシュを持つSWが有効化され、
   activate が正常な旧キャッシュを消してしまう。 */
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.add(new Request(SHELL, { cache: 'reload' })))
      .then(() => self.skipWaiting())
  );
});

/* ---------- activate ----------
   自分の接頭辞と LEGACY だけを消す。他アプリのキャッシュを巻き添えにしない。 */
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(
        ks.filter(k => k !== CACHE && (k.indexOf(PREFIX) === 0 || LEGACY.indexOf(k) >= 0))
          .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

/* ---------- helpers ----------
   caches.match() はオリジン内の全キャッシュを横断するため使わない。
   他アプリや削除前の旧キャッシュからヒットしうる。 */
function fromCache(req) {
  return caches.open(CACHE)
    .then(c => c.match(req).then(m => {
      if (m) return m;
      if (req.mode === 'navigate') return c.match(SHELL);
      return undefined;
    }))
    .catch(() => undefined);
}

function withTimeout(p, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout')), ms);
    p.then(
      v   => { clearTimeout(t); resolve(v); },
      err => { clearTimeout(t); reject(err); }
    );
  });
}

/* ---------- fetch ---------- */
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (req.headers.has('range')) return;   /* 206 は Cache.put が必ず失敗するので対象外 */

  let sameOrigin = false;
  try { sameOrigin = new URL(req.url).origin === self.location.origin; } catch (err) {}
  if (!sameOrigin) return;

  /* fetch は1回だけ。応答用とキャッシュ更新用でこの Promise を共有する。 */
  const network = fetch(req).then(res => {
    if (res && res.ok && res.type === 'basic') {
      const copy = res.clone();
      /* waitUntil で包む。包まないと SW が早期終了して書き込みが失われ、
         「画面には最新が出たのにキャッシュは古いまま」になる */
      e.waitUntil(caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {}));
    }
    return res;
  });

  /* タイムアウトで先にキャッシュを返した後も、この fetch を完走させて次回に備える */
  e.waitUntil(network.catch(() => {}));

  e.respondWith(
    withTimeout(network, NET_TIMEOUT_MS).then(
      res => {
        /* opaqueredirect は ok=false だが、そのまま返すのが仕様どおり。握り潰さない */
        if (res && (res.ok || res.type === 'opaqueredirect')) return res;
        /* ネットワークには届いたが 404/500 等 → キャッシュを優先する。
           fetch は HTTPエラーで reject しないので、ここを通さないと生の404が表示される。
           2026-08-28 の事故に対する本丸の対策 */
        return fromCache(req).then(m => m || res);
      },
      () => {
        /* 通信失敗、またはタイムアウト。
           キャッシュが無い場合は「単に遅いだけ」の可能性があるので network を待ち直す */
        return fromCache(req).then(m => m || network.catch(() => Response.error()));
      }
    )
  );
});
