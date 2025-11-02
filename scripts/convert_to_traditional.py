"""
将简体中文文档转换为繁体中文
"""
from zhconv import convert
import os

def convert_file_to_traditional(file_path):
    """将文件内容转换为繁体中文"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 转换为繁体中文
    traditional_content = convert(content, 'zh-tw')
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(traditional_content)
    
    print(f"已转换: {file_path}")

if __name__ == "__main__":
    # 需要转换的文件列表
    files_to_convert = [
        '需求文档.md',
        'user_flow.mmd',
        'flowchart_viewer.html',
        'README.md',
    ]
    
    for file_path in files_to_convert:
        if os.path.exists(file_path):
            convert_file_to_traditional(file_path)
        else:
            print(f"跳过不存在的文件: {file_path}")

