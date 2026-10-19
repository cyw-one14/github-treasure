# GitHub Treasure

挖掘值得分享的 GitHub 开源项目，生成能直接复制到 X（Twitter）的中文安利帖，每条配上真实项目截图。

适合做开源工具推荐、AI 与效率工具选题，或者想把发现的好项目分享给兄弟们的人。

## 能帮你做什么

- **选项目**：默认筛选 6 个实用项目，覆盖 AI、效率工具、本地运行等方向；合格候选不足时可输出 5 个。
- **核实信息**：查看官方仓库、文档和近期活动，确认用途、安装方式、许可证及使用门槛。
- **写分享帖**：第一句话有强钩子，疑问、吐槽、场景描述都可以，按内容选最自然的表达。
- **配真实截图**：优先使用官方产品截图，必要时在后台截取公开演示页面，再逐张查看内容。
- **方便复制**：每条正文独立放在 `text` 代码块里，编号与配图放在外面，方便通过客户端的代码块复制入口逐条复制。

默认面向中文读者，优先选择有中文文档和中文界面的项目。介绍像给熟悉的兄弟安利工具，自然分段，不套固定四段结构，也不硬凑字数。

## 安装

在 Codex 中使用内置安装器，发送：

```text
$skill-installer 从 https://github.com/cyw-one14/github-treasure 安装 github-treasure Skill，SKILL.md 位于仓库根目录。
```

也可以手动安装到某个项目的 `.agents/skills/github-treasure/`。在目标项目根目录执行：

**Windows / PowerShell**

```powershell
New-Item -ItemType Directory -Force .agents\skills | Out-Null
git clone https://github.com/cyw-one14/github-treasure.git .agents/skills/github-treasure
```

**macOS / Linux**

```bash
mkdir -p .agents/skills
git clone https://github.com/cyw-one14/github-treasure.git .agents/skills/github-treasure
```

项目内的 `.agents/skills/` 用于项目级发现；需要跨项目使用时，可将整个 Skill 文件夹放到 `~/.agents/skills/`。安装后若没有出现在可用 Skill 中，重启 Codex。安装和发现规则见 [OpenAI 官方 Skills 文档](https://learn.chatgpt.com/docs/build-skills)。

更新手动安装的版本：

```bash
git -C .agents/skills/github-treasure pull --ff-only
```

如果安装在其他位置，将命令中的路径换成实际位置。

## 使用

安装后，在 Codex 中直接发送请求。

**生成今日分享**

```text
使用 $github-treasure，帮我生成今天的 6 条开源项目分享。
```

**指定方向与受众**

```text
使用 $github-treasure，找 5 个适合普通办公用户的开源效率工具，优先中文界面和 Windows 可用的项目。
```

**调整已有文案**

```text
按最新版 $github-treasure，把刚才这六条重新写一版，开头别都用疑问句，保留逐条复制和原来的配图。
```

每次调用生成一批内容，不会自动创建定时任务或发布到 X。

## 输出是什么样

每条包含一段可独立发布的完整文案和对应截图：

1. 编号放在正文之外。
2. 正文单独放进 `text` 代码块，末尾保留 GitHub 仓库链接。
3. 真实项目截图放在代码块下方，与所属文案相邻。

复制入口由客户端提供，复制正文时不会混入编号和图片。

文案会围绕具体场景介绍项目的用途和亮点，按需要说明 API、模型、费用或平台限制。开头句式、段落数和收尾方式可以不同，不统一使用疑问句，也不逐条补一句“值得收藏”。

本地成品保存在运行项目的 `output/<日期或批次>/`，例如：

```text
output/2026-10-19/
├── posts.txt
└── images/
    ├── 01-项目截图.png
    ├── 02-项目截图.webp
    └── ...
```

`posts.txt` 保存纯文本帖子，`images/` 保存选中的真实截图；聊天中的文本块与配图排列由 Codex 完成。成品目录不覆盖，修订时使用新批次名。

## 运行环境

需要能读取 GitHub 和官方项目资料的联网 Codex 环境，以及能查看并展示图片的工具。完整的选题、核验和写作由 Codex 按 [SKILL.md](SKILL.md) 执行；Python 脚本负责批量取图和整理成品。

- **Python 与 Pillow**：用于取得、检查和整理图片。
- **Playwright（可选）**：仅在需要截取公开演示页面时使用，可配合已有 Chrome / Edge，或安装 Chromium。

截图在无头浏览器中完成。下载成功和图片可解码之后，还需要实际看图核验，不能把 Logo、错误页或概念图当成产品截图。

## 本地开发

仓库根目录就是 Skill 根目录，克隆后可直接修改：

```bash
git clone https://github.com/cyw-one14/github-treasure.git
cd github-treasure
```

**Windows / PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install Pillow
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

**macOS / Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install Pillow
.venv/bin/python -m unittest discover -s tests -v
```

需要网页截图时，在同一虚拟环境中额外安装 `playwright`，再选择已有浏览器或安装 Chromium。输入字段、批量命令、缓存和成品整理流程见 [截图工具说明](references/screenshots.md)。

### 文件说明

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | 选题、核验、写作与交付规则 |
| [agents/openai.yaml](agents/openai.yaml) | Skill 名称、简介和默认提示词 |
| [references/screenshots.md](references/screenshots.md) | 截图与成品整理的使用说明 |
| [scripts/project_screenshots.py](scripts/project_screenshots.py) | 批量获取官方截图，必要时截取公开演示 |
| [scripts/finalize_output.py](scripts/finalize_output.py) | 校验图文对应关系，整理成品并清理本批工作文件 |
| [tests/](tests/) | 离线行为测试 |

`.venv/`、`.work/` 和 `output/` 已加入 Git 忽略规则，分别存放本地依赖、临时工作文件和成品。
