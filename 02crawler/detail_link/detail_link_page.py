# ======================== 详情页链接采集 ========================
#
# 用途: 从列表页采集所有产品详情页链接（标题 + URL）
#
# 使用方式:
#   1. 修改 PAGES 列表（标题 + 链接）和 XPATH_LINK
#   2. 运行脚本，自动打开浏览器依次访问每个页面并提取链接
#
# 技术栈: DrissionPage + lxml
# 输出: XLSX（title, link）
# ================================================================

import os
import random
import time
from urllib.parse import urljoin, urlparse

import openpyxl
from DrissionPage import Chromium, ChromiumOptions
from lxml import html

# ===== 配置：修改此处 =====
XPATH_LINK = '//*[@id="product-grid"]/div/div/div[2]/a/@href'
MAX_PAGES = 7  # 每个分类最多采集页数
START_PAGE = 1  # 从第几页开始采集（1=从头开始）
PAGES = [
    ("Loungewear > Pajamas", "https://shophoneydew.com/collections/sleep-pajamas"),
    ("Loungewear > Dresses", "https://shophoneydew.com/collections/dresses"),
    ("Loungewear > Robes", "https://shophoneydew.com/collections/robes"),
    ("Loungewear > Lounge Sets", "https://shophoneydew.com/collections/loungesets"),
    ("Loungewear > Lounge Tops", "https://shophoneydew.com/collections/loungetops"),
    ("Loungewear > Lounge Bottoms", "https://shophoneydew.com/collections/lounge-bottoms"),
    ("Intimates > Lingerie", "https://shophoneydew.com/collections/intimates-lingerie"),
    ("Intimates > Underwear", "https://shophoneydew.com/collections/intimates-underwear"),
    ("Intimates > Bras", "https://shophoneydew.com/collections/intimates-bras"),
]

# ======================== 路径配置 ========================
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

MAX_RETRIES = 3   # 首页无链接时重试次数（反爬检测）
RETRY_DELAY = 5   # 重试间隔秒数
PAGE_LOAD_WAIT = 0  # 页面加载后额外等待秒数


# ======================== 浏览器初始化 ========================
def create_browser():
    co = ChromiumOptions()
    co.incognito(on_off=True)
    co.set_argument("--proxy-server=http://127.0.0.1:7897")
    random_port = random.randint(9222, 9322)
    co.set_local_port(random_port)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            chrome = Chromium(co)
            print(f"浏览器启动成功，端口: {random_port}")
            return chrome
        except Exception as e:
            print(f"端口 {random_port} 启动失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            random_port = random.randint(9222, 9322)
            co.set_local_port(random_port)
    raise RuntimeError("无法启动浏览器，已重试多次")


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


def get_page_html(tab):
    """获取当前页面完整 DOM 并返回 lxml tree"""
    raw = tab.run_js("return document.documentElement.outerHTML;")
    return html.fromstring(raw)


def scroll_page(tab, scroll_pause=1.5, max_scrolls=30):
    """滚动到页面底部，触发懒加载。页面高度不再变化时停止。"""
    last_height = tab.run_js("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        tab.run_js("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(scroll_pause)
        new_height = tab.run_js("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


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
    print()

    chrome = create_browser()
    tab = chrome.latest_tab
    all_results = []

    try:
        for i, (title, base_url) in enumerate(PAGES, 1):
            print(f"[{i}/{len(PAGES)}] {title}")

            page_links = []
            seen_in_category = set()
            page_num = START_PAGE

            while True:
                # 超过最大页数限制
                if page_num > MAX_PAGES:
                    print(f"  已达到最大页数 {MAX_PAGES}，该分类采集完毕")
                    break

                # 拼接分页 URL：第1页不带参数，后续加 ?page=N
                if page_num == 1:
                    url = base_url
                else:
                    sep = "&" if "?" in base_url else "?"
                    url = f"{base_url}{sep}page={page_num}"

                print(f"  第 {page_num} 页: {url}")
                tab.get(url)
                time.sleep(PAGE_LOAD_WAIT)
                scroll_page(tab)

                tree = get_page_html(tab)
                links = collect_links(tree, tab.url)

                # 找出本页新链接
                new_links = [l for l in links if l not in seen_in_category]

                if not new_links:
                    # 首页无链接 → 可能被反爬检测，重试
                    if page_num == START_PAGE:
                        retried = False
                        for retry in range(1, MAX_RETRIES + 1):
                            print(f"  首页无链接，可能被反爬检测，第 {retry}/{MAX_RETRIES} 次重试（{RETRY_DELAY}s 后）...")
                            time.sleep(RETRY_DELAY)
                            tab.get(url)
                            time.sleep(PAGE_LOAD_WAIT)
                            scroll_page(tab)
                            tree = get_page_html(tab)
                            links = collect_links(tree, tab.url)
                            new_links = [l for l in links if l not in seen_in_category]
                            if new_links:
                                print(f"  重试成功，获取到 {len(new_links)} 条链接")
                                retried = True
                                break
                        if not retried:
                            print(f"  首页重试 {MAX_RETRIES} 次仍无链接，跳过该分类")
                            break
                    else:
                        print(f"  第 {page_num} 页无新链接，该分类采集完毕")
                        break

                for link in new_links:
                    seen_in_category.add(link)
                    page_links.append(link)

                print(f"  新增 {len(new_links)} 条（累计 {len(page_links)} 条）")
                page_num += 1

            for link in page_links:
                all_results.append({"title": title, "link": link})

            print(f"  共采集 {len(page_links)} 条链接")
            print()

    finally:
        chrome.quit()

    print(f"采集完成: 共 {len(all_results)} 条链接")
    if all_results:
        domain = urlparse(PAGES[0][1]).netloc
        save_results(all_results, domain)
    else:
        print("未采集到任何链接，请检查 XPath 是否正确")


if __name__ == "__main__":
    main()
