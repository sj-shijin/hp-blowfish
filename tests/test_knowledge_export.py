"""仅在 mkdtemp 创建的独立知识库中验证导出边界，不调用正式库或 MCP。"""
import json
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from urllib.request import Request, urlopen

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from export_knowledge import export
from preview_knowledge import PreviewRequestHandler, build


class KnowledgeExportTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='pkw-web-test-'))
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        # 测试不启动 Basic Memory；配置与数据库预留在独立目录。
        (self.root / 'state').mkdir()
        self.out = self.root / 'export'
        self.manifest = self.root / 'publish.json'
        (self.vault / '甲.md').write_text('''---
title: 甲
private_metadata: PRIVATE_METADATA_SENTINEL
---
# 甲

## 定义
公式 $x^2$。[[乙#基本区域|去乙页]]，[[未公开|待补资料]]。
![示意图](图.svg)
%%HIDDEN_COMMENT_SENTINEL%%

```markdown
[[未公开]] 与 $literal$ 均保持代码原样。
```

`$inline_literal$`
''')
        (self.vault / '乙.md').write_text('# 乙\n\n## 基本区域\n回到 [[甲|前置定义]]。\n\n$$x+y=1$$\n')
        (self.vault / '未公开.md').write_text('UNPUBLISHED_BODY_SENTINEL\n')
        (self.vault / '图.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.spec = {'notes': [{'path': '甲.md', 'slug': 'alpha'}, {'path': '乙.md', 'slug': 'beta'}], 'attachments': ['图.svg']}

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_export(self, spec=None):
        self.manifest.write_text(json.dumps(self.spec if spec is None else spec))
        return export(self.vault, self.manifest, self.out, preview=True)

    def test_links_math_sources_and_visibility(self):
        report = self.run_export()
        rendered = (self.out / 'content/knowledge/alpha.md').read_text()
        raw = (self.out / 'static/knowledge/raw/alpha.md').read_text()
        index = json.loads((self.out / 'static/knowledge/index.json').read_text())
        all_text = '\n'.join(p.read_text() for p in self.out.rglob('*') if p.is_file())
        self.assertIn('/knowledge/beta/#%E5%9F%BA%E6%9C%AC%E5%8C%BA%E5%9F%9F', rendered)
        self.assertIn('引用此笔记', rendered)
        self.assertIn(r'\(x^2\)', rendered)
        self.assertIn('$x^2$', raw)
        self.assertIn('[[未公开]] 与 $literal$', rendered)
        self.assertIn('`$inline_literal$`', rendered)
        self.assertIn('待补资料', rendered)
        for marker in ['UNPUBLISHED_BODY_SENTINEL', 'PRIVATE_METADATA_SENTINEL', 'HIDDEN_COMMENT_SENTINEL']:
            self.assertNotIn(marker, all_text)
        self.assertEqual(index['notes'][0]['backlinks'], ['beta'])
        self.assertEqual((report['notes'], report['attachments'], report['links']), (2, 1, 2))
        self.assertEqual(len(list((self.out / 'static/knowledge/attachments').iterdir())), 1)

    def test_markdown_http_response_declares_utf8(self):
        self.run_export()
        handler = partial(PreviewRequestHandler, directory=str(self.out / 'static'))
        with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}/knowledge/raw/alpha.md'
                for method in ['GET', 'HEAD']:
                    with self.subTest(method=method), urlopen(Request(url, method=method), timeout=5) as response:
                        self.assertEqual(response.headers.get_content_type(), 'text/plain')
                        self.assertEqual(response.headers.get_content_charset(), 'utf-8')
                        body = response.read()
                        if method == 'GET':
                            self.assertTrue(body.decode(response.headers.get_content_charset()).startswith('# 甲\n'))
                            self.assertIn('去乙页', body.decode('utf-8'))
                        else:
                            self.assertEqual(body, b'')
            finally:
                server.shutdown()
                thread.join()

    def test_removal_cleans_old_pages_raw_files_and_attachments(self):
        self.run_export()
        self.run_export({'notes': [{'path': '乙.md', 'slug': 'beta'}], 'attachments': []})
        self.assertFalse((self.out / 'content/knowledge/alpha.md').exists())
        self.assertFalse((self.out / 'static/knowledge/raw/alpha.md').exists())
        self.assertFalse((self.out / 'static/knowledge/attachments').exists())
        index = json.loads((self.out / 'static/knowledge/index.json').read_text())
        self.assertEqual([n['id'] for n in index['notes']], ['beta'])

    def test_empty_publish_list_exports_no_content(self):
        self.run_export()
        report = self.run_export({'categories': [{'id': 'empty', 'title': '未导出领域'}],
                                  'notes': [], 'attachments': []})
        self.assertEqual(report['notes'], 0)
        self.assertEqual(report['categories'], 0)
        self.assertEqual(list((self.out / 'content').rglob('*')), [])
        self.assertEqual(list((self.out / 'static').rglob('*')), [])

    def test_categories_keep_urls_and_remove_unused_sections(self):
        self.spec['categories'] = [{'id': 'math', 'title': '数学领域'}, {'id': 'unused', 'title': '未导出领域'}]
        for note, group in zip(self.spec['notes'], ['基础知识', '研究增量']):
            note.update(category='math', group=group)
        report = self.run_export()
        self.assertEqual(report['categories'], 1)
        category = self.out / 'content/knowledge/math/_index.md'
        metadata = yaml.safe_load(category.read_text().split('---')[1])
        self.assertEqual(metadata['knowledgeGroups'], ['基础知识', '研究增量'])
        self.assertEqual(metadata['menus']['main']['parent'], 'knowledge')
        self.assertFalse((self.out / 'content/knowledge/unused').exists())
        rendered = (self.out / 'content/knowledge/math/alpha.md').read_text()
        self.assertIn('url: /knowledge/alpha/', rendered)
        index = json.loads((self.out / 'static/knowledge/index.json').read_text())
        self.assertEqual(index['categories'][0]['notes'], ['alpha', 'beta'])
        self.assertEqual(index['notes'][0]['category'], 'math')
        self.assertEqual(index['notes'][0]['group'], '基础知识')
        self.assertEqual(index['notes'][0]['backlinks'], ['beta'])
        self.run_export({'notes': [{'path': '乙.md', 'slug': 'beta'}]})
        self.assertFalse(category.parent.exists())
        self.assertTrue((self.out / 'content/knowledge/beta.md').exists())

    def test_invalid_category_references_and_url_collisions_are_rejected(self):
        self.spec['notes'][0]['category'] = 'missing'
        with self.assertRaisesRegex(ValueError, '未定义'):
            self.run_export()
        self.spec['categories'] = [{'id': 'alpha', 'title': '网址冲突'}]
        with self.assertRaisesRegex(ValueError, '重复网址'):
            self.run_export()

    @unittest.skipUnless(shutil.which('hugo'), '需要本地 Hugo 才能验证类别导航')
    def test_hugo_renders_two_categories_groups_and_breadcrumbs(self):
        self.spec['categories'] = [{'id': 'math', 'title': '数学领域'}, {'id': 'systems', 'title': '系统领域'}]
        for note, group in zip(self.spec['notes'], ['基础知识', '研究增量']):
            note.update(category='math', group=group)
        (self.vault / '丙.md').write_text('# 丙\n\n独立领域。\n')
        self.spec['notes'].append({'path': '丙.md', 'slug': 'gamma', 'category': 'systems', 'group': '概览'})
        self.manifest.write_text(json.dumps(self.spec))
        site = Path(__file__).resolve().parents[1]
        build(site, self.vault, self.manifest, self.root / 'preview')
        public = self.root / 'preview/public'
        home = (public / 'index.html').read_text()
        category = (public / 'knowledge/math/index.html').read_text()
        note = (public / 'knowledge/alpha/index.html').read_text()
        for identifier in ['math', 'systems']:
            self.assertIn(f'/knowledge/{identifier}/', home)
        self.assertIn('nested-menu', home)
        self.assertIn('基础知识', category)
        self.assertIn('研究增量', category)
        self.assertLess(category.index('href="/knowledge/alpha/"'), category.index('href="/knowledge/beta/"'))
        self.assertIn('aria-label="知识库导航"', note)
        self.assertIn('/knowledge/math/', note)
        self.assertTrue((public / 'knowledge/raw/alpha.md').exists())

    def test_unapproved_attachment_stops_export(self):
        self.spec['attachments'] = []
        with self.assertRaisesRegex(ValueError, '附件'):
            self.run_export()

    def test_external_paths_and_symlinks_are_rejected(self):
        (self.root / 'outside.md').write_text('outside')
        (self.vault / 'escape.md').symlink_to(self.root / 'outside.md')
        for path in ['../outside.md', 'escape.md']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.run_export({'notes': [{'path': path, 'slug': 'escape'}]})

    def test_shortcodes_and_note_transclusion_are_rejected(self):
        for body in ['{{< include "private" >}}', '![[乙]]']:
            (self.vault / '甲.md').write_text('# 甲\n\n' + body)
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.run_export()

    @unittest.skipUnless(shutil.which('hugo'), '需要本地 Hugo 才能验证公式 HTML')
    def test_hugo_preserves_math_operators_as_text(self):
        # 回归：原始 <i 被浏览器当作标签，导致求和公式及后续内容缺失。
        (self.vault / '甲.md').write_text('# 甲\n\n行内 $x<y$。\n\n$$\n\\sum_{j<i} b_j^*\n$$\n')
        self.run_export()
        site = self.root / 'site'
        (site / 'layouts/knowledge/_markup').mkdir(parents=True)
        (site / 'layouts/shortcodes').mkdir()
        (site / 'layouts/shortcodes/katex.html').write_text('')
        (site / 'layouts/knowledge/single.html').write_text('<html><body>{{ .Content }}</body></html>')
        hook = Path(__file__).resolve().parents[1] / 'layouts/knowledge/_markup/render-passthrough.html'
        shutil.copyfile(hook, site / 'layouts/knowledge/_markup/render-passthrough.html')
        (site / 'hugo.toml').write_text('contentDir = ' + json.dumps(str(self.out / 'content')) + '''
[markup.goldmark.extensions.passthrough]
enable = true
[markup.goldmark.extensions.passthrough.delimiters]
block = [['$$', '$$']]
inline = [['\\(', '\\)']]
''')
        subprocess.run(['hugo', '--source', str(site), '--noBuildLock'], check=True, capture_output=True, text=True)
        html = (site / 'public/knowledge/alpha/index.html').read_text()
        self.assertIn(r'\(x&lt;y\)', html)
        self.assertIn(r'\sum_{j&lt;i} b_j^*', html)
        self.assertNotIn('j<i', html)


if __name__ == '__main__':
    unittest.main()
