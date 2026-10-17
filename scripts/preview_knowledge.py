#!/usr/bin/env python3
"""在独立临时目录构建知识库网页，可选启动仅本机可访问的预览。"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile

from export_knowledge import export


class PreviewRequestHandler(SimpleHTTPRequestHandler):
    # Markdown 源文件按 UTF-8 纯文本展示，避免浏览器猜测编码或下载未知媒体类型。
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        '.md': 'text/plain; charset=utf-8',
        '.markdown': 'text/plain; charset=utf-8',
    }


def build(site: Path, vault: Path, manifest: Path, output: Path, *, port: int = 1314) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    exported = output / 'export'
    report = export(vault, manifest, exported, preview=True)
    config = output / 'preview.toml'
    config.write_text('\n'.join([
        'baseURL = ' + json.dumps(f'http://127.0.0.1:{port}/'),
        'resourceDir = ' + json.dumps(str(output / 'resources')),
        'enableRobotsTXT = false',
        '[params]', 'robots = "noindex, nofollow"', 'knowledgePreview = true',
        '[module]',
        '[[module.mounts]]', 'source = ' + json.dumps(str(site / 'content')), 'target = "content"',
        '[[module.mounts]]', 'source = ' + json.dumps(str(exported / 'content')), 'target = "content"',
        '[[module.mounts]]', 'source = ' + json.dumps(str(site / 'static')), 'target = "static"',
        '[[module.mounts]]', 'source = ' + json.dumps(str(exported / 'static')), 'target = "static"',
    ]) + '\n', encoding='utf-8')
    destination = output / 'public'
    subprocess.run(['hugo', '--source', str(site), '--config', f'{site}/config/_default/hugo.toml,{config}',
                    '--destination', str(destination), '--cacheDir', str(output / 'cache'),
                    '--noBuildLock', '--cleanDestinationDir'], check=True)
    report.update({'url': f'http://127.0.0.1:{port}/knowledge/', 'output': str(output), 'public': str(destination)})
    (output / 'preview-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--port', type=int, default=1314)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    site = args.site.resolve()
    vault = (args.vault or site / 'knowledge-vault').resolve()
    output = (args.output or Path(tempfile.mkdtemp(prefix='pkw-web-preview-'))).resolve()
    report = build(site, vault, args.manifest.resolve(), output, port=args.port)
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
