#!/usr/bin/env python3
"""
把 HTML 文章转换为 Hexo md 源文件
"""
import re
import os
from html import unescape

def extract_html_content(html_file):
    """从 HTML 中提取标题和内容"""
    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 提取标题
    title_match = re.search(r'<title>([^<]+)</title>', html)
    title = title_match.group(1).replace(' - 阿蒲的技术空间', '') if title_match else 'Untitled'
    
    # 提取 <article> 标签内的内容
    article_match = re.search(r'<article>(.*?)</article>', html, re.DOTALL)
    if not article_match:
        return title, ""
    
    content = article_match.group(1)
    
    # 处理 HTML 标签转换
    # 移除不需要的标签
    content = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', content, flags=re.DOTALL)
    
    # 转换常见标签
    content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', content)
    content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', content)
    content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', content)
    content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', content)
    content = re.sub(r'<br\s*/?>', '\n', content)
    content = re.sub(r'<strong>(.*?)</strong>', r'**\1**', content)
    content = re.sub(r'<b>(.*?)</b>', r'**\1**', content)
    content = re.sub(r'<em>(.*?)</em>', r'*\1*', content)
    content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', content)
    content = re.sub(r'<pre[^>]*class="ascii-art"[^>]*>(.*?)</pre>', r'```\n\1```\n', content, flags=re.DOTALL)
    content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'```\n\1```\n', content, flags=re.DOTALL)
    content = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', content)
    content = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', content)
    content = re.sub(r'<ul[^>]*>(.*?)</ul>', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'<ol[^>]*>(.*?)</ol>', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'<table[^>]*>(.*?)</table>', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'<thead[^>]*>(.*?)</thead>', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'<tbody[^>]*>(.*?)</tbody>', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'<tr[^>]*>(.*?)</tr>', r'\1\n', content, flags=re.DOTALL)
    content = re.sub(r'<th[^>]*>(.*?)</th>', r'|\1', content)
    content = re.sub(r'<td[^>]*>(.*?)</td>', r'|\1', content)
    content = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'> \1', content, flags=re.DOTALL)
    content = re.sub(r'<hr\s*/?>', r'---\n', content)
    content = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', content)
    content = re.sub(r'<div[^>]*>(.*?)</div>', r'\1\n', content)
    
    # 解码 HTML 实体
    content = unescape(content)
    
    # 清理多余空白
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()
    
    return title, content

# 文章配置
articles = [
    ('openclaw-deep-dive.html', '深度理解 OpenClaw：架构、原理与实践指南', ['OpenClaw', 'AI', '架构', '技术深度']),
    ('openclaw-architecture.html', 'OpenClaw 整体架构深度解析', ['OpenClaw', '架构']),
    ('openclaw-gateway.html', 'OpenClaw 网关核心原理', ['OpenClaw', '网关']),
    ('openclaw-channel.html', 'OpenClaw Channel 通道系统', ['OpenClaw', 'Channel']),
    ('openclaw-skills.html', 'OpenClaw Skills 技能系统', ['OpenClaw', 'Skills']),
    ('openclaw-memory.html', 'OpenClaw Memory 记忆系统', ['OpenClaw', '记忆系统']),
]

output_dir = '/root/.openclaw/workspace/my-tech-blog/source/_posts'
os.makedirs(output_dir, exist_ok=True)

for html_file, title, tags in articles:
    html_path = f'/root/.openclaw/workspace/my-tech-blog/{html_file}'
    if not os.path.exists(html_path):
        print(f"跳过: {html_file} 不存在")
        continue
    
    title, content = extract_html_content(html_path)
    
    # 生成 md 文件
    tags_str = '\n  - '.join(tags)
    md_content = f'''---
title: {title}
date: 2026-03-03
tags:
  - {tags_str}
---

{content}
'''
    
    # 文件名
    filename = html_file.replace('.html', '.md')
    md_path = os.path.join(output_dir, filename)
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"创建: {md_path}")

print("完成!")
