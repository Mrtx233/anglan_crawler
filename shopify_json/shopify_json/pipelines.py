# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import sys
from datetime import datetime
from pathlib import Path

import openpyxl
from itemadapter import ItemAdapter
from scrapy import signals

from shopify_json.utils.shopify_converter import convert_to_shopify


def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(str(text).encode("gbk", errors="replace").decode("gbk"))


def extract_images_from_styles(styles_str):
    """从 styles 字符串中提取 @image URL，保持出现顺序，去重。"""
    if not styles_str:
        return []
    images = []
    seen = set()
    for segment in styles_str.split("#"):
        if "@" in segment:
            img = segment.split("@", 1)[1].strip()
            if img and img not in seen:
                seen.add(img)
                images.append(img)
    return images


class ShopifyJsonPipeline:
    fields = [
        "title",
        "name",
        "price1",
        "price2",
        "styles1",
        "styles2",
        "styles3",
        "src_links",
        "link-href",
        "details",
    ]

    def open_spider(self, spider):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        module = sys.modules.get(spider.__module__)
        input_file = getattr(spider, "INPUT_FILE", None) or getattr(module, "INPUT_FILE", None)
        if input_file:
            input_path = Path(input_file)
            parent_name = input_path.parent.name
            output_group = str(Path(parent_name) / input_path.stem) if parent_name and parent_name != "." else input_path.stem
        else:
            output_group = spider.name
        output_dir = Path(__file__).resolve().parent / "output" / output_group / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = output_dir
        self.xlsx_path = output_dir / f"{spider.name}_styles.xlsx"
        self.rows = []
        self.current = 0
        self.fail_count = 0
        spider.crawler.signals.connect(self._item_dropped, signal=signals.item_dropped)

    def _item_dropped(self, item, response, exception, spider):
        self.current += 1
        self.fail_count += 1
        total = getattr(spider, "total_items", "?")
        safe_print(f"[{self.current}/{total}] 获取失败: {exception}")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        row = {
            field: adapter.get(field, "")
            for field in self.fields
        }
        # src_links: 取 spider 前5张商品图，追加 styles 中 @image 变体图，去重
        spider_images = [u.strip() for u in row.get("src_links", "").split("#") if u.strip()][:5]
        seen = set(spider_images)
        for key in ("styles1", "styles2", "styles3"):
            for img in extract_images_from_styles(row.get(key, "")):
                if img not in seen:
                    seen.add(img)
                    spider_images.append(img)
        row["src_links"] = "#".join(spider_images)
        self.rows.append(row)
        self.current += 1
        total = getattr(spider, "total_items", "?")
        safe_print(f"[{self.current}/{total}] 获取成功")
        return item

    def close_spider(self, spider):
        safe_print(f"完成: {len(self.rows)} 成功, {self.fail_count} 失败")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = spider.name
        ws.append(self.fields)
        for row in self.rows:
            ws.append([row.get(field, "") for field in self.fields])
        wb.save(self.xlsx_path)

        print(f"XLSX saved: {self.xlsx_path} ({len(self.rows)} rows)")

        if not self.rows:
            safe_print("No rows scraped; skipping Shopify conversion.")
            return

        price_path, match_path = convert_to_shopify(self.xlsx_path)
        print(f"Shopify price XLSX saved: {price_path}")
        print(f"Shopify match XLSX saved: {match_path}")
