# ======================== 详情页链接采集（滚动加载） ========================
#
# 用途: 从列表页采集所有产品详情页链接（标题 + URL）
#       适用于无限滚动加载的页面（如 Shopify collection）
#
# 使用方式:
#   1. 修改 PAGES 列表（标题 + 链接）和 XPATH_LINK
#   2. 运行脚本，自动打开浏览器滚动加载并提取链接
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
from webdriver_manager.chrome import ChromeDriverManager
from lxml import html

# ===== 配置：修改此处 =====
XPATH_LINK = "//h3/a/@href"  # 产品链接 XPath

PAGES = [
    ("Sale > Shirts", "https://www.oliveclothing.com/shirts/?snapshotId=4b31fc01-e10b-43f2-9464-ff00a3346b2a"),
    ("Sale > Shirts", "https://www.oliveclothing.com/shirts/?snapshotId=0e6326bc-0ce8-425a-898f-bb6c7edd1864&page=2"),
    ("Sale > Shirts", "https://www.oliveclothing.com/shirts/?snapshotId=0e6326bc-0ce8-425a-898f-bb6c7edd1864&page=3"),
    ("Sale > Sweaters", "https://www.oliveclothing.com/categories/men/knitwear/sweaters.html?snapshotId=7dd539c9-04cf-4348-bd19-3b7d181e9a3d"),
    ("Sale > Sweaters", "https://www.oliveclothing.com/categories/men/knitwear/sweaters.html?page=2&snapshotId=016f64ce-49c8-4441-82ec-e27ac555fc94"),
    ("Sale > Cardigans", "https://www.oliveclothing.com/categories/men/knitwear/cardigans.html?snapshotId=d8e34dac-d81c-4d4d-8aea-f50bee17a3e2"),
    ("Sale > Outerwear", "https://www.oliveclothing.com/outerwear/"),
    ("Sale > Outerwear", "https://www.oliveclothing.com/outerwear/?page=2"),
    ("Sale > Sweatshirts", "https://www.oliveclothing.com/sweatshirts/?snapshotId=bed35718-7e16-4813-a949-19289be39743"),
    ("Sale > Trousers", "https://www.oliveclothing.com/categories/men/legwear/trousers.html?snapshotId=65fd744b-ef24-4588-a838-ced5a574c80d"),
    ("Sale > Trousers", "https://www.oliveclothing.com/categories/men/legwear/trousers.html?snapshotId=fdffc805-1d3f-460d-ac12-f8a356c61c8d&page=2"),
    ("Sale > Trousers", "https://www.oliveclothing.com/categories/men/legwear/trousers.html?snapshotId=fdffc805-1d3f-460d-ac12-f8a356c61c8d&page=3"),
    ("Sale > Jeans", "https://www.oliveclothing.com/categories/men/legwear/jeans.html?snapshotId=5ad9d58f-bb38-46fa-8c01-2b462bb13807"),
    ("Sale > Shorts", "https://www.oliveclothing.com/categories/men/legwear/shorts.html?snapshotId=78027000-0a16-4d40-8baf-b36859b3f9bf"),
]

# ======================== 路径配置 ========================
OUTPUT_DIR = r"/02crawler/output"

SCROLL_PAUSE = 2       # 每次滚动后等待秒数
MAX_NO_CHANGE = 3      # 连续几次滚动无新内容则停止
SCROLL_STEP = 800      # 每次滚动像素数


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


def scroll_to_load_all(driver):
    """滚动页面直到内容不再增加"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    no_change_count = 0

    while no_change_count < MAX_NO_CHANGE:
        driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
        time.sleep(SCROLL_PAUSE)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            no_change_count += 1
        else:
            no_change_count = 0
        last_height = new_height


def dismiss_popup(driver):
    """检测到配送国家/地区确认弹窗时，选择美国(USD)并关闭"""
    try:
        has_popup = driver.execute_script("""
            var selects = document.querySelectorAll('select');
            for (var i = 0; i < selects.length; i++) {
                var opts = selects[i].options;
                for (var j = 0; j < opts.length; j++) {
                    if (opts[j].text.includes('美国') || opts[j].text.includes('United States')) {
                        return true;
                    }
                }
            }
            return false;
        """)
        if not has_popup:
            return False

        driver.execute_script("""
            var selects = document.querySelectorAll('select');
            for (var i = 0; i < selects.length; i++) {
                var opts = selects[i].options;
                for (var j = 0; j < opts.length; j++) {
                    if (opts[j].text.includes('美国') || opts[j].text.includes('United States')) {
                        selects[i].selectedIndex = j;
                        selects[i].dispatchEvent(new Event('change', {bubbles: true}));
                        break;
                    }
                }
            }
        """)
        time.sleep(2)

        clicked = driver.execute_script("""
            var btns = document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.includes('确认并继续') || btns[i].textContent.includes('Confirm and continue')) {
                    btns[i].click();
                    return true;
                }
            }
            return false;
        """)
        if clicked:
            print("  [POPUP] 检测到配送弹窗，已选择美国(USD)并确认")
            time.sleep(2)
            return True
    except Exception:
        pass
    return False


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

    print(f"共 {len(PAGES)} 个页面待采集")
    print(f"链接 XPath: {XPATH_LINK}")
    print(f"滚动间隔: {SCROLL_PAUSE}s，连续 {MAX_NO_CHANGE} 次无变化则停止")
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

            # 检测并关闭配送国家弹窗
            dismiss_popup(driver)

            print("  开始滚动加载...")
            scroll_to_load_all(driver)

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
