"""
将Python脚本中的中文转换为繁体中文
"""
from zhconv import convert
import re

def convert_strings_in_file(file_path):
    """将文件中的中文字符串转换为繁体中文"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 匹配字符串中的中文（单引号、双引号、三引号）
    def replace_chinese(match):
        quote = match.group(1)  # 引号类型
        string_content = match.group(2)
        # 转换其中的中文
        traditional = convert(string_content, 'zh-tw')
        return f"{quote}{traditional}{quote}"
    
    # 匹配字符串：'...', "...", '''...''', """..."""
    patterns = [
        (r"(')([^']*[\u4e00-\u9fff]+[^']*)(')", "'"),  # 单引号
        (r'(")([^"]*[\u4e00-\u9fff]+[^"]*)(")', '"'),  # 双引号
        (r"(''')([\s\S]*?[\u4e00-\u9fff]+[\s\S]*?)(''')", "'''"),  # 三单引号
        (r'(""")([\s\S]*?[\u4e00-\u9fff]+[\s\S]*?)(""")', '"""'),  # 三双引号
    ]
    
    # 转换所有匹配的中文字符串
    for pattern, quote_type in patterns:
        def replacer(match):
            full_match = match.group(0)
            quote = match.group(1)
            string_content = match.group(2)
            if '\u4e00' <= string_content and string_content <= '\u9fff' or any('\u4e00' <= c <= '\u9fff' for c in string_content):
                traditional = convert(string_content, 'zh-tw')
                return quote + traditional + quote
            return full_match
        
        content = re.sub(pattern, replacer, content, flags=re.MULTILINE | re.DOTALL)
    
    # 直接转换注释中的中文（简单处理）
    lines = content.split('\n')
    converted_lines = []
    for line in lines:
        if '#' in line:
            # 分离代码和注释
            code_part = line.split('#')[0]
            comment_part = '#' + '#'.join(line.split('#')[1:]) if '#' in line else ''
            if comment_part and any('\u4e00' <= c <= '\u9fff' for c in comment_part):
                comment_part = convert(comment_part, 'zh-tw')
            converted_lines.append(code_part + comment_part)
        else:
            converted_lines.append(line)
    
    content = '\n'.join(converted_lines)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"已转换: {file_path}")

if __name__ == "__main__":
    files_to_convert = [
        'generate_flowchart.py',
        'generate_pdf.py',
    ]
    
    for file_path in files_to_convert:
        try:
            convert_strings_in_file(file_path)
        except Exception as e:
            print(f"转换 {file_path} 时出错: {e}")

