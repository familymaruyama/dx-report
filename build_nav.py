#!/usr/bin/env python3
"""dx-report の月切替バー・リダイレクトスタブ・index.html を再生成する。

構成ルール:
  <key>.html            固定URL。常に最新のレポート実体を置く（共有するのはこれ）
  <key>-YYYY-MM.html    過去分アーカイブ。実体を置く
  redirect_stubs        最新と同じ月の旧URL。固定URLへ転送するだけの薄いHTML

使い方:
  python3 build_nav.py          # reports.json を読んで全ページを再生成
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "reports.json"

NAV_START = "<!-- DXNAV:START -->"
NAV_END = "<!-- DXNAV:END -->"
LIST_START = "<!-- DXLIST:START -->"
LIST_END = "<!-- DXLIST:END -->"

NAV_CSS = """
<style>
.dxnav{max-width:1000px;margin:14px auto 0;padding:10px 20px;display:flex;align-items:center;
  gap:8px;flex-wrap:wrap;font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,system-ui,sans-serif;}
.dxnav .dxnav-lbl{font-size:11.5px;font-weight:800;letter-spacing:.06em;color:#7C756B;margin-right:2px;}
.dxnav a{font-size:12.5px;font-weight:700;text-decoration:none;color:#544E47;background:#fff;
  border:1px solid #EAE3D6;border-radius:999px;padding:5px 13px;transition:border-color .12s,color .12s;}
.dxnav a:hover{border-color:#E57138;color:#C85A28;}
.dxnav a.is-current{background:#FBF0E6;border-color:#E57138;color:#C85A28;}
.dxnav a.dxnav-idx{border-style:dashed;color:#7C756B;}
@media print{.dxnav{display:none;}}
</style>
""".strip()


def build_nav(member, current_file):
    """1メンバー分の月切替バーHTMLを組み立てる。"""
    pages = [(f"{member['key']}.html", f"{member['latest_label']}（最新）")]
    pages += [(a["file"], a["label"]) for a in member["archives"]]

    links = []
    for href, label in pages:
        cls = ' class="is-current"' if href == current_file else ""
        links.append(f'<a href="{href}"{cls}>{label}</a>')
    links.append('<a href="index.html" class="dxnav-idx">一覧 →</a>')

    return (
        f"{NAV_START}\n{NAV_CSS}\n"
        f'<nav class="dxnav"><span class="dxnav-lbl">📄 {member["display"]}さんのレポート</span>'
        + "".join(links)
        + f"</nav>\n{NAV_END}"
    )


def inject_nav(path, nav_html):
    """<body> 直後に月切替バーを挿入する。既存バーがあれば差し替える（冪等）。"""
    html = path.read_text(encoding="utf-8")

    if NAV_START in html and NAV_END in html:
        html = re.sub(
            re.escape(NAV_START) + r".*?" + re.escape(NAV_END),
            lambda _: nav_html,
            html,
            flags=re.S,
        )
    else:
        m = re.search(r"<body[^>]*>", html, re.I)
        if not m:
            raise SystemExit(f"[ERROR] <body> が見つかりません: {path.name}")
        html = html[: m.end()] + "\n" + nav_html + "\n" + html[m.end():]

    path.write_text(html, encoding="utf-8")


STUB_MARK = "<!-- DXSTUB -->"


def write_stub(path, target, display, label):
    """旧URL用の転送ページ。最新と同じ月の実体は固定URL側にしか置かないため。

    既存ファイルが転送ページでない＝過去分の実体なら、上書きせず中断する
    （翌月に過去分へ退避したあと redirect_stubs を消し忘れた場合の事故防止）。
    """
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if STUB_MARK not in current:
            raise SystemExit(
                f"[ERROR] {path.name} は転送ページではなく実体です。上書きを中断しました。\n"
                f"        過去分へ退避済みなら reports.json の redirect_stubs から "
                f"{path.name} を外し、archives に移してください。"
            )

    html = f"""<!DOCTYPE html>
{STUB_MARK}
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="0; url={target}">
<title>DX戦略課 月次進捗レポート（{display}）</title>
</head>
<body style="font-family:system-ui,sans-serif;background:#FBF8F3;color:#544E47;padding:40px 20px;text-align:center;">
<p>{display}さんの{label}のレポートは、最新版の固定URLへ移動しました。</p>
<p><a href="{target}" style="color:#C85A28;font-weight:700;">レポートを開く →</a></p>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def build_index(members):
    """index.html のリンク一覧を固定URLで再生成する。"""
    path = BASE / "index.html"
    html = path.read_text(encoding="utf-8")

    rows = []
    for m in members:
        rows.append(
            f'      <li><a href="{m["key"]}.html"><span class="who"><b>{m["display"]}</b>'
            f' ／ {m["latest_label"]}</span><span class="arw">開く →</span></a></li>'
        )
        for a in m["archives"]:
            rows.append(
                f'      <li class="past"><a href="{a["file"]}"><span class="who">{m["display"]}'
                f' ／ {a["label"]}<em>過去分</em></span><span class="arw">開く →</span></a></li>'
            )

    block = LIST_START + "\n" + "\n".join(rows) + "\n      " + LIST_END

    if LIST_START in html and LIST_END in html:
        html = re.sub(
            re.escape(LIST_START) + r".*?" + re.escape(LIST_END),
            lambda _: block,
            html,
            flags=re.S,
        )
    else:
        m = re.search(r"<ul>(.*?)</ul>", html, re.S)
        if not m:
            raise SystemExit("[ERROR] index.html に <ul> が見つかりません")
        html = html[: m.start(1)] + "\n" + block + "\n    " + html[m.end(1):]

    path.write_text(html, encoding="utf-8")
    print(f"  index.html … {len(rows)}件のリンクを再生成")


def main():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    members = data["members"]

    for m in members:
        latest = BASE / f"{m['key']}.html"
        if not latest.exists():
            raise SystemExit(f"[ERROR] 固定URLの実体がありません: {latest.name}")

        targets = [latest] + [BASE / a["file"] for a in m["archives"]]
        for t in targets:
            if not t.exists():
                raise SystemExit(f"[ERROR] ファイルがありません: {t.name}")
            inject_nav(t, build_nav(m, t.name))
            print(f"  {t.name} … 月切替バーを更新")

        archive_files = {a["file"] for a in m["archives"]}
        for stub in m["redirect_stubs"]:
            if stub in archive_files:
                raise SystemExit(
                    f"[ERROR] {stub} が archives と redirect_stubs の両方にあります。"
                    "過去分の実体を残すなら redirect_stubs から外してください。"
                )
            write_stub(BASE / stub, f"{m['key']}.html", m["display"], m["latest_label"])
            print(f"  {stub} … 転送ページを生成")

    build_index(members)
    print("完了")


if __name__ == "__main__":
    sys.exit(main())
