# tokei.html → docs/ 配信一式(index.html + manifest + アイコン + スプラッシュ + SW)を生成する。
# 使い方: python tools/gen_release.py → git commit → git push → GitHub Pages(docs/)に反映
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tokei.html"
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

# 起動スプラッシュの対象サイズ(実ピクセル, 論理px, 倍率)。iPhoneの新画面が出たらここに足す
SPLASH = [
    (1179, 2556, 393, 852, 3),  # 14 Pro / 15 / 15 Pro / 16
    (1170, 2532, 390, 844, 3),  # 12 / 13 / 14
    (1290, 2796, 430, 932, 3),  # 14 Pro Max / 15 Plus・Pro Max / 16 Plus
    (1206, 2622, 402, 874, 3),  # 16 Pro
    (1320, 2868, 440, 956, 3),  # 16 Pro Max
    (1125, 2436, 375, 812, 3),  # 12 mini / 13 mini / X / XS
]

html = SRC.read_text(encoding="utf-8")

splash_links = ""
for w, h, lw, lh, r in SPLASH:
    base = f"screen and (device-width: {lw}px) and (device-height: {lh}px) and (-webkit-device-pixel-ratio: {r}) and (orientation: portrait)"
    # ダーク用を先に(prefers-color-scheme未対応のiOSではdark側が不成立→後段のライトが効く)
    splash_links += f'<link rel="apple-touch-startup-image" media="{base} and (prefers-color-scheme: dark)" href="splash-{w}x{h}-dark.png">\n'
    splash_links += f'<link rel="apple-touch-startup-image" media="{base}" href="splash-{w}x{h}.png">\n'

VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
assert VIEWPORT in html, "NG: viewportメタが見つからない"
html = html.replace(VIEWPORT, VIEWPORT + (
    '<meta name="apple-mobile-web-app-capable" content="yes">\n'
    '<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">\n'
    '<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">\n'
    '<link rel="manifest" href="manifest.webmanifest">\n'
    '<link rel="apple-touch-icon" href="apple-touch-icon.png">\n'
    '<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">\n'
) + splash_links, 1)

html = html.rstrip() + "\n" + (
    "<script>\n"
    "if('serviceWorker' in navigator){\n"
    "  addEventListener('load', () => { navigator.serviceWorker.register('sw.js').catch(() => {}); });\n"
    "}\n"
    "</script>\n"
)
(DOCS / "index.html").write_text(
    '<!doctype html>\n<html lang="ja">' + html.rstrip("\n") + "\n</html>\n",
    encoding="utf-8", newline="\n")  # lang必須: 無いとAndroidで中国語字形の漢字が混じる(監査high-5)

(DOCS / "manifest.webmanifest").write_text(json.dumps({
    "id": "/sumi-tokei/",
    "name": "sumi時計",
    "short_name": "sumi時計",
    "description": "秒までわかる。日本標準時にあわせる白黒の時計",
    "lang": "ja",
    "dir": "ltr",
    "start_url": ".",
    "scope": "./",
    "display": "standalone",
    "orientation": "any",  # 時計は横向きの大表示にも実需がある(電卓と違い縦固定にしない)
    "background_color": "#ffffff",
    "theme_color": "#ffffff",
    "shortcuts": [  # アイコン長押しの近道(Android)
        {"name": "秒読み", "url": "./?cd",
         "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}]}],
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

# sw.js はシリーズ共通のため、ここでは書かない。
# 正典は シリーズ管理/tools/sw.js.tpl 、配布は apply_sw.py が行う。
# VERSION が配信HTMLの内容ハッシュから決まるので、必ず「このビルドの後」に実行すること:
#     python ../シリーズ管理/tools/apply_sw.py tokei


def draw24(bg="#ffffff", fg="#000000"):
    """白地24グリッドの時計モチーフ: 帳面の枠+丸い文字盤+針、下に同期状態の一行(アプリの画面と同じ構図)"""
    im = Image.new("RGB", (24, 24), bg)
    d = ImageDraw.Draw(im)
    d.rectangle([3, 2, 20, 21], outline=fg)    # 枠(帳面。シリーズ同族)
    d.ellipse([6, 4, 17, 15], outline=fg)      # 文字盤
    d.rectangle([11, 6, 12, 10], fill=fg)      # 長針(12時へ)
    d.rectangle([12, 9, 15, 10], fill=fg)      # 短針(3時へ)
    d.rectangle([6, 18, 17, 18], fill=fg)      # 時計の下の一行(同期状態の行)
    return im


def icon(px, name, cell):
    base = draw24().resize((24 * cell, 24 * cell), Image.NEAREST)
    cv = Image.new("RGB", (px, px), "#ffffff")
    off = (px - 24 * cell) // 2
    cv.paste(base, (off, off))
    cv.save(DOCS / name)


icon(512, "icon-512.png", 21)
icon(192, "icon-192.png", 8)
icon(180, "apple-touch-icon.png", 7)
icon(512, "icon-maskable-512.png", 13)  # maskable: 図案を中央61%に収めAndroidの切り抜きに耐える

# 起動スプラッシュ(無地。ダーク起動時に白く光らないための地色だけを敷く)
for w, h, lw, lh, r in SPLASH:
    for dark in (False, True):
        bg = "#000000" if dark else "#ffffff"
        cv = Image.new("RGB", (w, h), bg)
        cv.save(DOCS / f"splash-{w}x{h}{'-dark' if dark else ''}.png")

print(f"OK: docs/ 一式を生成した(スプラッシュ {len(SPLASH) * 2}枚)")
