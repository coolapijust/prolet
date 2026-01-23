# front-text 依赖文件清单

## 项目依赖说明

本项目从 `https://github.com/coolapijust/front-text` 引入以下文件，实现前端与项目解耦。

---

## 依赖文件列表

### 1. 同步脚本

| 文件 | 来源路径 | 本地路径 | 说明 |
|------|---------|---------|------|
| `sync.py` | `front-text/scripts/sync.py` | `frontend/scripts/sync.py` | 增强版同步脚本，支持 GitHub Actions 环境检测 |

**功能**：
- 扫描文档目录（txt/md/docx 文件）
- 转换为静态 HTML 文件
- 生成索引文件（index.json）
- 支持配置文件读取
- 支持排除规则（exclude_patterns、exclude_files）

**依赖库**：
- `python-docx`：处理 DOCX 文件（备选方案）
- `mammoth`：处理 DOCX 文件（推荐方案，更好的 HTML 转换）

**环境变量**：
- `SYNC_ROOT_DIR`：指定项目根目录（GitHub Actions 中自动设置）

---

### 2. 前端页面

| 文件 | 来源路径 | 本地路径 | 说明 |
|------|---------|---------|------|
| `index.html` | `front-text/reader/index.html` | `reader/index.html` | 主页面，包含侧边栏、内容区域 |

**功能**：
- 响应式布局（支持移动端）
- 侧边栏目录树
- 搜索功能
- 主题切换（亮/暗模式）
- 返回顶部按钮
- Mermaid 图表支持
- Markdown 渲染

**外部依赖**（CDN）：
- Mermaid: `https://s4.zstatic.net/npm/mermaid@10.9.1/dist/mermaid.min.js`
- Markdown-it: `https://s4.zstatic.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js`
- Highlight.js: `https://s4.zstatic.net/npm/highlight.js@11.9.0/`

---

### 3. 前端逻辑

| 文件 | 来源路径 | 本地路径 | 说明 |
|------|---------|---------|------|
| `app.js` | `front-text/reader/app.js` | `reader/app.js` | 前端交互逻辑 |

**功能**：
- 加载配置文件（config.json）
- 加载索引文件（index.json）
- 渲染侧边栏目录树
- 文档搜索
- 文档加载和渲染
- 主题切换
- 侧边栏折叠/展开
- 移动端菜单
- 返回顶部功能
- Mermaid 图表渲染

---

### 4. 样式文件

| 文件 | 来源路径 | 本地路径 | 说明 |
|------|---------|---------|------|
| `style.css` | `front-text/reader/css/style.css` | `reader/css/style.css` | 前端样式 |

**功能**：
- 响应式布局
- 亮/暗主题样式
- 侧边栏样式
- 内容区域样式
- 代码高亮样式
- 表格样式
- 移动端适配

---

## 文件来源

### 主项目维护的文件

| 文件 | 说明 |
|------|------|
| `txt/` | 文档内容目录（或整个仓库扫描）|
| `reader/config.json` | 配置文件 |
| `scripts/download-files.py` | GitHub API 下载脚本 |

### front-text 提供的文件

| 文件 | 说明 |
|------|------|
| `scripts/sync.py` | 同步脚本 |
| `reader/index.html` | 主页面 |
| `reader/app.js` | 前端逻辑 |
| `reader/css/style.css` | 样式文件 |

---

## Workflow 架构

### Sync Documents (sync-api.yml)

```yaml
1. 检出主项目
   - txt/（或整个仓库）
   - reader/config.json
   - scripts/download-files.py

2. 检出 front-text
   - scripts/sync.py

3. 下载文档
   - python scripts/download-files.py

4. 安装依赖
   - pip install -q python-docx mammoth

5. 同步文档
   - python frontend/scripts/sync.py
   - 生成 reader/docs/
   - 生成 reader/index.json

6. 上传 artifact
   - name: docs
   - path: reader/
```

### Build and Deploy (build-frontend.yml)

```yaml
1. 检出主项目
   - reader/config.json

2. 下载 docs artifact
   - 从 Sync Documents workflow

3. 检出 front-text
   - reader/index.html
   - reader/app.js
   - reader/css/style.css

4. 合并前端
   - cp -r frontend/reader/* reader/

5. 部署到 GitHub Pages
   - actions/deploy-pages@v4
```

---

## 配置说明

### reader/config.json

```json
{
  "github_repo": "ProletRevDicta/Prolet",
  "source_dir": "",
  "target_branch": "master",
  "site_title": "社会主义历史文献资料引擎",
  "sidebar_title": "文献目录",
  "theme": "light",
  "max_content_width": 900,
  "enable_search": true,
  "enable_back_to_top": true,
  "exclude_patterns": [],
  "exclude_files": [],
  "home_page": null
}
```

**配置项说明**：
- `github_repo`：文档源仓库（用于 download-files.py 下载）
- `source_dir`：文档源目录（空字符串表示扫描整个仓库）
- `target_branch`：目标分支（默认 master）
- `site_title`：网站标题
- `sidebar_title`：侧边栏标题
- `theme`：主题（light/dark）
- `max_content_width`：内容区域最大宽度（px）
- `enable_search`：是否启用搜索
- `enable_back_to_top`：是否启用返回顶部按钮
- `exclude_patterns`：排除的目录模式（通配符）
- `exclude_files`：排除的文件名列表
- `home_page`：首页文件名（需存在于源目录）

---

## 注意事项

### 1. sync.py 环境变量

在 GitHub Actions 中，需要设置 `SYNC_ROOT_DIR` 环境变量：

```yaml
- name: Run Sync Script
  env:
    SYNC_ROOT_DIR: ${{ github.workspace }}
  run: |
    python frontend/scripts/sync.py
```

### 2. front-text/sync.py 修改

需要在 front-text 仓库中修改 `scripts/sync.py`，支持 `SYNC_ROOT_DIR` 环境变量：

```python
if is_github_actions:
    sync_root = os.environ.get('SYNC_ROOT_DIR', Path.cwd())
    CONFIG_FILE = Path(sync_root) / 'reader' / 'config.json'
elif os.environ.get('SYNC_ROOT_DIR'):
    sync_root = os.environ.get('SYNC_ROOT_DIR')
    CONFIG_FILE = Path(sync_root) / 'reader' / 'config.json'
```

详见：[SYNC_PY_FIX.md](file:///D:/Users/prolet-tools/SYNC_PY_FIX.md)

### 3. 本地开发

本地开发时，如果需要测试 sync.py，需要设置环境变量：

**Windows PowerShell**：
```powershell
$env:SYNC_ROOT_DIR = "D:\path\to\prolet-tools"
python frontend/scripts/sync.py
```

**Windows CMD**：
```cmd
set SYNC_ROOT_DIR=D:\path\to\prolet-tools
python frontend/scripts/sync.py
```

**Linux/Mac**：
```bash
export SYNC_ROOT_DIR=/path/to/prolet-tools
python frontend/scripts/sync.py
```

---

## 更新记录

### 2026-01-22

- ✅ 实现 GitHub Actions 双 Workflow 架构
- ✅ 从 front-text 拉取前端文件和同步脚本
- ✅ 修复 download-files.py 路径问题
- ✅ 添加 SYNC_ROOT_DIR 环境变量支持
