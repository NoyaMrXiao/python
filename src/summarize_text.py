"""
長文本總結 Agent
支持將長文本分塊，對每個塊進行總結，最後生成整體總結
支持異步並發處理和更大的文本塊
"""
import os
import sys
from typing import List, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 處理導入路徑
try:
    from .chat_completion import chat_completion_simple
except ImportError:
    # 如果相對導入失敗，嘗試絕對導入
    sys.path.insert(0, str(Path(__file__).parent))
    from chat_completion import chat_completion_simple


def split_text_into_chunks(
    text: str,
    chunk_size: int = 100000,  # GPT-4o 支持 128k tokens，约等于 100k-150k 字符（中文/英文混合）
    chunk_overlap: int = 300  # 相应增大重叠部分以保持上下文连贯性
) -> List[str]:
    """
    將長文本分塊
    
    參數:
        text (str): 要分塊的文本
        chunk_size (int): 每塊的最大字符數，默認為 100000（充分利用 GPT-4o 的 128k tokens 上下文）
        chunk_overlap (int): 塊之間的重疊字符數，默認為 5000
    
    返回:
        List[str]: 文本塊列表
    
    示例:
        >>> text = "很長的文本..."
        >>> chunks = split_text_into_chunks(text, chunk_size=1000)
        >>> print(f"分成 {len(chunks)} 塊")
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        # 計算當前塊的結束位置
        end = min(start + chunk_size, text_length)
        
        # 如果不是最後一塊，嘗試在句號、換行符等位置切斷
        if end < text_length:
            # 尋找合適的分割點（優先選擇句號、問號、感嘆號、換行符）
            for separator in ['。\n', '。 ', '\n\n', '。', '！', '？', '\n']:
                last_sep = text.rfind(separator, start, end)
                if last_sep != -1:
                    end = last_sep + len(separator)
                    break
        
        # 提取當前塊
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 計算下一個塊的起始位置（考慮重疊）
        start = max(end - chunk_overlap, start + 1)
    
    return chunks


def summarize_chunk(
    chunk: str,
    chunk_index: int,
    total_chunks: int,
    api_key: str,
    model: str = "chatgpt-4o-latest",
    language: str = "中文"
) -> str:
    """
    總結單個文本塊
    
    參數:
        chunk (str): 要總結的文本塊
        chunk_index (int): 當前塊的索引（從 1 開始）
        total_chunks (int): 總塊數
        api_key (str): API 密鑰
        model (str): 模型名稱
        language (str): 總結使用的語言，默認為 "中文"
    
    返回:
        str: 該塊的總結
    """
    system_prompt = f"""你是一個專業的文本總結助手。你的任務是對給定的文本進行簡潔、準確的總結。
要求：
1. 提取文本的核心要點和關鍵信息
2. 保持邏輯清晰，結構完整
3. 使用{language}進行總結
4. 總結長度應該適中，既不能遺漏重要信息，也不能過於冗長
5. 如果文本涉及特定領域（如技術、科學、文學等），請保持專業性"""
    
    prompt = f"""請總結以下文本（第 {chunk_index}/{total_chunks} 塊）：

{chunk}

請提供一個清晰、簡潔的總結，突出核心要點和關鍵信息。"""
    
    try:
        summary = chat_completion_simple(
            prompt=prompt,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=0.3,  # 較低的溫度以保證總結的一致性和準確性
            max_tokens=8000  # 增大输出 token 限制，充分利用 GPT-4o 的能力
        )
        return summary
    except Exception as e:
        print(f"⚠️ 總結第 {chunk_index} 塊時發生錯誤: {e}")
        return f"[總結失敗: {str(e)}]"


def summarize_text(
    text: str,
    api_key: Optional[str] = None,
    model: str = "chatgpt-4o-latest",
    chunk_size: int = 100000,  # GPT-4o 支持 128k tokens，约等于 100k-150k 字符
    chunk_overlap: int = 300,  # 相应增大重叠以保持上下文连贯性
    language: str = "中文",
    show_progress: bool = True,
    enable_async: bool = True,
    max_workers: int = 5  # 并发总结的线程数
) -> str:
    """
    總結長文本的主函數
    
    參數:
        text (str): 要總結的長文本
        api_key (str, optional): API 密鑰，如果為 None 則從環境變量讀取
        model (str): 模型名稱，默認為 "chatgpt-4o-latest"
        chunk_size (int): 每塊的最大字符數，默認為 100000（充分利用 GPT-4o 的 128k tokens 上下文）
        chunk_overlap (int): 塊之間的重疊字符數，默認為 5000
        language (str): 總結使用的語言，默認為 "中文"
        show_progress (bool): 是否顯示進度，默認為 True
        enable_async (bool): 是否啟用異步並發總結，默認為 True
        max_workers (int): 並發總結的最大線程數，默認為 5
    
    返回:
        str: 最終的文本總結
    
    示例:
        >>> long_text = "很長的文本內容..."
        >>> summary = summarize_text(long_text, api_key="your-api-key")
        >>> print(summary)
    """
    # 獲取 API key
    if api_key is None:
        api_key = os.getenv("API_KEY_302_AI") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("請提供 API 密鑰或設置環境變量 API_KEY_302_AI 或 OPENAI_API_KEY")
    
    if not text or not text.strip():
        raise ValueError("文本不能為空")
    
    # 步驟 1: 將文本分塊
    if show_progress:
        print(f"📝 正在將文本分塊（塊大小: {chunk_size}, 重疊: {chunk_overlap}）...")
    
    chunks = split_text_into_chunks(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    if not chunks:
        raise ValueError("文本分塊失敗，未生成任何塊")
    
    total_chunks = len(chunks)
    if show_progress:
        print(f"✓ 文本已分成 {total_chunks} 塊\n")
    
    # 如果只有一塊，直接總結
    if total_chunks == 1:
        if show_progress:
            print("📊 文本較短，直接進行總結...")
        return summarize_chunk(
            chunks[0],
            chunk_index=1,
            total_chunks=1,
            api_key=api_key,
            model=model,
            language=language
        )
    
    # 步驟 2: 對每個塊進行總結（支持並發）
    if show_progress:
        if enable_async:
            print(f"📋 開始並發總結各個文本塊（最大 {max_workers} 個線程）...\n")
        else:
            print(f"📋 開始總結各個文本塊...\n")
    
    chunk_summaries = []
    
    if enable_async and total_chunks > 1:
        # 使用線程池並發總結
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {}
            
            for i, chunk in enumerate(chunks, start=1):
                future = executor.submit(
                    summarize_chunk,
                    chunk,
                    chunk_index=i,
                    total_chunks=total_chunks,
                    api_key=api_key,
                    model=model,
                    language=language
                )
                future_to_chunk[future] = i
            
            # 收集結果（按順序）
            completed = 0
            results_dict = {}  # 使用字典保存結果，以保持順序
            
            for future in as_completed(future_to_chunk):
                chunk_idx = future_to_chunk[future]
                try:
                    summary = future.result()
                    results_dict[chunk_idx] = summary
                    completed += 1
                    
                    if show_progress:
                        print(f"  ✓ 完成第 {chunk_idx}/{total_chunks} 塊 ({completed}/{total_chunks})")
                except Exception as e:
                    print(f"  ⚠️ 總結第 {chunk_idx} 塊時發生錯誤: {e}")
                    results_dict[chunk_idx] = f"[總結失敗: {str(e)}]"
            
            # 按順序組裝結果
            chunk_summaries = [results_dict[i] for i in range(1, total_chunks + 1) if i in results_dict]
    else:
        # 順序處理
        for i, chunk in enumerate(chunks, start=1):
            if show_progress:
                print(f"  處理第 {i}/{total_chunks} 塊...", end=" ", flush=True)
            
            summary = summarize_chunk(
                chunk,
                chunk_index=i,
                total_chunks=total_chunks,
                api_key=api_key,
                model=model,
                language=language
            )
            
            chunk_summaries.append(summary)
            
            if show_progress:
                print("✓")
    
    # 步驟 3: 合併所有塊的總結，生成最終總結
    if show_progress:
        print(f"\n📑 正在生成最終總結...")
    
    # 合併所有塊的總結
    combined_summaries = "\n\n".join([
        f"第 {i+1} 塊總結：\n{summary}"
        for i, summary in enumerate(chunk_summaries)
    ])
    
    system_prompt = f"""你是一個專業的文本總結助手。你的任務是根據多個文本塊的總結，生成一個完整、連貫的整體總結。
要求：
1. 整合所有塊的總結，形成一個邏輯清晰的整體總結
2. 消除重複信息，突出核心要點
3. 保持總結的完整性和連貫性
4. 使用{language}進行總結
5. 確保總結能夠全面反映原文的核心內容和主要觀點"""
    
    final_prompt = f"""以下是對長文本各個部分的總結：

{combined_summaries}

請根據以上各個部分的總結，生成一個完整、連貫的整體總結。要求：
1. 整合所有關鍵信息，形成邏輯清晰的總結
2. 消除重複內容
3. 突出核心觀點和主要論述
4. 保持結構完整，語言流暢"""
    
    try:
        # 充分利用 GPT-4o 的 128k tokens 上下文，增大 max_tokens 输出限制
        final_summary = chat_completion_simple(
            prompt=final_prompt,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=16000  # 增大以充分利用 GPT-4o 的能力生成更详细的总结
        )
        
        if show_progress:
            print("✓ 總結完成！\n")
        
        return final_summary
    except Exception as e:
        raise Exception(f"生成最終總結時發生錯誤: {str(e)}")


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("長文本總結 Agent")
    print("=" * 60)
    
    # 從環境變量獲取 API key
    api_key = os.getenv("API_KEY_302_AI") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("\n❌ 錯誤: 請設置環境變量 API_KEY_302_AI 或 OPENAI_API_KEY")
        print("\n使用方法:")
        print("  export API_KEY_302_AI='your-api-key'")
        print("  python summarize_text.py <文本文件路徑>")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("\n使用方法:")
        print("  python summarize_text.py <文本文件路徑> [塊大小] [模型名稱]")
        print("\n示例:")
        print("  python summarize_text.py document.txt")
        print("  python summarize_text.py document.txt 2000 chatgpt-4o-latest")
        sys.exit(1)
    
    file_path = sys.argv[1]
    chunk_size = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    model = sys.argv[3] if len(sys.argv) > 3 else "chatgpt-4o-latest"
    
    try:
        # 讀取文本文件
        print(f"\n📖 讀取文件: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        if not text.strip():
            print("❌ 錯誤: 文件為空")
            sys.exit(1)
        
        print(f"✓ 文件長度: {len(text)} 字符\n")
        
        # 執行總結
        summary = summarize_text(
            text=text,
            api_key=api_key,
            model=model,
            chunk_size=chunk_size,
            show_progress=True
        )
        
        print("=" * 60)
        print("最終總結:")
        print("=" * 60)
        print(summary)
        print("\n" + "=" * 60)
        
        # 可選：保存總結到文件
        output_file = file_path.rsplit('.', 1)[0] + "_summary.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("長文本總結\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"原文文件: {file_path}\n")
            f.write(f"原文長度: {len(text)} 字符\n\n")
            f.write("=" * 60 + "\n")
            f.write("總結:\n")
            f.write("=" * 60 + "\n\n")
            f.write(summary)
        
        print(f"\n💾 總結已保存到: {output_file}")
        
    except FileNotFoundError:
        print(f"\n❌ 錯誤: 找不到文件 '{file_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

