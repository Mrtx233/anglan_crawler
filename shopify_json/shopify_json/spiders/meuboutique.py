import json
from pathlib import Path

import openpyxl
import scrapy
from scrapy import signals
from scrapy.exceptions import DontCloseSpider

from shopify_json.items import ShopifyJsonItem
from shopify_json.utils.json_variants import (
    build_first_image_srcs,
    build_variant_combo,
    clean_body_html,
    find_fallback_variant,
    format_price,
    format_price2,
    group_targets_by_json_url,
    fetch_exchange_rates,
    _exchange_rates_cache,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_FILE = PROJECT_ROOT / "01xlsx/A0730/陈港/lindvs.com连衣裙/meuboutique.myshopify.com.xlsx"
TEST_MODE = False
TEST_COUNT = 10
SKIP_POSITIONS = None
SKIP_OPTIONS = None

fetch_exchange_rates()


def read_targets_from_excel(filepath):
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    targets = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        title = str(row[0]).strip() if row and row[0] else ""
        url = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        if url:
            targets.append((title, url))
    wb.close()
    return targets


class MeuboutiqueSpider(scrapy.Spider):
    name = "meuboutique"
    allowed_domains = ["meuboutique.myshopify.com"]
    handle_httpstatus_list = [429]
    custom_settings = {
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 0.5,
        'RETRY_TIMES': 5,
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider._pending_retries = 0
        crawler.signals.connect(spider._spider_idle, signal=signals.spider_idle)
        return spider

    def _build_start_requests(self):
        targets = read_targets_from_excel(INPUT_FILE)
        if TEST_MODE:
            targets = targets[:TEST_COUNT]
        print(f"[{self.name}] loaded {len(targets)} urls from {INPUT_FILE}")

        json_url_groups, duplicate_count = group_targets_by_json_url(targets)
        self.total_items = len(json_url_groups)
        print(
            f"[{self.name}] {self.total_items} unique product urls "
            f"(from {len(targets)} rows, skipped {duplicate_count} duplicate product urls)"
        )

        for json_url, group in json_url_groups.items():
            yield scrapy.Request(
                json_url,
                callback=self.parse_json,
                headers={"Accept": "application/json,text/plain,*/*"},
                dont_filter=True,
                meta={
                    "table_title": group["title"],
                    "original_url": group["original_url"],
                    "json_url": json_url,
                },
            )

    def start_requests(self):
        yield from self._build_start_requests()

    async def start(self):
        for request in self._build_start_requests():
            yield request

    def _handle_429(self, response):
        """429时延迟重新排队，用计数器防止spider提前关闭"""
        from twisted.internet import reactor
        meta = response.meta.copy()
        retry_count = meta.get("retry_429", 0) + 1
        if retry_count > 5:
            print(f"[{self.name}] 429重试超过5次，放弃: {response.url}")
            return
        meta["retry_429"] = retry_count
        delay = 30 * retry_count
        self._pending_retries += 1
        print(f"[{self.name}] 429 第{retry_count}次，{delay}秒后重试: {response.url}")
        def _retry():
            self._pending_retries -= 1
            from scrapy import Request
            req = Request(
                response.url,
                callback=self.parse_json,
                headers={"Accept": "application/json,text/plain,*/*"},
                dont_filter=True,
                meta=meta,
            )
            self.crawler.engine.crawl(req)
        reactor.callLater(delay, _retry)

    def _spider_idle(self, spider):
        if self._pending_retries > 0:
            print(f"[{self.name}] 等待 {self._pending_retries} 个429重试，阻止关闭")
            raise DontCloseSpider

    def parse_json(self, response):
        if response.status == 429:
            self._handle_429(response)
            return
        data = json.loads(response.text)
        product = data.get("product", {})
        variant = find_fallback_variant(product)

        item = ShopifyJsonItem()
        item["title"] = response.meta["table_title"]
        item["name"] = product.get("title", "")
        item["price1"] = format_price(variant.get("price", ""), rates=_exchange_rates_cache, currency=variant.get("price_currency", ""))
        item["price2"] = format_price2(variant, rates=_exchange_rates_cache)
        item["styles1"] = build_variant_combo(product, skip_positions=SKIP_POSITIONS, skip_options=SKIP_OPTIONS, rates=_exchange_rates_cache)
        item["styles2"] = ""
        item["styles3"] = ""
        item["src_links"] = build_first_image_srcs(product, limit=5, skip_positions=SKIP_POSITIONS)
        item["link-href"] = response.meta["original_url"]
        item["details"] = clean_body_html(product.get("body_html", ""))
        yield item
