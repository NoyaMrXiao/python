"""
使用googletrans翻譯文本
支持多種語言的自動翻譯
"""
from googletrans import Translator, LANGUAGES
from typing import Optional, Union, List, Dict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


# 創建全局翻譯器實例
_translator = None


def get_translator():
    """獲取翻譯器實例（單例模式）"""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def translate_text(
    text: Union[str, List[str]],
    dest: str = 'en',
    src: Optional[str] = None,
    retry_count: int = 3,
    retry_delay: float = 1.0
) -> Union[Dict, List[Dict]]:
    """
    翻譯文本到目標語言
    
    參數:
        text (str | List[str]): 要翻譯的文本或文本列表
        dest (str): 目標語言代碼（默認 'en'），如 'zh-cn', 'ja', 'ko' 等
        src (str, optional): 源語言代碼，None為自動檢測
        retry_count (int): 重試次數（網絡問題時）
        retry_delay (float): 重試延遲（秒）
    
    返回:
        dict 或 List[dict]: 翻譯結果
        單個文本返回: {'text': '翻譯後的文本', 'src': '源語言', 'dest': '目標語言', 'pronunciation': '發音'}
        多個文本返回: 上述字典的列表
    """
    translator = get_translator()
    
    # 驗證目標語言
    if dest not in LANGUAGES:
        raise ValueError(f"不支持的目標語言: {dest}。支持的語言: {list(LANGUAGES.keys())}")
    
    # 處理重試邏輯
    last_exception = None
    for attempt in range(retry_count):
        try:
            if isinstance(text, list):
                # 批量翻譯
                result = translator.translate(text, dest=dest, src=src)
                return [
                    {
                        'text': r.text,
                        'src': r.src,
                        'dest': r.dest,
                        'pronunciation': getattr(r, 'pronunciation', None),
                        'original': original
                    }
                    for r, original in zip(result, text)
                ]
            else:
                # 單個文本翻譯
                result = translator.translate(text, dest=dest, src=src)
                return {
                    'text': result.text,
                    'src': result.src,
                    'dest': result.dest,
                    'pronunciation': getattr(result, 'pronunciation', None),
                    'original': text
                }
        
        except Exception as e:
            last_exception = e
            if attempt < retry_count - 1:
                print(f"⚠ 翻譯失敗，正在重試 ({attempt + 1}/{retry_count})...")
                time.sleep(retry_delay)
            else:
                raise Exception(f"翻譯失敗，已重試 {retry_count} 次: {str(e)}")
    
    if last_exception:
        raise last_exception


def translate_text_simple(text: str, dest: str = 'en') -> str:
    """
    簡單版本：只返回翻譯後的文本
    
    參數:
        text (str): 要翻譯的文本
        dest (str): 目標語言代碼
    
    返回:
        str: 翻譯後的文本
    """
    result = translate_text(text, dest=dest)
    return result['text']


def detect_language(text: str) -> Dict[str, Union[str, float]]:
    """
    檢測文本的語言
    
    參數:
        text (str): 要檢測的文本
    
    返回:
        dict: {'language': '語言代碼', 'confidence': '置信度'}
    """
    translator = get_translator()
    try:
        result = translator.detect(text)
        return {
            'language': result.lang,
            'confidence': result.confidence if hasattr(result, 'confidence') else None
        }
    except Exception as e:
        raise Exception(f"語言檢測失敗: {str(e)}")


def get_supported_languages() -> Dict[str, str]:
    """
    獲取所有支持的語言
    
    返回:
        dict: {語言代碼: 語言名稱}
    """
    return LANGUAGES.copy()


def translate_file(
    input_file: str,
    output_file: Optional[str] = None,
    dest: str = 'en',
    src: Optional[str] = None,
    encoding: str = 'utf-8'
) -> str:
    """
    翻譯文件內容
    
    參數:
        input_file (str): 輸入文件路徑
        output_file (str, optional): 輸出文件路徑，默認為輸入文件名_translated.txt
        dest (str): 目標語言代碼
        src (str, optional): 源語言代碼
        encoding (str): 文件編碼
    
    返回:
        str: 輸出文件路徑
    """
    import os
    from pathlib import Path
    
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"文件不存在: {input_file}")
    
    # 讀取文件
    with open(input_file, 'r', encoding=encoding) as f:
        content = f.read()
    
    # 按行翻譯（處理較大文件）
    lines = content.split('\n')
    translated_lines = []
    
    print(f"正在翻譯文件: {input_file}")
    print(f"總共 {len(lines)} 行")
    
    for i, line in enumerate(lines, 1):
        if line.strip():  # 跳過空行
            try:
                result = translate_text(line, dest=dest, src=src)
                translated_lines.append(result['text'])
                if i % 10 == 0:
                    print(f"進度: {i}/{len(lines)}")
            except Exception as e:
                print(f"⚠ 第 {i} 行翻譯失敗: {e}")
                translated_lines.append(line)  # 保留原文
        else:
            translated_lines.append('')
    
    # 確定輸出文件路徑
    if output_file is None:
        input_path = Path(input_file)
        output_file = str(input_path.parent / f"{input_path.stem}_translated{input_path.suffix}")
    
    # 寫入文件
    with open(output_file, 'w', encoding=encoding) as f:
        f.write('\n'.join(translated_lines))
    
    print(f"✓ 翻譯完成，已保存到: {output_file}")
    return output_file


def translate_list(
    texts: List[str],
    dest: str = 'en',
    src: Optional[str] = None,
    batch_size: int = 15
) -> List[str]:
    """
    批量翻譯文本列表
    
    參數:
        texts (List[str]): 要翻譯的文本列表
        dest (str): 目標語言代碼
        src (str, optional): 源語言代碼
        batch_size (int): 批次大小（googletrans可能有字符限制）
    
    返回:
        List[str]: 翻譯後的文本列表
    """
    if not texts:
        return []
    
    # 如果列表較小，直接翻譯
    if len(texts) <= batch_size:
        result = translate_text(texts, dest=dest, src=src)
        # 確保正確提取翻譯文本
        translated = []
        for r in result:
            if isinstance(r, dict):
                translated.append(r.get('text', ''))
            elif hasattr(r, 'text'):
                translated.append(r.text)
            else:
                translated.append(str(r))
        return translated
    
    # 分批處理
    translated_texts = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_result = translate_text(batch, dest=dest, src=src)
        # 確保正確提取翻譯文本
        for r in batch_result:
            if isinstance(r, dict):
                translated_texts.append(r.get('text', ''))
            elif hasattr(r, 'text'):
                translated_texts.append(r.text)
            else:
                translated_texts.append(str(r))
        print(f"進度: {min(i + batch_size, len(texts))}/{len(texts)}")
    
    return translated_texts


def translate_list_parallel(
    texts: List[str],
    dest: str = 'en',
    src: Optional[str] = None,
    batch_size: int = 15,
    max_workers: int = 5
) -> List[str]:
    """
    並行批量翻譯文本列表
    
    參數:
        texts (List[str]): 要翻譯的文本列表
        dest (str): 目標語言代碼
        src (str, optional): 源語言代碼
        batch_size (int): 每批次的文本數量
        max_workers (int): 最大並發線程數
    
    返回:
        List[str]: 翻譯後的文本列表（順序與輸入一致）
    """
    if not texts:
        return []
    
    # 如果列表較小，直接翻譯
    if len(texts) <= batch_size * max_workers:
        return translate_list(texts, dest=dest, src=src, batch_size=batch_size)
    
    # 將文本分成多個批次
    batches = []
    for i in range(0, len(texts), batch_size):
        batches.append((i, texts[i:i + batch_size]))
    
    # 並行翻譯
    translated_texts = [None] * len(texts)  # 預分配列表以保持順序
    
    def translate_batch(batch_idx, batch_texts):
        """翻譯單個批次"""
        try:
            result = translate_text(batch_texts, dest=dest, src=src)
            # 確保正確提取翻譯文本
            translated_batch = []
            for r in result:
                if isinstance(r, dict):
                    translated_batch.append(r.get('text', ''))
                elif hasattr(r, 'text'):
                    translated_batch.append(r.text)
                else:
                    translated_batch.append(str(r))
            print(f"✓ 批次 {batch_idx} 翻譯完成，共 {len(translated_batch)} 條")
            return batch_idx, translated_batch
        except Exception as e:
            print(f"⚠ 批次 {batch_idx} 翻譯失敗: {e}")
            import traceback
            traceback.print_exc()
            return batch_idx, batch_texts  # 返回原文作為後備
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有批次任務
        future_to_batch = {
            executor.submit(translate_batch, batch_idx, batch_texts): batch_idx 
            for batch_idx, batch_texts in batches
        }
        
        # 收集結果
        completed = 0
        for future in as_completed(future_to_batch):
            try:
                batch_idx, translated_batch = future.result()
                start_idx = batch_idx
                for i, translated_text in enumerate(translated_batch):
                    if start_idx + i < len(translated_texts):
                        translated_texts[start_idx + i] = translated_text
                completed += 1
                print(f"翻譯進度: {completed}/{len(batches)} 批次")
            except Exception as e:
                print(f"⚠ 處理批次結果時出錯: {e}")
    
    # 確保所有文本都已翻譯（如果有失敗的，使用原文）
    for i, text in enumerate(translated_texts):
        if text is None:
            translated_texts[i] = texts[i]
    
    return translated_texts


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Google Translate 文本翻譯工具")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\n使用方法:")
        print("  翻譯文本: python translate_text.py '要翻譯的文本' [目標語言]")
        print("  翻譯文件: python translate_text.py --file <文件路徑> [目標語言]")
        print("  檢測語言: python translate_text.py --detect '文本'")
        print("  列出語言: python translate_text.py --languages")
        print("\n語言代碼示例: en(英語), zh-cn(簡體中文), zh-tw(繁體中文), ja(日語), ko(韓語)")
        sys.exit(1)
    
    try:
        if sys.argv[1] == '--languages':
            # 列出所有支持的語言
            languages = get_supported_languages()
            print("\n支持的語言:")
            print("-" * 60)
            for code, name in sorted(languages.items()):
                print(f"{code:8} - {name}")
        
        elif sys.argv[1] == '--detect':
            # 檢測語言
            if len(sys.argv) < 3:
                print("錯誤: 需要提供要檢測的文本")
                sys.exit(1)
            text = sys.argv[2]
            result = detect_language(text)
            print(f"\n檢測結果:")
            print(f"語言: {result['language']} ({LANGUAGES.get(result['language'], 'Unknown')})")
            if result['confidence']:
                print(f"置信度: {result['confidence']:.2%}")
        
        elif sys.argv[1] == '--file':
            # 翻譯文件
            if len(sys.argv) < 3:
                print("錯誤: 需要提供文件路徑")
                sys.exit(1)
            file_path = sys.argv[2]
            dest_lang = sys.argv[3] if len(sys.argv) > 3 else 'en'
            translate_file(file_path, dest=dest_lang)
        
        else:
            # 翻譯文本
            text = sys.argv[1]
            dest_lang = sys.argv[2] if len(sys.argv) > 2 else 'en'
            
            print(f"\n原文: {text}")
            print(f"目標語言: {dest_lang}")
            print("-" * 60)
            
            result = translate_text(text, dest=dest_lang)
            print(f"翻譯: {result['text']}")
            print(f"檢測到的源語言: {result['src']} ({LANGUAGES.get(result['src'], 'Unknown')})")
            if result.get('pronunciation'):
                print(f"發音: {result['pronunciation']}")
    
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()

