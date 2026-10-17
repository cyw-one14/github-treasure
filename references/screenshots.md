# 批量取得项目截图

在允许本地 Python 和网络访问的环境使用 `scripts/project_screenshots.py`。它减少逐页浏览与工具往返，不能替代项目调研、来源确认及看图检查。获取和保存公开官方素材用于本次配图；不得用它绕过当前环境的访问、媒体展示或权限限制。

## 运行

命令中的脚本路径以 Skill 根目录为基准；工作目录不在 Skill 根目录时改用脚本绝对路径。输入和图片保存在当前任务的工作目录，避免污染已安装的 Skill。

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
python scripts/project_screenshots.py --input projects.json --output-dir screenshots
```

默认三个项目并发，`--workers 1` 可改为串行；`--refresh` 忽略缓存并重新获取。HTTP 单次等待设为 15 秒，单文件限制 12 MiB；页面导航与截图另设有限超时。外部网络和 DNS 状况仍可能影响总耗时。

## 浏览器兜底（可选）

只在需要截取演示页面时安装 Playwright。可使用电脑已有的 Chrome / Edge，避免另下载浏览器：

```text
python -m pip install playwright
python scripts/project_screenshots.py --input projects.json --output-dir screenshots --browser-channel chrome
```

Edge 用 `--browser-channel msedge`。没有可用浏览器时，安装 Playwright 的 Chromium 后省略 channel：

```text
python -m playwright install chromium
```

脚本创建独立的无头浏览器上下文，加载公开页面，等待 DOM 与短暂渲染后截图；不等待可能永不结束的 `networkidle`。需要登录、出现验证码或浏览器依赖缺失时报告失败。页面加载缓慢仍可能得到不完整画面，必须看图再决定重试、指定区域或替换候选。缺失依赖只返回安装提示，不自动安装。

## 读取结果与核验

标准输出仅包含 `manifest_path` 与每个项目的精简结果；同一结果列表保存为输出目录下的 `manifest.json`。

- 状态为 `downloaded`（官方图片）、`captured`（演示截图）或 `cached`（缓存命中）时，读取 `image_path`（绝对路径）、`source_url`、`source_kind`、`width`、`height`、`elapsed_seconds`。
- 每个结果都保留 `needs_visual_review: true`。格式、尺寸、成功下载均不能证明它是项目界面；使用图片查看工具逐张检查，不把 Logo、错误页、宣传图或空白页当成成品。
- 任一项目失败不会中断其余项目；查看该项的 `error`，只补充失败项目的已核实地址并重跑，或更换项目。
- 退出码 `0`：本批都取得图片；`1`：至少一项获取失败；`2`：输入或依赖有问题。非零时仍检查已经产出的成功结果。
- 缓存按仓库、输入地址、选择器及浏览器选项区分，复用前重新验证文件存在且可解码。缓存没有自动过期；要获取最新界面，显式加 `--refresh`。缓存命中仍需本次看图确认。

核验通过后，在所属帖子下直接嵌入 `![项目名界面截图](本地绝对路径)`。内部保留仓库、官方来源页面和结果路径的对应关系；工具输出不要混入最终发帖文案。

实现依据：[Playwright 截图 API](https://playwright.dev/python/docs/screenshots)、[使用已有 Chrome / Edge](https://playwright.dev/python/docs/browsers)、[GitHub README API](https://docs.github.com/en/rest/repos/contents#get-a-repository-readme)。
