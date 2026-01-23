"""
构建器模块

编排整个构建流程：下载 -> 转换 -> 生成索引 -> 复制前端资源
"""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config_manager import Config
from .downloader import FileItem, fetch_file_list, download_all
from .converter import convert_file


@dataclass
class IndexEntry:
    """索引条目"""
    name: str           # 显示名称（无扩展名）
    path: str           # 相对于 docs/ 的 HTML 文件路径
    type: str           # "file" 或 "dir"
    children: list["IndexEntry"] = field(default_factory=list)


def build_index_tree(files: list[FileItem]) -> list[IndexEntry]:
    """
    根据文件列表构建目录树索引

    Args:
        files: 文件列表

    Returns:
        根级索引条目列表
    """
    # 使用嵌套字典构建树结构
    tree: dict = {}

    for f in files:
        parts = Path(f.path).parts
        current = tree

        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # 文件节点
                name_no_ext = Path(part).stem
                html_path = str(Path(f.path).with_suffix(".html"))
                current[part] = {
                    "_is_file": True,
                    "_name": name_no_ext,
                    "_path": html_path,
                }
            else:
                # 目录节点
                if part not in current:
                    current[part] = {"_is_file": False, "_name": part}
                current = current[part]

    def _to_entries(node: dict) -> list[IndexEntry]:
        """递归转换为 IndexEntry 列表"""
        entries: list[IndexEntry] = []

        for key, value in node.items():
            if key.startswith("_"):
                continue

            if value.get("_is_file"):
                entries.append(IndexEntry(
                    name=value["_name"],
                    path=value["_path"],
                    type="file",
                ))
            else:
                children = _to_entries(value)
                entries.append(IndexEntry(
                    name=value.get("_name", key),
                    path="",
                    type="dir",
                    children=children,
                ))

        # 目录排在前面，文件排在后面；同类型按名称排序
        entries.sort(key=lambda e: (0 if e.type == "dir" else 1, e.name.lower()))
        return entries

    return _to_entries(tree)


def index_to_dict(entries: list[IndexEntry]) -> list[dict]:
    """将 IndexEntry 转换为 JSON 兼容的字典列表"""
    result = []
    for e in entries:
        item = {
            "name": e.name,
            "title": e.name,  # 前端 app.js 需要 title 字段
            "type": "folder" if e.type == "dir" else "file",
        }
        if e.type == "file":
            item["path"] = e.path
        else:
            item["children"] = index_to_dict(e.children)
        result.append(item)
    return result


def run_build(config: Config, output_dir: Optional[Path] = None) -> None:
    """
    执行完整构建流程

    Args:
        config: 配置对象
        output_dir: 输出目录，默认为 {project_root}/reader
    """
    if output_dir is None:
        output_dir = config.project_root / "reader"

    docs_dir = output_dir / "docs"
    temp_dir = config.project_root / ".cache" / "downloads"

    print("=" * 60)
    print("Prolet Tools - 文档构建")
    print("=" * 60)
    print(f"仓库: {config.github_repo}")
    print(f"分支: {config.target_branch}")
    print(f"输出: {output_dir}")
    print()

    # 1. 获取文件列表
    print("[1/4] 获取文件列表...")
    file_list = fetch_file_list(config)
    print(f"  找到 {len(file_list)} 个文档文件")

    if not file_list:
        print("  ⚠ 未找到任何文档，构建终止")
        return

    # 2. 下载文件
    print("\n[2/4] 下载文件...")
    temp_dir.mkdir(parents=True, exist_ok=True)
    downloaded, download_failed = download_all(config, file_list, temp_dir)
    print(f"  下载完成: {len(downloaded)} 个文件")

    # 3. 转换文件
    print("\n[3/4] 转换文件...")
    docs_dir.mkdir(parents=True, exist_ok=True)
    convert_failed: list[str] = []

    def _convert_one(local_path: Path):
        # 计算相对路径
        rel_path = local_path.relative_to(temp_dir)
        html_path = docs_dir / rel_path.with_suffix(".html")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            html_content = convert_file(local_path)
            html_path.write_text(html_content, encoding="utf-8")
            return True, str(rel_path)
        except Exception as e:
            return False, f"{rel_path}: {e}"

    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_convert_one, path) for path in downloaded]
        completed = 0
        for future in as_completed(futures):
            completed += 1
            success, info = future.result()
            if not success:
                convert_failed.append(info)
                print(f"    ⚠ 转换失败: {info}")
            if completed % 500 == 0 or completed == len(downloaded):
                print(f"  [{completed}/{len(downloaded)}] 转换完成")

    # 4. 生成索引
    print("\n[4/4] 生成索引...")
    index_tree = build_index_tree(file_list)
    index_data = index_to_dict(index_tree)

    index_path = output_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    print(f"  索引已保存: {index_path}")

    # 5. 复制前端资源（如果指定了 front-text 路径）
    if config.front_text_path and config.front_text_path.exists():
        print("\n[额外] 复制前端资源...")
        front_reader = config.front_text_path / "reader"
        if front_reader.exists():
            for item in ["index.html", "app.js", "css"]:
                src = front_reader / item
                dst = output_dir / item
                if src.exists():
                    if src.is_dir():
                        if dst.exists():
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                    print(f"  复制: {item}")

    # 输出失败文件清单
    all_failed = download_failed + convert_failed
    if all_failed:
        print("\n" + "=" * 60)
        print(f"⚠ 失败文件清单 ({len(all_failed)} 个):")
        print("=" * 60)
        for f in all_failed:
            print(f"  - {f}")
        print("=" * 60)

    print("\n" + "=" * 60)
    print("✓ 构建完成!")
    if all_failed:
        print(f"  (有 {len(all_failed)} 个文件处理失败)")
    print("=" * 60)
