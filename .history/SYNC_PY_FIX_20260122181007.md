# sync.py 修改说明

## 问题

在新的架构中，sync.py 从 front-text 仓库拉取，位于 `frontend/scripts/sync.py`，但配置文件在项目根目录的 `reader/config.json`。

## 解决方案

修改 front-text/scripts/sync.py 的配置文件路径逻辑：

### 修改前（第 17-24 行）：

```python
CONFIG_FILE = Path(__file__).parent.parent / 'reader' / 'config.json'

is_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

if is_github_actions:
    current_dir = Path.cwd()
    if 'tools' in str(current_dir).lower():
        CONFIG_FILE = current_dir / 'reader' / 'config.json'
```

### 修改后：

```python
CONFIG_FILE = Path(__file__).parent.parent / 'reader' / 'config.json'

is_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

if is_github_actions:
    sync_root = os.environ.get('SYNC_ROOT_DIR', Path.cwd())
    CONFIG_FILE = Path(sync_root) / 'reader' / 'config.json'
elif os.environ.get('SYNC_ROOT_DIR'):
    sync_root = os.environ.get('SYNC_ROOT_DIR')
    CONFIG_FILE = Path(sync_root) / 'reader' / 'config.json'
```

## 说明

- 使用环境变量 `SYNC_ROOT_DIR` 指定项目根目录
- 在 GitHub Actions 中，workflow 会自动设置 `SYNC_ROOT_DIR: ${{ github.workspace }}`
- 在本地开发时，需要手动设置 `SYNC_ROOT_DIR` 环境变量指向主项目根目录
  - Windows PowerShell: `$env:SYNC_ROOT_DIR = "D:\path\to\prolet-tools"`
  - Windows CMD: `set SYNC_ROOT_DIR=D:\path\to\prolet-tools`
  - Linux/Mac: `export SYNC_ROOT_DIR=/path/to/prolet-tools`
- 这样无论 sync.py 在哪个目录，都能找到正确的配置文件

## 验证

修改后，sync.py 能够：
1. 在 GitHub Actions 中正确找到配置文件（使用环境变量 `SYNC_ROOT_DIR`）
2. 在本地开发时，通过设置 `SYNC_ROOT_DIR` 环境变量指向主项目根目录来找到配置文件
3. 如果不设置环境变量，则使用默认的相对路径（适用于 front-text 仓库独立运行）
