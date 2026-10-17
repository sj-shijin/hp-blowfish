#!/usr/bin/env python3
"""按公开清单构建网站，私有知识库只作为输入，发布文件写入独立目录。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from export_knowledge import export


def build(site: Path, vault: Path, manifest: Path, output: Path, *,
          preview: bool = False, port: int = 1314) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    exported = output / 'export'
    report = export(vault, manifest, exported, preview=preview)
    settings = ['resourceDir = ' + json.dumps(str(output / 'resources'))]
    if preview:
        settings += ['baseURL = ' + json.dumps(f'http://127.0.0.1:{port}/'),
                     'enableRobotsTXT = false']
    settings += ['[params]', 'knowledgePreview = ' + str(preview).lower()]
    if preview:
        settings += ['robots = "noindex, nofollow"']
    # 仅挂载网站内容及清单导出的结果，完整知识库不会进入 Hugo 的内容目录。
    settings += ['[module]']
    for source, target in [(site / 'content', 'content'),
                           (exported / 'content', 'content'),
                           (site / 'static', 'static'),
                           (exported / 'static', 'static')]:
        settings += ['[[module.mounts]]', 'source = ' + json.dumps(str(source)),
                     'target = ' + json.dumps(target)]
    config = output / 'build.toml'
    config.write_text('\n'.join(settings) + '\n', encoding='utf-8')
    destination = output / 'public'
    command = ['hugo', '--source', str(site),
               '--config', f'{site}/config/_default/hugo.toml,{config}',
               '--destination', str(destination), '--cacheDir', str(output / 'cache'),
               '--noBuildLock', '--cleanDestinationDir']
    if not preview:
        command += ['--gc', '--minify']
    subprocess.run(command, check=True)
    report.update({'output': str(output), 'public': str(destination)})
    if preview:
        report['url'] = f'http://127.0.0.1:{port}/knowledge/'
    report_name = 'preview-report.json' if preview else 'build-report.json'
    (output / report_name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    site = args.site.resolve()
    vault = (args.vault or site / 'knowledge-vault').resolve()
    manifest = (args.manifest or site / 'knowledge/publish.json').resolve()
    output = (args.output or Path(tempfile.mkdtemp(prefix='pkw-site-build-'))).resolve()
    print(json.dumps(build(site, vault, manifest, output), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
