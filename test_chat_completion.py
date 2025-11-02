"""
全面测试 chat_completion.py 的所有功能
"""
import os
import sys
from pathlib import Path

# 加载 .env 文件
def load_env_file():
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# 加载环境变量
load_env_file()

# 导入 chat_completion 模块
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from chat_completion import chat_completion, chat_completion_simple, chat_completion_stream

# 获取 API key
api_key = os.getenv("API_KEY_302_AI") or os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ 错误: 未找到 API key")
    print("请在 .env 文件中设置 API_KEY_302_AI 或 OPENAI_API_KEY")
    sys.exit(1)

print("=" * 70)
print("chat_completion.py 全面测试")
print("=" * 70)
print(f"API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
print(f"API Base URL: https://api.302.ai")
print(f"默认模型: chatgpt-4o-latest")
print("=" * 70)

# 测试 1: chat_completion_simple (简单版本)
print("\n[测试 1] chat_completion_simple - 简单版本测试")
print("-" * 70)
try:
    prompt1 = "用一句话介绍 Python 编程语言的特点。"
    print(f"请求: {prompt1}")
    
    response1 = chat_completion_simple(
        prompt=prompt1,
        api_key=api_key,
        model="chatgpt-4o-latest",
        timeout=30
    )
    
    print(f"✓ 成功")
    print(f"回复: {response1}")
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试 2: chat_completion (完整版本)
print("\n[测试 2] chat_completion - 完整版本测试")
print("-" * 70)
try:
    messages = [
        {"role": "system", "content": "你是一个有帮助的AI助手。"},
        {"role": "user", "content": "什么是机器学习？请用一句话回答。"}
    ]
    print(f"请求消息数: {len(messages)}")
    
    response2 = chat_completion(
        messages=messages,
        api_key=api_key,
        model="chatgpt-4o-latest",
        temperature=0.7,
        timeout=30
    )
    
    print(f"✓ 成功")
    print(f"响应结构: {list(response2.keys())}")
    
    if "choices" in response2 and len(response2["choices"]) > 0:
        content = response2["choices"][0]["message"]["content"]
        print(f"回复内容: {content}")
        
    if "usage" in response2:
        usage = response2["usage"]
        print(f"Token 使用: prompt_tokens={usage.get('prompt_tokens', 0)}, "
              f"completion_tokens={usage.get('completion_tokens', 0)}, "
              f"total_tokens={usage.get('total_tokens', 0)}")
except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 3: chat_completion_simple with system prompt
print("\n[测试 3] chat_completion_simple - 带系统提示词测试")
print("-" * 70)
try:
    prompt3 = "解释一下什么是 API"
    system_prompt = "你是一个技术专家，请用通俗易懂的语言解释技术概念。"
    print(f"系统提示词: {system_prompt}")
    print(f"用户请求: {prompt3}")
    
    response3 = chat_completion_simple(
        prompt=prompt3,
        api_key=api_key,
        model="chatgpt-4o-latest",
        system_prompt=system_prompt,
        timeout=30
    )
    
    print(f"✓ 成功")
    print(f"回复: {response3[:200]}..." if len(response3) > 200 else f"回复: {response3}")
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试 4: chat_completion_stream (流式调用)
print("\n[测试 4] chat_completion_stream - 流式调用测试")
print("-" * 70)
try:
    messages_stream = [
        {"role": "user", "content": "请用三句话介绍 Flask Web 框架。"}
    ]
    print(f"请求: {messages_stream[0]['content']}")
    print("流式响应:")
    print("-" * 70)
    
    full_response = ""
    chunk_count = 0
    for chunk in chat_completion_stream(
        messages=messages_stream,
        api_key=api_key,
        model="chatgpt-4o-latest",
        timeout=30
    ):
        print(chunk, end="", flush=True)
        full_response += chunk
        chunk_count += 1
    
    print("\n" + "-" * 70)
    print(f"✓ 成功 - 收到 {chunk_count} 个数据块")
    print(f"完整回复长度: {len(full_response)} 字符")
except Exception as e:
    print(f"\n❌ 失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 5: 参数测试 (temperature, max_tokens)
print("\n[测试 5] chat_completion - 自定义参数测试")
print("-" * 70)
try:
    messages_param = [
        {"role": "user", "content": "用一句话描述人工智能。"}
    ]
    print(f"请求: {messages_param[0]['content']}")
    print(f"参数: temperature=0.1 (低随机性), max_tokens=50")
    
    response5 = chat_completion(
        messages=messages_param,
        api_key=api_key,
        model="chatgpt-4o-latest",
        temperature=0.1,
        max_tokens=50,
        timeout=30
    )
    
    content5 = response5["choices"][0]["message"]["content"]
    print(f"✓ 成功")
    print(f"回复: {content5}")
    print(f"回复长度: {len(content5)} 字符")
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "=" * 70)
print("测试完成！")
print("=" * 70)

