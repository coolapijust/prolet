"""
内容转换器模块

将 txt/md/docx 文件转换为 HTML 片段。
本模块的逻辑参考 front-text 的转换实现，确保生成的 HTML 结构与前端兼容。
"""

from pathlib import Path
from typing import Optional
import html


def convert_txt(content: str) -> str:
    """
    将纯文本转换为 HTML (智能段落化)
    
    规则：
    1. 自动识别双换行符 (\n\n) 为段落分隔。
    2. 处理首行缩进。
    3. 识别 URL 并转换为链接。
    """
    import re
    
    # 1. 预处理：标准化换行并去除 BOM
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # 2. 分段
    paragraphs = content.split('\n\n')
    html_parts = []
    
    link_pattern = re.compile(r'(https?://\S+)')
    
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
            
        # 3. 处理段落内的单换行
        # 如果看起来像包含强制换行的长文本，这里可以将 \n 替换为 <br> 或者合并
        # 为了保持原文意图，我们保留段内换行作为 <br>
        p_html = html.escape(p).replace('\n', '<br>')
        
        # 4. 自动链接
        p_html = link_pattern.sub(r'<a href="\1" target="_blank">\1</a>', p_html)
        
        html_parts.append(f'<p>{p_html}</p>')
    
    # 如果段落很少（可能是一整块代码或诗歌），或者包含特殊缩进，退回 <pre> 可能会更好
    # 但作为通用阅读器，<p> 更适合大多数情况
    
    joined_html = '\n'.join(html_parts)
    return f'<div class="txt-wrapper content-prose">{joined_html}</div>'


def convert_markdown(content: str) -> str:
    """
    将 Markdown 转换为 HTML

    使用 markdown-it-py 渲染，确保与前端 markdown-it 一致。
    """
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        # 回退到简单预格式化
        print("⚠ markdown-it-py 未安装，使用简单 HTML 转换")
        escaped = html.escape(content)
        return f'<pre class="md-fallback">{escaped}</pre>'

    # 配置与前端 markdown-it 尽量一致
    md = MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})

    # 启用常用插件功能
    md.enable(["table", "strikethrough"])

    return md.render(content)


def _clean_html_content(html_result: str) -> str:
    """清理转换后的 HTML 内容，去除冗余标签和特定标识"""
    import re
    
    # 1. 剔除分页标识 (针对 Word/TXT)
    # 匹配类似于 ==========第1页========== 或 =============第 12 页=============
    page_marker_pattern = re.compile(r'={3,}.*?第\s?\d+\s?页.*?={3,}', re.IGNORECASE)
    html_result = page_marker_pattern.sub('', html_result)
    
    # 2. 清理冗余的空段落 (mammoth 经常产生这种标签)
    # 匹配 <p></p>, <p> </p>, <p>&nbsp;</p>, <p><br /></p> 等
    empty_p_pattern = re.compile(r'<p>\s*(?:&nbsp;|<br\s*/?>)?\s*</p>', re.IGNORECASE)
    html_result = empty_p_pattern.sub('', html_result)
    
    # 3. 连续的 <br> 合并 (可选，视需要而定)
    # html_result = re.sub(r'(<br\s*/?>\s*){3,}', '<br><br>', html_result)
    
    return html_result.strip()


def convert_docx(file_path: Path, assets_dir: Optional[Path] = None, assets_prefix: str = "") -> str:
    """
    将 DOCX 文件转换为 HTML

    使用 mammoth 库进行转换，带有自定义样式映射和图片处理
    """
    try:
        import mammoth
    except ImportError:
        return '<p class="error">无法转换 DOCX 文件：mammoth 库未安装</p>'

    # 自定义样式映射
    style_map = """
    p[style-name='Heading 1'] => h1:fresh
    p[style-name='Heading 2'] => h2:fresh
    p[style-name='Heading 3'] => h3:fresh
    p[style-name='Heading 4'] => h4:fresh
    p[style-name='Title'] => h1.title:fresh
    p[style-name='Subtitle'] => p.subtitle:fresh
    p[style-name='Quote'] => blockquote:fresh
    r[style-name='Strong'] => strong
    
    # 中文样式映射
    p[style-name='标题 1'] => h1:fresh
    p[style-name='标题 2'] => h2:fresh
    p[style-name='标题 3'] => h3:fresh
    p[style-name='标题 4'] => h4:fresh
    p[style-name='标题 5'] => h5:fresh
    p[style-name='标题 #1'] => h1:fresh
    p[style-name='标题 #2'] => h2:fresh
    p[style-name='标题 #3'] => h3:fresh
    p[style-name='标题 #4'] => h4:fresh
    
    # 结构样式
    p[style-name='目录'] => div.toc-entry:fresh
    p[style-name^='TOC'] => div.toc-entry:fresh
    p[style-name='表格标题'] => p.caption:fresh
    p[style-name='脚注'] => p.footnote:fresh
    p[style-name='页眉'] => p.header:fresh
    p[style-name='页脚'] => p.footer:fresh
    """

    # 图片处理函数
    convert_image = None
    if assets_dir:
        def image_handler(image):
            # 生成唯一文件名
            import hashlib
            with image.open() as image_bytes:
                content = image_bytes.read()
                ext = image.content_type.split("/")[-1]
                if ext == "jpeg": ext = "jpg"
                
                # 使用内容哈希作为文件名
                md5 = hashlib.md5(content).hexdigest()
                filename = f"{md5}.{ext}"
                
                # 保存文件
                target_file = assets_dir / filename
                if not target_file.exists():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_bytes(content)
                
                # 返回 img 标签属性
                return {
                    "src": f"{assets_prefix}/{filename}",
                    "loading": "lazy",
                    "class": "docx-image"
                }
        convert_image = mammoth.images.inline(image_handler)

    try:
        with open(file_path, "rb") as f:
            # 如果配置了图片处理，传给 mammoth
            kwargs = {"style_map": style_map}
            if convert_image:
                kwargs["convert_image"] = convert_image
                
            result = mammoth.convert_to_html(f, **kwargs)
            
            if result.messages:
                # 过滤警告，忽略常见的样式丢失警告
                ignore_patterns = [
                    "Unrecognised paragraph style: 正文文本",
                    "Unrecognised paragraph style: Body Text",
                    "Unrecognised run style",
                    "An unrecognised element was ignored: w:cr"
                ]
                for msg in result.messages:
                    msg_str = str(msg.message)
                    if any(p in msg_str for p in ignore_patterns):
                        continue
                    print(f"  mammoth warning: {msg_str}")
            
            # 使用内容清洗
            cleaned_html = _clean_html_content(result.value)
            return f'<div class="docx-wrapper">{cleaned_html}</div>'
    except Exception as e:
        escaped = html.escape(str(e))
        return f'<p class="error">DOCX 转换失败: {escaped}</p>'


def _inject_metadata(html_content: str, text_content: str) -> str:
    """注入字数统计和阅读时间"""
    # 简单估算：中文字符 + 英文单词
    import re
    # 移除 HTML 标签获取纯文本用于统计
    clean_text = re.sub(r'<[^>]+>', '', text_content).strip()
    if not clean_text:
        return html_content
        
    char_count = len(clean_text)
    # 按 400 字/分钟估算
    read_time = max(1, round(char_count / 400))
    
    meta_html = (
        f'<div class="doc-metadata" style="color: #666; font-size: 0.9em; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eee;">'
        f'<span>字数: {char_count}</span> &nbsp; '
        f'<span>预计阅读: {read_time} 分钟</span>'
        f'</div>'
    )
    return meta_html + html_content


def convert_file(file_path: Path, assets_dir: Optional[Path] = None, assets_prefix: str = "") -> str:
    """
    根据文件类型自动选择转换器

    Args:
        file_path: 源文件路径
        assets_dir: 资源保存目录 (用于 DOCX 图片)
        assets_prefix: HTML 中引用的资源前缀

    Returns:
        HTML 字符串
    """
    ext = file_path.suffix.lower()
    html_result = ""

    # 对于文本文件，先读取内容
    content = ""
    try:
        # 尝试常见编码
        for encoding in ["utf-8", "gbk", "gb2312", "utf-16"]:
            try:
                content = file_path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            # 所有编码都失败，使用二进制读取并强制解码
            content = file_path.read_bytes().decode("utf-8", errors="replace")
    except Exception as e:
        return f'<p class="error">文件读取失败: {html.escape(str(e))}</p>'

    if ext == ".docx":
        # DOCX 特殊处理，通过 mammoth 转换
        # mammoth 返回的 HTML 已经是结果，但也需要注入 metadata
        # 由于 mammoth 不直接返回纯文本，我们需要从转换后的 HTML 中提取（略显粗糙但有效）
        html_result = convert_docx(file_path, assets_dir, assets_prefix)
        # 再次利用 _inject_metadata，传入 html_result 作为 text_content (会被用于统计)
        return _inject_metadata(html_result, html_result)

    if ext == ".md":
        html_result = convert_markdown(content)
    elif ext == ".txt":
        html_result = convert_txt(content)
    else:
        # 未知类型，作为纯文本处理
        html_result = convert_txt(content)
        
    return _inject_metadata(html_result, content)


def generate_html_page(title: str, content_html: str, config: Optional[dict] = None) -> str:
    """
    生成完整的 HTML 页面（独立阅读用）

    注意：通常只需要 HTML 片段供前端 app.js 动态加载，本函数可选使用。

    Args:
        title: 页面标题
        content_html: 内容 HTML
        config: 可选配置

    Returns:
        完整 HTML 页面字符串
    """
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        pre {{ background: #f5f5f5; padding: 1em; overflow-x: auto; }}
        code {{ background: #f5f5f5; padding: 0.2em 0.4em; border-radius: 3px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    </style>
</head>
<body>
    <article class="document-content">
        {content_html}
    </article>
</body>
</html>'''
