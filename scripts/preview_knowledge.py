#!/usr/bin/env python3
"""在独立临时目录构建知识库网页，可选启动仅本机可访问的预览。"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile

from build_site import build as build_site


class PreviewRequestHandler(SimpleHTTPRequestHandler):
    # Markdown 源文件按 UTF-8 纯文本展示，避免浏览器猜测编码或下载未知媒体类型。
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        '.md': 'text/plain; charset=utf-8',
        '.markdown': 'text/plain; charset=utf-8',
    }


def build(site: Path, vault: Path, manifest: Path, output: Path, *, port: int = 1314) -> dict:
    return build_site(site, vault, manifest, output, preview=True, port=port)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--port', type=int, default=1314)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    site = args.site.resolve()
    vault = (args.vault or site / 'knowledge-vault').resolve()
    manifest = (args.manifest or site / 'knowledge/publish.json').resolve()
    output = (args.output or Path(tempfile.mkdtemp(prefix='pkw-web-preview-'))).resolve()
    report = build(site, vault, manifest, output, port=args.port)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if args.serve:
        handler = partial(PreviewRequestHandler, directory=report['public'])
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
        print('Local: ' + report['url'], flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
