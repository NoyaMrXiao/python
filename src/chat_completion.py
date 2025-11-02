"""
調用大語言模型 API（302.ai OpenAI 兼容接口）
支持 ChatGPT-4o-latest 模型
"""
import requests
from typing import Optional, List, Dict, Union, Any
import json
import time


def chat_completion(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str = "chatgpt-4o-latest",
    base_url: str = "https://api.302.ai",
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    n: Optional[int] = None,
    stream: Optional[bool] = None,
    stop: Optional[Union[str, List[str]]] = None,
    max_tokens: Optional[int] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logit_bias: Optional[Dict[int, float]] = None,
    user: Optional[str] = None,
    timeout: int = 60,
    retry_count: int = 3,
    retry_delay: float = 1.0
) -> Dict[str, Any]:
    """
    調用大語言模型 API 進行對話完成
    
    參數:
        messages (List[Dict[str, str]]): 對話消息列表，每個消息包含 'role' 和 'content'
            例如: [{"role": "user", "content": "你好"}]
        api_key (str): API 密鑰（Bearer token）
        model (str): 模型名稱，默認為 "chatgpt-4o-latest"
        base_url (str): API 基礎 URL，默認為 "https://api.302.ai"
        temperature (float, optional): 採樣溫度（0-2），越高越隨機
        top_p (float, optional): 核採樣參數（0-1）
        n (int, optional): 生成多少個選擇
        stream (bool, optional): 是否流式返回
        stop (str | List[str], optional): 停止序列
        max_tokens (int, optional): 最大生成 token 數
        presence_penalty (float, optional): 存在懲罰（-2.0 到 2.0）
        frequency_penalty (float, optional): 頻率懲罰（-2.0 到 2.0）
        logit_bias (Dict[int, float], optional): token 偏置
        user (str, optional): 用戶標識符
        timeout (int): 請求超時時間（秒），默認為 60
        retry_count (int): 重試次數（網絡問題時），默認為 3
        retry_delay (float): 重試延遲（秒），默認為 1.0
    
    返回:
        dict: API 響應，包含以下字段：
            - id: 響應 ID
            - object: 對象類型
            - created: 創建時間戳
            - choices: 選擇列表，每個包含 message, finish_reason 等
            - usage: token 使用情況（prompt_tokens, completion_tokens, total_tokens）
    
    示例:
        >>> messages = [{"role": "user", "content": "你好，請介紹一下你自己"}]
        >>> response = chat_completion(messages, api_key="your-api-key")
        >>> print(response["choices"][0]["message"]["content"])
    """
    # 構建請求 URL
    url = f"{base_url}/chat/completions"
    
    # 構建請求頭
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 構建請求體
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages
    }
    
    # 添加可選參數
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if n is not None:
        payload["n"] = n
    if stream is not None:
        payload["stream"] = stream
    if stop is not None:
        payload["stop"] = stop
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if logit_bias is not None:
        payload["logit_bias"] = logit_bias
    if user is not None:
        payload["user"] = user
    
    # 驗證 messages 格式
    if not messages or not isinstance(messages, list):
        raise ValueError("messages 必須是非空列表")
    
    for msg in messages:
        if not isinstance(msg, dict):
            raise ValueError("messages 中的每個元素必須是字典")
        if "role" not in msg or "content" not in msg:
            raise ValueError("messages 中的每個字典必須包含 'role' 和 'content' 字段")
    
    # 重試邏輯
    last_exception = None
    for attempt in range(retry_count):
        try:
            # 發送請求
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            # 檢查 HTTP 狀態碼
            response.raise_for_status()
            
            # 解析 JSON 響應
            result = response.json()
            return result
            
        except requests.exceptions.Timeout:
            last_exception = Exception(f"請求超時（超過 {timeout} 秒）")
            if attempt < retry_count - 1:
                print(f"⚠ 請求超時，正在重試 ({attempt + 1}/{retry_count})...")
                time.sleep(retry_delay)
            else:
                raise last_exception
        
        except requests.exceptions.HTTPError as e:
            # HTTP 錯誤（如 401, 403, 404 等）通常不需要重試
            error_msg = f"HTTP 錯誤: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if "error" in error_detail:
                    error_msg += f" - {error_detail['error']}"
            except:
                error_msg += f" - {e.response.text}"
            raise Exception(error_msg)
        
        except requests.exceptions.RequestException as e:
            last_exception = e
            if attempt < retry_count - 1:
                print(f"⚠ 請求失敗，正在重試 ({attempt + 1}/{retry_count})...")
                time.sleep(retry_delay)
            else:
                raise Exception(f"請求失敗，已重試 {retry_count} 次: {str(e)}")
        
        except json.JSONDecodeError as e:
            raise Exception(f"響應 JSON 解析失敗: {str(e)}")
    
    if last_exception:
        raise last_exception


def chat_completion_simple(
    prompt: str,
    api_key: str,
    model: str = "chatgpt-4o-latest",
    system_prompt: Optional[str] = None,
    **kwargs
) -> str:
    """
    簡單版本：只返回模型生成的文本內容
    
    參數:
        prompt (str): 用戶提示
        api_key (str): API 密鑰
        model (str): 模型名稱
        system_prompt (str, optional): 系統提示詞
        **kwargs: 其他傳遞給 chat_completion 的參數
    
    返回:
        str: 模型生成的回覆文本
    
    示例:
        >>> response = chat_completion_simple("你好", api_key="your-api-key")
        >>> print(response)
    """
    messages = []
    
    # 添加系統提示（如果提供）
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # 添加用戶提示
    messages.append({"role": "user", "content": prompt})
    
    # 調用 API
    response = chat_completion(messages, api_key=api_key, model=model, **kwargs)
    
    # 提取回覆內容
    if "choices" in response and len(response["choices"]) > 0:
        return response["choices"][0]["message"]["content"]
    else:
        raise Exception("API 響應中沒有找到回覆內容")


def chat_completion_stream(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str = "chatgpt-4o-latest",
    base_url: str = "https://api.302.ai",
    **kwargs
) -> Any:
    """
    流式調用大語言模型 API（返回生成器）
    
    參數:
        messages (List[Dict[str, str]]): 對話消息列表
        api_key (str): API 密鑰
        model (str): 模型名稱
        base_url (str): API 基礎 URL
        **kwargs: 其他參數（不包括 stream，會自動設置為 True）
    
    返回:
        生成器: 逐步返回模型生成的內容
    
    示例:
        >>> messages = [{"role": "user", "content": "寫一首詩"}]
        >>> for chunk in chat_completion_stream(messages, api_key="your-api-key"):
        ...     print(chunk, end="", flush=True)
    """
    # 確保 stream 參數為 True
    kwargs["stream"] = True
    
    # 調用 API（注意：需要處理流式響應）
    # 這裡返回生成器，實際實現需要處理 SSE 格式
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": True
    }
    
    # 添加其他參數
    for key, value in kwargs.items():
        if key != "stream" and value is not None:
            payload[key] = value
    
    try:
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()
        
        # 解析 SSE 格式的流式響應
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # 移除 'data: ' 前綴
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        raise Exception(f"流式請求失敗: {str(e)}")


if __name__ == "__main__":
    import sys
    import os
    
    print("=" * 60)
    print("大語言模型 API 調用工具")
    print("=" * 60)
    
    # 從環境變量獲取 API key
    api_key = os.getenv("API_KEY_302_AI") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("\n❌ 錯誤: 請設置環境變量 API_KEY_302_AI 或 OPENAI_API_KEY")
        print("\n使用方法:")
        print("  export API_KEY_302_AI='your-api-key'")
        print("  python chat_completion.py '你的問題'")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("\n使用方法:")
        print("  python chat_completion.py '你的問題' [模型名稱]")
        print("\n示例:")
        print("  python chat_completion.py '你好，請介紹一下你自己'")
        print("  python chat_completion.py '寫一首關於春天的詩' chatgpt-4o-latest")
        sys.exit(1)
    
    prompt = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "chatgpt-4o-latest"
    
    try:
        print(f"\n問題: {prompt}")
        print(f"模型: {model}")
        print("-" * 60)
        
        # 使用簡單版本
        response = chat_completion_simple(prompt, api_key=api_key, model=model)
        
        print(f"\n回覆:\n{response}")
        print("\n" + "=" * 60)
        
        # 如果需要詳細信息，可以使用完整版本
        # messages = [{"role": "user", "content": prompt}]
        # response = chat_completion(messages, api_key=api_key, model=model)
        # print(f"\n完整響應:")
        # print(json.dumps(response, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()

