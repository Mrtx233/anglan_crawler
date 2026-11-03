# ======================== 详情页链接采集（点击加载更多） ========================
#
# 用途: 从列表页采集所有产品详情页链接（标题 + URL）
#       适用于有"加载更多"按钮的页面
#
# 使用方式:
#   1. 修改 PAGES 列表（标题 + 链接）、XPATH_LINK 和 XPATH_LOAD_MORE
#   2. 运行脚本，自动打开浏览器点击加载按钮并提取链接
#
# 技术栈: Selenium + lxml，调用本地 Chrome
# 输出: XLSX（title, link）
# ========================================================================

import os
import time
from urllib.parse import urljoin, urlparse

import openpyxl
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from lxml import html

# ===== 配置：修改此处 =====
XPATH_LINK = ""  # 产品链接 XPath
XPATH_LOAD_MORE = ""  # "加载更多"按钮 XPath

PAGES = [
    # ("分类名称", "https://example.com/collections/xxx"),
]

# ======================== 路径配置 ========================
OUTPUT_DIR = r"/02crawler/output"

CLICK_PAUSE = 2        # 每次点击后等待秒数
MAX_NO_CHANGE = 3      # 连续几次点击无新内容则停止


# ======================== Selenium 初始化 ========================
def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # 使用本地代理
    options.add_argument("--proxy-server=http://127.0.0.1:7897")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: undefined})"
    )
    return driver


# ======================== 辅助函数 ========================
def resolve_url(href, page_url):
    """将相对 URL 转为绝对 URL"""
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(page_url, href)


def get_page_html(driver):
    """获取当前页面完整 DOM 并返回 lxml tree"""
    raw = driver.execute_script("return document.documentElement.outerHTML;")
    return html.fromstring(raw)


def collect_links(tree, page_url):
    """从页面中提取所有链接，去重后返回"""
    link_els = tree.xpath(XPATH_LINK) if XPATH_LINK else []
    links = []
    seen = set()
    for el in link_els:
        href = el.strip() if isinstance(el, str) else ""
        if not href and hasattr(el, "get"):
            href = el.get("href", "").strip()
        href = resolve_url(href, page_url)
        if href and href not in seen:
            seen.add(href)
            links.append(href)
    return links


def click_load_more(driver):
    """反复点击"加载更多"按钮直到消失或无新内容"""
    no_change_count = 0

    while no_change_count < MAX_NO_CHANGE:
        # 查找按钮
        try:
            tree = get_page_html(driver)
            btn_els = tree.xpath(XPATH_LOAD_MORE) if XPATH_LOAD_MORE else []
            if not btn_els:
                print("  按钮已消失，停止加载")
                break
        except Exception:
            break

        # 用 Selenium 定位按钮并点击
        try:
            btn = driver.find_element(By.XPATH, XPATH_LOAD_MORE)
        except NoSuchElementException:
            print("  按钮已消失，停止加载")
            break

        # 滚动到按钮位置
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        time.sleep(0.5)

        try:
            btn.click()
        except ElementClickInterceptedException:
            # 按钮被遮挡，尝试 JS 点击
            driver.execute_script("arguments[0].click();", btn)

        time.sleep(CLICK_PAUSE)

        # 检查是否有新内容加载
        new_tree = get_page_html(driver)
        new_btn_els = new_tree.xpath(XPATH_LOAD_MORE) if XPATH_LOAD_MORE else []
        if not new_btn_els:
            # 按钮消失说明加载完了
            break

        # 通过比较页面链接数量判断是否有新内容
        old_links = collect_links(tree, driver.current_url)
        new_links = collect_links(new_tree, driver.current_url)

        if len(new_links) > len(old_links):
            no_change_count = 0
            print(f"  点击加载更多... 当前 {len(new_links)} 条链接")
        else:
            no_change_count += 1
            print(f"  点击后无新内容 ({no_change_count}/{MAX_NO_CHANGE})")


# ======================== 保存结果 ========================
FIELD_NAMES = ["title", "link"]


def save_results(all_results, domain):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_domain = domain.replace("www.", "").replace(".", "_")
    output_xlsx = os.path.join(OUTPUT_DIR, f"{safe_domain}.xlsx")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = domain[:31]
    ws.append(FIELD_NAMES)
    for row in all_results:
        ws.append([row.get(f, "") for f in FIELD_NAMES])
    wb.save(output_xlsx)

    print(f"\nXLSX: {output_xlsx}")


# ======================== 主流程 ========================
def main():
    if not PAGES:
        print("[ERROR] 请先设置 PAGES 列表")
        return
    if not XPATH_LINK:
        print("[ERROR] 请先设置 XPATH_LINK")
        return
    if not XPATH_LOAD_MORE:
        print("[ERROR] 请先设置 XPATH_LOAD_MORE")
        return

    print(f"共 {len(PAGES)} 个页面待采集")
    print(f"链接 XPath: {XPATH_LINK}")
    print(f"加载更多按钮 XPath: {XPATH_LOAD_MORE}")
    print(f"点击间隔: {CLICK_PAUSE}s，连续 {MAX_NO_CHANGE} 次无变化则停止")
    print()

    driver = create_driver()
    all_results = []
    global_seen = set()

    try:
        for i, (title, url) in enumerate(PAGES, 1):
            print(f"[{i}/{len(PAGES)}] {title}")
            print(f"  URL: {url}")

            driver.get(url)
            time.sleep(3)  # 等待首次渲染

            print("  开始点击加载更多...")
            click_load_more(driver)

            tree = get_page_html(driver)
            links = collect_links(tree, driver.current_url)

            new_count = 0
            for link in links:
                if link not in global_seen:
                    global_seen.add(link)
                    all_results.append({"title": title, "link": link})
                    new_count += 1

            print(f"  采集到 {len(links)} 条链接，新增 {new_count} 条（去重后）")
            print()

    finally:
        driver.quit()

    print(f"采集完成: 共 {len(all_results)} 条链接")
    if all_results:
        domain = urlparse(PAGES[0][1]).netloc
        save_results(all_results, domain)
    else:
        print("未采集到任何链接，请检查 XPath 是否正确")


if __name__ == "__main__":
    main()
