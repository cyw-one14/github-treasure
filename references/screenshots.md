# 批量取得项目截图

在允许本地 Python 和网络访问的环境使用 `scripts/project_screenshots.py`。它减少逐页浏览与工具往返，不能替代项目调研、来源确认及看图检查。获取和保存公开官方素材用于本次配图；不得用它绕过当前环境的访问、媒体展示或权限限制。

## 运行

命令中的脚本路径以 Skill 根目录为基准；工作目录不在 Skill 根目录时改用脚本绝对路径。本仓库根目录就是 Skill 根目录，开发时直接修改仓库内文件即可；安装后也可能位于项目的 `.agents/skills/github-treasure/` 或用户 Skill 目录，无需为了本地开发额外复制到全局目录。输入 JSON 放在系统临时目录，截图工作目录使用运行项目的 `.work/<唯一批次>/`；最终成品放在 `output/<日期或批次>/`，不把运行文件写进 Skill 源码。

基础依赖只有 Pillow，优先使用已有可用的 Python；缺少时在任务虚拟环境安装：

```text
python -m pip install Pillow
```

输入 `projects.json` 是数组，例如：

```json
[
  {"repo": "glanceapp/glance"},
  {
    "repo": "CorentinTh/it-tools",
    "demo_url": "https://it-tools.tech"
  }
]
```

字段：

- `repo`：必填，`owner/repository`，同批不可重复。
- `image_url`：可选，已从官方来源核实的图片直链。提供后优先直接获取；否则读取默认分支 README，提取并排序图片，最多尝试三张。
- `demo_url`：可选，已核实的官方公开演示地址；没有可用图片时才访问。脚本不猜测演示地址，不登录、不接管个人浏览器会话。
- `selector`：可选，仅与 `demo_url` 一起使用；从实际页面观察到的 CSS 选择器，用于截取界面区域。省略时截取 1440×900 浏览器视口。

```text
python scripts/project_screenshots.py --input projects.json --output-dir .work/batch-001
```

默认三个项目并发，`--workers 1` 可改为串行；`--refresh` 忽略缓存并重新获取。HTTP 单次等待设为 15 秒，单文件限制 12 MiB；页面导航与截图另设有限超时。外部网络和 DNS 状况仍可能影响总耗时。

## 浏览器兜底（可选）

只在需要截取演示页面时安装 Playwright。可使用电脑已有的 Chrome / Edge，避免另下载浏览器：

```text
python -m pip install playwright
python scripts/project_screenshots.py --input projects.json --output-dir .work/batch-001 --browser-channel chrome
```

Edge 用 `--browser-channel msedge`。没有可用浏览器时，安装 Playwright 的 Chromium 后省略 channel：

```text
python -m playwright install chromium
```

脚本创建独立的无头浏览器上下文，加载公开页面，等待 DOM 与短暂渲染后截图；不等待可能永不结束的 `networkidle`。需要登录、出现验证码或浏览器依赖缺失时报告失败。页面加载缓慢仍可能得到不完整画面，必须看图再决定重试、指定区域或替换候选。缺失依赖只返回安装提示，不自动安装。

不得用 `open_in_codex`、CUA 或桌面浏览器打开可见标签页来取得这些截图。调研优先用 GitHub 连接器、搜索和 HTTP；本脚本的 `headless=True` 是后台网页渲染，不接管个人浏览器。视频 Skill 使用 FFmpeg 从视频文件取帧，这种命令行处理及临时文件释放方式值得参考，但 FFmpeg 不负责网页渲染；本工具不依赖外部视频 Skill，也不复制字幕拼图、Cookies 或下载功能。

## 读取结果与核验

标准输出仅包含 `manifest_path` 与每个项目的精简结果；同一结果列表保存为输出目录下的 `manifest.json`。

- 状态为 `downloaded`（官方图片）、`captured`（演示截图）或 `cached`（缓存命中）时，读取 `image_path`（绝对路径）、`source_url`、`source_kind`、`width`、`height`、`elapsed_seconds`。
- 每个结果都保留 `needs_visual_review: true`。格式、尺寸、成功下载均不能证明它是项目界面；使用图片查看工具逐张检查，不把 Logo、错误页、宣传图或空白页当成成品。
- 任一项目失败不会中断其余项目；查看该项的 `error`，只补充失败项目的已核实地址并重跑，或更换项目。
- 退出码 `0`：本批都取得图片；`1`：至少一项获取失败；`2`：输入或依赖有问题。非零时仍检查已经产出的成功结果。
- 缓存只用于当前批次重试，按仓库、输入地址、选择器及浏览器选项区分，复用前重新验证文件存在且可解码。要获取最新界面，显式加 `--refresh`。缓存命中仍需本次看图确认；成功整理成品后清除本批缓存。

## 整理与清理

逐张检查后，创建临时 `posts.json` 数组，每项为 `repo`、`text` 和 `visually_reviewed: true`。`text` 为自然分段的完整分享文案，末尾单独一行保留对应的 `🔗 https://github.com/owner/repo`。未实际看图时不得写入已检查标志。

```text
python scripts/finalize_output.py --posts posts.json --work-dir .work/batch-001 --output-dir output/2026-10-18
```

整理器验证 5–6 条独立且非空的文案、末尾仓库链接、图文对应和真实文件后，一次产出 `posts.txt` 与 `images/`；不限制文案的段落数、开头标点或字数，语气和信息质量由发送前检查把关。现有成品目录不覆盖，重复执行使用新批次名。只清除有本工具归属标记的工作目录中已知生成文件，不删除陌生文件或输入素材。缺图、未看图或文案不合格时停止整理并保留工作文件供修复。

确认最终目录完整后，删除本次临时输入 JSON 及空工作目录；测试素材放在 `TemporaryDirectory` 中自动释放。保留 Skill 源码、测试代码和可复用依赖环境。最终图片必须引用 `output/` 内的绝对路径，不能引用随后会清除的工作文件。已清理工作文件后重跑同一任务会重新获取图片。

在所属帖子下直接嵌入 `![项目名界面截图](最终图片绝对路径)`。内部核验时保留项目与官方来源对应关系；调研记录不额外混进用户的成品目录，工具输出也不要混入发帖文案。

实现依据：[Playwright 截图 API](https://playwright.dev/python/docs/screenshots)、[使用已有 Chrome / Edge](https://playwright.dev/python/docs/browsers)、[GitHub README API](https://docs.github.com/en/rest/repos/contents#get-a-repository-readme)。
