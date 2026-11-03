import random
from pathlib import Path

import scrapy

from not_shopify.items import NotShopifyItem
from not_shopify.utils import (
    extract_price,
    extract_quince_image_links,
    get_text,
    get_texts,
    normalize_quince_style,
    read_quince_targets,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = PROJECT_ROOT / "../01xlsx/quince.xlsx"

TEST_MODE = False
TEST_COUNT = 10

XPATH_NAME = "//h1[contains(@class,'productInfo_container__header__text')]"
XPATH_PRICE1 = "//span[contains(@class,'salesPrice_selector_for_force_update') or contains(@class,'sales_price_selector_for_force_update')]"
XPATH_PRICE2 = "//span[contains(@class,'traditionalPrice_selector_for_force_update') or contains(@class,'traditional_price_selector_for_force_update')]"
XPATH_STYLES1 = "//legend[contains(@class,'productForm_container__label')]"
XPATH_STYLES2 = ""
XPATH_STYLES3 = ""
XPATH_DETAILS = "//div[contains(@class,'product-description_productDescription__content')]/p"


class QuinceSpider(scrapy.Spider):
    name = "quince"
    allowed_domains = ["quince.com", "www.quince.com"]
    test_mode = TEST_MODE

    def _build_start_requests(self):
        targets = read_quince_targets(INPUT_FILE)
        if TEST_MODE and len(targets) > TEST_COUNT:
            targets = random.sample(targets, TEST_COUNT)
        print(f"[{self.name}] loaded {len(targets)} urls from {INPUT_FILE}")
        for category, url in targets:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "category": category,
                    "wait_xpath": XPATH_NAME,
                    "wait_extra": 3,
                },
            )

    def start_requests(self):
        yield from self._build_start_requests()

    async def start(self):
        for request in self._build_start_requests():
            yield request

    def parse(self, response):
        raw_styles1 = normalize_quince_style(get_text(response, XPATH_STYLES1))
        price1 = extract_price(get_text(response, XPATH_PRICE1))
        price2 = extract_price(get_text(response, XPATH_PRICE2))
        styles1 = f"{raw_styles1}${price1}${price2}" if raw_styles1 else f"${price1}${price2}"

        item = NotShopifyItem()
        item["title"] = response.meta.get("category", "")
        item["name"] = get_text(response, XPATH_NAME)
        item["price1"] = price1
        item["price2"] = price2
        item["styles1"] = styles1
        item["styles2"] = get_texts(response, XPATH_STYLES2)
        item["styles3"] = get_texts(response, XPATH_STYLES3)
        item["src_links"] = extract_quince_image_links(response, XPATH_STYLES1)
        item["link_href"] = response.url
        item["details"] = get_texts(response, XPATH_DETAILS, sep=" ")
        yield item
