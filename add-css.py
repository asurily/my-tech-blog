#!/usr/bin/env python3
"""为 ASCII 图添加样式"""

import os

ascii_style = '''.ascii-art{background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:16px;overflow-x:auto;font-family:Consolas,Monaco,"Courier New",monospace;font-size:0.85em;line-height:1.4;color:#495057;white-space:pre;}'''

files = [
    'openclaw-gateway.html',
    'openclaw-channel.html', 
    'openclaw-skills.html',
    'openclaw-memory.html'
]

for fname in files:
    path = f'/root/.openclaw/workspace/my-tech-blog/{fname}'
    if not os.path.exists(path):
        continue
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已有 ascii-art 样式
    if 'ascii-art' in content and '.ascii-art{' in content:
        print(f"{fname}: 已有样式")
        continue
    
    # 在 </style> 前添加样式
    content = content.replace('</style>', ascii_style + '</style>')
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"{fname}: 已添加样式")

print("完成!")
