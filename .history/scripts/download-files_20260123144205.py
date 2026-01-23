#!/usr/bin/env python3
"""
使用 GitHub API 只下载 txt/md/docx 文件
避免下载整个仓库
"""

import os
import json
import subprocess
import urllib.request
import urllib.error
import time
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(os.environ.get('GITHUB_WORKSPACE', '.'))

ALLOWED_EXTENSIONS = {'.txt', '.md', '.docx'}

USER_AGENT = 'text-sync-tool/1.0'
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

def log_info(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'[Download-API][{timestamp}] {msg}')

def log_error(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'[Download-API][{timestamp}] [ERROR] {msg}')

is_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

if is_github_actions:
    current_dir = Path.cwd()
    if 'tools' in str(current_dir).lower():
        WORKSPACE = current_dir
        log_info(f'GitHub Actions 环境，调整工作目录: {WORKSPACE}')

def load_config():
    config_path = WORKSPACE / 'reader' / 'config.json'
    
    if not config_path.exists():
        log_error(f'配置文件不存在: {config_path}')
        log_error(f'当前工作目录: {WORKSPACE}')
        log_error(f'请检查配置文件是否正确上传到仓库')
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        log_info(f'配置文件加载成功: {config_path}')
        return config
    except (json.JSONDecodeError, IOError) as e:
        log_error(f'配置文件加载失败: {e}')
        return {}

def get_github_repo():
    override_repo = os.environ.get('GITHUB_REPO_OVERRIDE', '')
    if override_repo:
        log_info(f'从环境变量覆盖读取仓库: {override_repo}')
        return override_repo
    
    config = load_config()
    github_repo = config.get('github_repo', '')
    if github_repo:
        log_info(f'从配置文件读取仓库: {github_repo}')
        return github_repo
    
    github_repo = os.environ.get('GITHUB_REPOSITORY', '')
    if github_repo:
        log_info(f'从环境变量读取仓库: {github_repo}')
        return github_repo
    
    log_info('使用默认仓库: coolapijust/front-text')
    return 'coolapijust/front-text'

def get_source_dir():
    config = load_config()
    source_dir = config.get('source_dir', '')
    log_info(f'从配置文件读取源目录: {source_dir if source_dir else "无（扫描整个仓库）"}')
    return source_dir

def get_token():
    token = os.environ.get('GITHUB_TOKEN', '')
    if token:
        log_info('GitHub Token 已配置')
    else:
        log_error('GitHub Token 未配置，可能遇到速率限制')
    return token

def get_branch():
    config = load_config()
    branch = config.get('target_branch', '')
    if branch:
        log_info(f'从配置文件读取目标分支: {branch}')
        return branch
    
    branch = os.environ.get('GITHUB_REF', 'refs/heads/master').replace('refs/heads/', '')
    if not branch:
        branch = 'master'
        log_info(f'使用默认分支: master')
    log_info(f'目标分支: {branch}')
    return branch

def run_cmd(cmd, capture=True):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture, text=capture, timeout=60)
        if capture and result.returncode != 0:
            log_error(f'命令执行失败: {cmd}')
            log_error(f'错误输出: {result.stderr}')
        return result
    except subprocess.TimeoutExpired:
        log_error(f'命令执行超时: {cmd}')
        return None
    except Exception as e:
        log_error(f'命令执行异常: {cmd} - {e}')
        return None

def get_tree_files_recursive(sha, repo, token):
    log_info(f'获取文件树: {sha}')
    url = f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': USER_AGENT
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            tree = data.get('tree', [])
            log_info(f'文件树获取成功，共 {len(tree)} 个项目')
            return tree
    except urllib.error.HTTPError as e:
        log_error(f'HTTP 错误: {e.code} - {e.reason}')
        if e.code == 404:
            log_error(f'仓库或分支不存在: {repo}')
        elif e.code == 403:
            log_error(f'API 速率限制或权限不足')
        return []
    except urllib.error.URLError as e:
        log_error(f'URL 错误: {e.reason}')
        return []
    except json.JSONDecodeError as e:
        log_error(f'JSON 解析错误: {e}')
        return []
    except TimeoutError as e:
        log_error(f'请求超时: {e}')
        return []
    except Exception as e:
        log_error(f'获取文件树异常: {e}')
        return []

def get_file_sha_cache():
    cache_path = WORKSPACE / '.github' / 'file-sha-cache.json'
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(f'读取 SHA 缓存失败: {e}')
    return {}

def save_file_sha_cache(cache):
    cache_path = WORKSPACE / '.github' / 'file-sha-cache.json'
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error(f'保存 SHA 缓存失败: {e}')

def sanitize_filename(path):
    invalid_chars = {'"', ':', '<', '>', '|', '*', '?', '\r', '\n'}
    path_obj = Path(path)
    filename = path_obj.name
    
    if not any(char in filename for char in invalid_chars):
        return path, False
    
    original_filename = filename
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    new_path = str(path_obj.parent / filename)
    return new_path, original_filename != filename

def download_file(path, sha, repo, token, sha_cache, max_retries=MAX_RETRIES):
    sanitized_path, was_sanitized = sanitize_filename(path)
    dest = WORKSPACE / sanitized_path
    
    cache_key = sanitized_path
    cached_sha = sha_cache.get(cache_key)
    if cached_sha == sha and dest.exists() and dest.stat().st_size > 0:
        log_info(f'[Cache] 跳过未变更文件: {sanitized_path}')
        return True
    
    if was_sanitized:
        log_info(f'[Sanitize] 文件名包含无效字符，已替换: {path} -> {sanitized_path}')
    
    url = f'https://api.github.com/repos/{repo}/git/blobs/{sha}'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw',
        'User-Agent': USER_AGENT
    }
    
    for attempt in range(max_retries):
        try:
            log_info(f'[Download] 开始下载: {path} (尝试 {attempt + 1}/{max_retries})')
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                content = resp.read()
                
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, 'wb') as f:
                    f.write(content)
                
                sha_cache[cache_key] = sha
                log_info(f'[Download] 下载成功: {sanitized_path} ({len(content)} bytes)')
                return True
                
        except urllib.error.HTTPError as e:
            log_error(f'[Download] HTTP 错误: {e.code} - {e.reason} - {path}')
            if e.code == 404:
                log_error(f'[Download] 文件不存在: {path}')
                return False
            elif e.code == 403:
                log_error(f'[Download] API 速率限制或权限不足: {path}')
                if attempt < max_retries - 1:
                    wait_time = 60
                    log_info(f'[Download] 等待 {wait_time} 秒后重试...')
                    time.sleep(wait_time)
                    continue
                else:
                    return False
            elif e.code >= 500:
                if attempt < max_retries - 1:
                    wait_time = 5
                    log_info(f'[Download] 服务器错误，等待 {wait_time} 秒后重试...')
                    time.sleep(wait_time)
                    continue
                else:
                    return False
            else:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    log_info(f'[Download] 等待 {wait_time} 秒后重试...')
                    time.sleep(wait_time)
                    continue
                else:
                    return False
                    
        except urllib.error.URLError as e:
            log_error(f'[Download] 网络错误: {e.reason} - {path}')
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                log_info(f'[Download] 等待 {wait_time} 秒后重试...')
                time.sleep(wait_time)
                continue
            else:
                return False
                
        except TimeoutError as e:
            log_error(f'[Download] 请求超时: {path}')
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                log_info(f'[Download] 等待 {wait_time} 秒后重试...')
                time.sleep(wait_time)
                continue
            else:
                return False
                
        except Exception as e:
            log_error(f'[Download] 未知错误: {e} - {path}')
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                log_info(f'[Download] 等待 {wait_time} 秒后重试...')
                time.sleep(wait_time)
                continue
            else:
                return False
    
    return False

def main():
    log_info('=' * 60)
    log_info('开始下载文件')
    log_info('=' * 60)
    
    REPO = get_github_repo()
    TOKEN = get_token()
    BRANCH = get_branch()
    SOURCE_DIR = get_source_dir()
    
    log_info(f'仓库: {REPO}')
    log_info(f'分支: {BRANCH}')
    log_info(f'源目录: {SOURCE_DIR}')
    log_info(f'工作目录: {WORKSPACE}')
    
    sha_cache = get_file_sha_cache()
    
    result = run_cmd(f'git ls-remote https://github.com/{REPO}.git {BRANCH}')
    if not result or result.returncode != 0:
        log_error(f'无法获取仓库信息: {REPO}/{BRANCH}')
        log_error(f'返回码: {result.returncode if result else "None"}')
        log_error(f'错误输出: {result.stderr if result else "None"}')
        log_error(f'请检查：')
        log_error(f'1. 仓库名称是否正确: {REPO}')
        log_error(f'2. 分支名称是否正确: {BRANCH}')
        log_error(f'3. 仓库是否为公开仓库')
        return
    
    if not result.stdout or not result.stdout.strip():
        log_error(f'git ls-remote 输出为空')
        return
    
    lines = result.stdout.strip().split('\n')
    if not lines or not lines[0]:
        log_error(f'无法解析 git ls-remote 输出')
        return
    
    commit_sha = lines[0].split()[0]
    log_info(f'最新 Commit: {commit_sha}')
    
    files = get_tree_files_recursive(commit_sha, REPO, TOKEN)
    if not files:
        log_error('无法获取文件列表，退出')
        return
    
    downloaded = 0
    cached = 0
    failed = 0
    skipped = 0
    skipped_ext = 0
    skipped_dir = 0
    
    log_info(f'开始处理文件...')
    log_info(f'允许的扩展名: {ALLOWED_EXTENSIONS}')
    
    for item in files:
        if item['type'] != 'blob':
            continue
        
        path = item['path']
        
        ext = Path(path).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            skipped_ext += 1
            continue
        
        result = download_file(path, item['sha'], REPO, TOKEN, sha_cache)
        if result:
            dest = WORKSPACE / path
            if dest.exists() and dest.stat().st_size > 0:
                cached_sha = sha_cache.get(path)
                if cached_sha == item['sha']:
                    cached += 1
                else:
                    downloaded += 1
        else:
            failed += 1
    
    log_info(f'跳过统计: 目录过滤={skipped_dir}, 扩展名过滤={skipped_ext}, 其他={skipped - skipped_dir - skipped_ext}')
    
    save_file_sha_cache(sha_cache)
    
    log_info('=' * 60)
    log_info(f'下载完成: {downloaded} 文件下载, {cached} 文件缓存, {failed} 文件失败, {skipped} 文件跳过')
    log_info('=' * 60)
    
    log_info('下载目录结构:')
    for root, dirs, files in os.walk(WORKSPACE):
        level = root.replace(str(WORKSPACE), '').count(os.sep)
        indent = '  ' * level
        print(f'{indent}{os.path.basename(root)}/')
        subindent = '  ' * (level + 1)
        for file in files[:10]:
            print(f'{subindent}{file}')
        if len(files) > 10:
            print(f'{subindent}... 还有 {len(files) - 10} 个文件')

if __name__ == '__main__':
    main()
