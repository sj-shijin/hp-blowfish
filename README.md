# hp-blowfish

ShiJin 的个人网站，使用 [Hugo](https://gohugo.io/) 与 [Blowfish](https://blowfish.page/) 主题，发布在 GitHub Pages。

站点地址：https://shijin.space/

## 本地预览

需要已安装 Hugo Extended（当前构建使用 0.165.0）。

```bash
git clone https://github.com/sj-shijin/hp-blowfish.git
cd hp-blowfish
git submodule update --init --recursive themes/blowfish
hugo server
```

推送到 `main` 后，GitHub Actions 会自动构建并部署。

## 项目技能

`.agents/skills/blowfish` 链接到 `themes/blowfish/.claude/skills/blowfish`，使用主题自带的官方 Agent Skill。`SKILL.md` 已包含标准的 `name`、`description` 和操作说明；正文随主题子模块固定版本更新，无须另外维护副本。初始化主题子模块后，该链接即可读取。

在本仓库的 ChatGPT 桌面本地项目或 Codex 会话中，可以请求“使用 Blowfish skill 调整网站”；技能选择器可用时，在 ChatGPT 中输入 `@` 搜索 Blowfish；本机 Codex 将官方包识别为 `blowfish:blowfish`，可用 `$blowfish:blowfish` 引用。`.agents/skills` 是项目级发现目录，支持符号链接；若刚迁移后未出现，可重新打开项目会话。参见 [OpenAI 技能文档](https://learn.chatgpt.com/docs/build-skills)。网页版 ChatGPT 的工作区技能需通过其安装入口管理，本地目录不会自动上传。

## 知识库本地预览

`knowledge-vault/` 是私有仓库的子模块，固定到一个已提交版本。笔记仍在 Obsidian 的正式知识库中维护；这里仅作为构建输入。常规网站构建和 GitHub Actions 目前只读取公开网站内容，不加载私有子模块。主页和导航栏均有知识库入口；没有导出笔记时，只显示空目录页。

有私有仓库读取权限的本机先获取子模块：

```bash
git submodule update --init knowledge-vault
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements-knowledge.txt
```

已有安装 PyYAML 的 Python 环境可以直接使用，无须重复安装。将本地预览清单保存在网站仓库之外；格式如下，其中路径相对于知识库根目录，`slug` 决定稳定的网址：

```json
{
  "categories": [
    {"id": "example-field", "title": "领域"}
  ],
  "notes": [
    {
      "path": "领域/基础知识/概念.md",
      "slug": "concept",
      "category": "example-field",
      "group": "基础知识"
    }
  ],
  "attachments": ["领域/附件/diagram.png"]
}
```

```bash
.venv/bin/python scripts/preview_knowledge.py \
  --manifest /absolute/path/to/local-preview.json --serve
```

打开 `http://127.0.0.1:1314/knowledge/`。服务只监听本机；关闭时按 `Ctrl+C`。每次运行重新生成快照，修改清单或笔记后重新启动。默认读取子模块；需要检查尚未提交的正式笔记时，可加 `--vault /absolute/path/to/obsidian-vault`。所有生成内容、缓存及图片处理结果都放在独立临时目录，不写入正式库或网站的 `content/`、`static/`。

当前支持普通 Markdown、公式、图片、Obsidian 双链（含别名、章节链接）和清单内笔记的反向链接。仅复制清单中明确允许且实际引用的附件；指向未选笔记的链接显示为文字。整篇笔记嵌入和块引用暂不支持，遇到时停止导出。

知识库使用主题默认纯色背景。正文复用 Blowfish 的目录组件：宽屏时在右侧固定显示，窄屏时在正文上方折叠。开关为 `article.showTableOfContents`；整个知识库的跨笔记导航由知识库目录页负责。

顶部采用 Blowfish 原生嵌套菜单：知识库 → 领域。导出器根据清单中实际选中的笔记生成领域页面和菜单项；领域目录为 `/knowledge/<category-id>/`，页面按 `group` 分组。类别顺序取决于 `categories` 的顺序，分组按首次出现的顺序排列，组内笔记按 `notes` 顺序排列。`category` 和 `group` 可省略，兼容原来的无分类清单；类别 `id` 与笔记 `slug` 不能相同，以免网址冲突。

增加类别时，在本地清单的 `categories` 中增加一项，再为要展示的笔记填写该 `category` 和可选 `group`，重新运行预览即可；无需逐篇修改导航配置。清单仍显式列出每篇笔记，新增文件不会自动进入展示范围。网页分类只作用于导出结果，不改变知识库目录或笔记属性。

浏览器从 `/knowledge/` 选择领域。每篇笔记的面包屑可以返回领域或分组；既有笔记仍使用 `/knowledge/<slug>/`。程序可从 `/knowledge/index.json` 读取 `categories`、笔记的 `category`／`group`、网址和关联，再获取 `/knowledge/raw/<slug>.md`。这些入口都仅包含本次清单中的内容。

Markdown 导出文件使用 UTF-8，预览服务通过 `Content-Type: text/plain; charset=utf-8` 让浏览器直接按纯文本显示，文件仍保留 `.md` 格式。更新预览脚本后，需要停止旧服务并重新启动。正式托管后的响应头由托管服务决定，上线时需再核验。

## 同步与公开范围

在正式知识库提交并推送后，更新本地网站引用：

```bash
git -C knowledge-vault fetch origin
git -C knowledge-vault checkout --detach origin/main
git diff --submodule
```

检查通过后再将 `knowledge-vault` 的版本变更提交到网站。不要直接在子模块副本编辑笔记，避免出现两个独立维护的来源。

`knowledge/publish.json` 是未来公开发布的候选清单，目前为空，且尚未接入生产构建。正式公开前需要确认笔记和附件范围，再接入仅能读取私有库的构建凭据与导出步骤。本地预览清单和临时输出不能提交或复制到公开网站仓库。

目前完整跑通的是本地流程：正式知识库提交并推送 → 网站更新子模块版本 → 预览脚本按本地清单导出 → Hugo 构建 → 本机浏览。网站远端现有的流程是推送 `main` 后构建公开网站并部署到 GitHub Pages；知识库的生产导出还没有接入该流程。仅推送私有知识库不会更新子模块引用或触发网站发布。

导出器的测试全部使用独立临时知识库：

```bash
.venv/bin/python -m unittest discover -s tests -p test_knowledge_export.py -v
```
