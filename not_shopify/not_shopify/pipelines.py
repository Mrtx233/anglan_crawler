# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import csv
import os
from datetime import datetime
from pathlib import Path

import openpyxl
from itemadapter import ItemAdapter

from not_shopify.shopify_converter import convert_to_shopify


FIELD_NAMES = [
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


class NotShopifyPipeline:
    def open_spider(self, spider):
        self.items = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_root = Path(__file__).resolve().parents[1]
        self.output_dir = os.path.join(project_root, "output", timestamp)
        os.makedirs(self.output_dir, exist_ok=True)
        table_name = f"{spider.name}_test" if getattr(spider, "test_mode", False) else spider.name
        self.csv_path = os.path.join(self.output_dir, f"{table_name}.csv")
        self.xlsx_path = os.path.join(self.output_dir, f"{table_name}.xlsx")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        row = {}
        for field in FIELD_NAMES:
            source_field = "link_href" if field == "link-href" else field
            row[field] = adapter.get(source_field, "")

        self.items.append(row)
        print("=" * 60)
        for field in FIELD_NAMES:
            print(f"{field}: {row[field]}")
        print("=" * 60)
        return item

    def close_spider(self, spider):
        if not self.items:
            return

        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
            writer.writeheader()
            writer.writerows(self.items)
        print(f"CSV saved: {self.csv_path}")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = spider.name
        ws.append(FIELD_NAMES)
        for row in self.items:
            ws.append([row.get(field, "") for field in FIELD_NAMES])
        wb.save(self.xlsx_path)
        print(f"XLSX saved: {self.xlsx_path}")

        shopify_path, split_path = convert_to_shopify(self.xlsx_path)
        print(f"Shopify XLSX saved: {shopify_path}")
        print(f"Shopify split XLSX saved: {split_path}")
