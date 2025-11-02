from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def main():
    # 1. 初始化浏览器
    driver = webdriver.Chrome()  # 确保已安装chromedriver
    driver.implicitly_wait(10)  # 设置隐式等待
    
    try:
        # 2. 打开 BBC 新闻搜索页
        driver.get("https://www.bbc.co.uk/search")
        
        # 3. 等待页面加载并找到搜索框（尝试多个可能的选择器）
        wait = WebDriverWait(driver, 10)
        
        # 尝试多种方式定位搜索框
        search_box = None
        selectors = [
            (By.ID, "search-input"),
            (By.CSS_SELECTOR, "input[type='search']"),
            (By.CSS_SELECTOR, "input[name='q']"),
            (By.CSS_SELECTOR, "input[placeholder*='Search']"),
            (By.CSS_SELECTOR, "#search-input"),
            (By.XPATH, "//input[@type='search']"),
            (By.XPATH, "//input[contains(@placeholder, 'Search')]"),
        ]
        
        for by, selector in selectors:
            try:
                search_box = wait.until(EC.presence_of_element_located((by, selector)))
                print(f"找到搜索框，使用选择器: {by}, {selector}")
                break
            except:
                continue
        
        if not search_box:
            print("无法找到搜索框，请检查页面结构")
            return
        
        # 输入关键词并搜索
        search_box.clear()
        search_box.send_keys("climate change")
        search_box.send_keys(Keys.RETURN)
        
        # 4. 等待搜索结果加载
        time.sleep(3)
        
        # 5. 获取新闻标题和链接（尝试多个可能的选择器）
        results = []
        result_selectors = [
            ".ssrcss-6arcww-PromoHeadline a",
            ".ssrcss-1f3bvyz-Stack a",
            "article a",
            "[data-testid='search-result'] a",
            ".promo-headline a",
        ]
        
        for selector in result_selectors:
            results = driver.find_elements(By.CSS_SELECTOR, selector)
            if results:
                print(f"找到 {len(results)} 条结果，使用选择器: {selector}")
                break
        
        if not results:
            print("未找到搜索结果，请检查选择器")
        else:
            for r in results[:5]:  # 取前5条
                title = r.text.strip()
                link = r.get_attribute("href")
                if title and link:
                    print(f"{title}\n{link}\n")
    
    except Exception as e:
        print(f"发生错误: {e}")
    
    finally:
        # 6. 关闭浏览器
        time.sleep(2)  # 等待一下以便查看结果
        driver.quit()


if __name__ == "__main__":
    main()
