#!/usr/bin/env python3
"""
修复博客文章中的 ASCII 架构图和代码块混排问题
- ASCII 图移到 <pre class="ascii-art"> 不带 code 标签
- 代码块保留 <pre><code class="language-xxx">
"""

import re
import os

# ASCII 图的特征：包含框线字符
ASCII_CHARS = ['┌', '┐', '└', '┘', '─', '│', '├', '┤', '┬', '┴', '┼']

def has_ascii_art(content):
    """检查内容是否包含 ASCII 图"""
    for char in ASCII_CHARS:
        if char in content:
            return True
    return False

def process_file(filepath):
    print(f"处理: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 替换 <pre><code>...content...</code></pre> 
    # 如果内容是 ASCII 图，改为 <pre class="ascii-art">...content...</pre>
    # 否则保持 <pre><code>...content...</code></pre>
    
    # 匹配 <pre><code> 或 <pre><code class="...">
    pattern = r'<pre><code( class="language-[^"]*")?>(.*?)</code></pre>'
    
    def replace_match(m):
        lang_class = m.group(1) or ''
        inner = m.group(2)
        
        # 解码 HTML 实体
        inner = inner.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        
        if has_ascii_art(inner):
            # 是 ASCII 图，移除 code 标签，添加到 pre
            return f'<pre class="ascii-art">{inner}</pre>'
        else:
            # 是代码，保持原样
            return m.group(0)
    
    content = re.sub(pattern, replace_match, content, flags=re.DOTALL)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ 已修复")
    else:
        print(f"  - 无需修复")

# 需要修复的文件
files = [
    'openclaw-gateway.html',
    'openclaw-channel.html', 
    'openclaw-skills.html',
    'openclaw-memory.html'
]

for f in files:
    path = f'/root/.openclaw/workspace/my-tech-blog/{f}'
    if os.path.exists(path):
        process_file(path)
    else:
        print(f"文件不存在: {path}")

print("完成!")
