import random
import re
import string
from itertools import product
from pathlib import Path

import pandas as pd


SHOPIFY_COLUMNS = [
    "Link-Href", "Handle", "Title", "Body (HTML)", "Collection",
    "Vendor", "Type", "Tags", "Published", "Option1 Name",
    "Option1 Value", "Option2 Name", "Option2 Value", "Option3 Name",
    "Option3 Value", "Variant SKU", "Variant Grams",
    "Variant Inventory Tracker", "Variant Inventory Qty",
    "Variant Inventory Policy", "Variant Fulfillment Service",
    "Variant Price", "Variant Compare At Price",
    "Variant Requires Shipping", "Variant Taxable",
    "Variant Barcode", "Image Src", "Image Position",
    "Image Alt Text", "Gift Card", "SEO Title",
    "SEO Description", "Google Shopping - Google Product Category",
    "Google Shopping - Gender", "Google Shopping - Age Group",
    "Google Shopping - MPN", "Google Shopping - AdWords Grouping",
    "Google Shopping - AdWords Labels", "Google Shopping - Condition",
    "Google Shopping - Custom Product", "Google Shopping - Custom Label 0",
    "Google Shopping - Custom Label 1", "Google Shopping - Custom Label 2",
    "Google Shopping - Custom Label 3", "Google Shopping - Custom Label 4",
    "Variant Image", "Variant Weight Unit", "Variant Tax Code",
    "Cost per item",
]

REQUIRED_COLUMNS = [
    "title",
    "name",
    "price1",
    "price2",
    "details",
    "src_links",
    "styles1",
    "styles2",
    "styles3",
]

PRICE_LIBRARY = [
    8.99, 9.01, 9.31, 9.33, 9.37, 9.63, 9.71, 9.72, 9.84, 9.86, 9.95, 9.99,
    10.03, 10.05, 10.11, 10.13, 10.15, 10.35, 10.36, 10.38, 10.54, 10.63, 10.64, 10.66,
    10.71, 10.78, 10.83, 10.94, 10.95, 10.99, 11.22, 11.36, 11.48, 11.65, 11.87, 11.95,
    11.99, 12.22, 12.25, 12.36, 12.41, 12.87, 12.92, 12.95, 12.99, 13.02, 13.13, 13.14,
    13.47, 13.69, 13.95, 13.99, 14.25, 14.32, 14.62, 14.83, 14.91, 14.95, 14.99, 15.31,
    15.52, 15.78, 15.95, 15.99, 16.34, 16.53, 16.66, 16.77, 16.95, 16.99, 17.11, 17.34,
    17.57, 17.95, 17.99, 18.62, 18.81, 18.84, 18.95, 18.99, 19.04, 19.25, 19.95, 19.99,
    20.14, 20.19, 20.34, 20.68, 20.74, 20.95, 20.99, 21.3, 21.47, 21.74, 21.95, 21.99,
    22.31, 22.34, 22.81, 22.95, 22.99, 23.14, 23.32, 23.95, 23.99, 24.22, 24.46, 24.63,
    24.95, 24.99, 25.37, 25.95, 25.99, 26.18, 26.34, 26.95, 26.99, 27.31, 27.54, 27.95,
    27.99, 28.11, 28.95, 28.99, 29, 29.31, 29.95, 29.99, 30.54, 30.95, 30.99, 31.26,
    31.52, 31.95, 31.99, 32.14, 32.24, 32.95, 32.99, 33.62, 33.84, 33.95, 33.99, 34.18,
    34.62, 34.95, 34.99, 35, 35.14, 35.33, 35.95, 35.99, 36.47, 36.95, 36.99, 37.21,
    37.95, 37.99, 38.14, 38.52, 38.95, 38.99, 39, 39.54, 39.95, 39.99, 40.02, 40.15,
    40.95, 40.99, 41.32, 41.95, 41.99, 42.51, 42.95, 42.99, 43.16, 43.95, 43.99, 44.82,
    44.95, 44.99, 45.17, 45.95, 45.99, 46.57, 47.82, 48.36, 49, 49.31, 50.03, 50.13,
    50.81, 55, 59, 69, 79, 85, 89, 99, 109, 119, 129, 189, 219, 259, 299, 319,
    349, 369, 399, 459, 499, 519, 599,
]


def generate_unique_handle(base, used_handles):
    while True:
        digits = "".join(random.choices(string.digits, k=3))
        letters1 = "".join(random.choices(string.ascii_lowercase, k=2))
        letters2 = "".join(random.choices(string.ascii_lowercase, k=2))
        handle = f"{base}-{letters1}{digits}{letters2}" if base else f"-{letters1}{digits}{letters2}"
        if handle not in used_handles:
            used_handles.add(handle)
            return handle


def generate_variant_sku(used_skus=None):
    while True:
        first_digit = random.choice("123456789")
        digits1 = "".join(random.choices(string.digits, k=2))
        letters1 = "".join(random.choices(string.ascii_uppercase, k=2))
        letter1 = random.choice(string.ascii_uppercase)
        digits2 = "".join(random.choices(string.digits, k=2))
        letters2 = "".join(random.choices(string.ascii_uppercase, k=2))
        digits3 = "".join(random.choices(string.digits, k=3))
        sku = f"{first_digit}{digits1}{letters1}-{letter1}{digits2}{letters2}-{digits3}{letters1}"
        if used_skus is None or sku not in used_skus:
            if used_skus is not None:
                used_skus.add(sku)
            return sku


def clean_cell(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def clean_handle_name(name):
    name = clean_cell(name)
    cleaned = re.sub(r"[^a-zA-Z\s]", "", name).lower()
    return cleaned.replace(" ", "-").strip("-")


def parse_style_group(value):
    parts = [part.strip() for part in clean_cell(value).split("#") if part.strip()]
    if not parts:
        return "", [""]
    if len(parts) == 1:
        return parts[0], [""]
    return parts[0], parts[1:]


def parse_variant_segment(segment):
    text = clean_cell(segment)
    image = ""
    if "@" in text:
        text, image = text.split("@", 1)
    price1 = ""
    price2 = ""
    price_parts = text.rsplit("$", 2)
    if len(price_parts) == 3:
        text, price1, price2 = price_parts
    option_parts = text.split("&") if text else []
    return {
        "option1_value": option_parts[0] if len(option_parts) > 0 else "",
        "option2_name": option_parts[1] if len(option_parts) > 1 else "",
        "option2_value": option_parts[2] if len(option_parts) > 2 else "",
        "option3_name": option_parts[3] if len(option_parts) > 3 else "",
        "option3_value": option_parts[4] if len(option_parts) > 4 else "",
        "price1": price1,
        "price2": price2,
        "image": image.strip(),
    }


def match_prices(shopify_file_name):
    """对拆分后的 Shopify 文件执行价格匹配，输出 _价格匹配 和 _未匹配到的价格 文件（xlsx + csv）。"""
    shopify_path = Path(shopify_file_name)
    df = pd.read_excel(shopify_path).reset_index(drop=True)
    df["匹配价格"] = None

    price_library_sorted = sorted(PRICE_LIBRARY)
    global_used_prices = set()

    for handle, group in df.groupby("Handle"):
        if pd.isna(handle):
            continue

        valid_rows = []
        for idx, row in group.iterrows():
            price = row.get("Variant Price")
            if pd.isna(price):
                continue
            try:
                valid_rows.append((idx, float(price)))
            except (ValueError, TypeError):
                continue

        if not valid_rows:
            continue

        valid_rows_sorted = sorted(valid_rows, key=lambda x: x[1])
        available_prices = [p for p in price_library_sorted if p not in global_used_prices]

        for idx, original_price in valid_rows_sorted:
            lower_bound = original_price * 0.75
            upper_bound = original_price * 1.25
            candidates = [p for p in available_prices if lower_bound <= p <= upper_bound]

            if candidates:
                matched = candidates[0]
                global_used_prices.add(matched)
                available_prices.remove(matched)
                df.at[idx, "匹配价格"] = matched

    output_stem = shopify_path.stem
    for suffix in ("_Shopify_原价",):
        if output_stem.endswith(suffix):
            output_stem = output_stem[: -len(suffix)]
            break

    xlsx_dir = shopify_path.parent
    csv_dir = xlsx_dir.parent / "csv"
    csv_dir.mkdir(exist_ok=True)
    unused_prices = [p for p in price_library_sorted if p not in global_used_prices]
    unused_df = pd.DataFrame({"未匹配价格": unused_prices})

    price_xlsx = xlsx_dir / f"{output_stem}_Shopify_价格匹配.xlsx"
    price_csv = csv_dir / f"{output_stem}_Shopify_价格匹配.csv"
    unused_xlsx = xlsx_dir / f"{output_stem}_Shopify_未匹配到的价格.xlsx"
    unused_csv = csv_dir / f"{output_stem}_Shopify_未匹配到的价格.csv"

    df.to_excel(price_xlsx, index=False)
    df.to_csv(price_csv, index=False, encoding="utf-8-sig")
    unused_df.to_excel(unused_xlsx, index=False)
    unused_df.to_csv(unused_csv, index=False, encoding="utf-8-sig")

    print(f"价格匹配: {price_xlsx}")
    print(f"未匹配价格: {unused_xlsx}")
    print(f"已使用价格数量: {len(global_used_prices)}")
    print(f"未匹配价格数量: {len(unused_prices)}")

    return price_xlsx


def convert_to_shopify(input_file_name):
    input_path = Path(input_file_name)

    xlsx_dir = input_path.parent / "xlsx"
    csv_dir = input_path.parent / "csv"
    xlsx_dir.mkdir(exist_ok=True)
    csv_dir.mkdir(exist_ok=True)

    output_file_name = xlsx_dir / f"{input_path.stem}_Shopify_原价.xlsx"
    csv_path = csv_dir / f"{input_path.stem}_Shopify_原价.csv"

    input_df = pd.read_excel(input_path)
    missing = [col for col in REQUIRED_COLUMNS if col not in input_df.columns]
    if missing:
        raise ValueError(f"输入文件缺少必要列: {', '.join(missing)}")

    rows = []
    used_handles = set()
    used_skus = set()

    for _, item in input_df.iterrows():
        base_handle = clean_handle_name(item.get("name", ""))
        handle = generate_unique_handle(base_handle, used_handles)

        option1_name, option1_values = parse_style_group(item.get("styles1", ""))
        option2_name, option2_values = parse_style_group(item.get("styles2", ""))
        option3_name, option3_values = parse_style_group(item.get("styles3", ""))
        images = [img.strip() for img in clean_cell(item.get("src_links", "")).split("#") if img.strip()]
        combinations = list(product(option1_values or [""], option2_values or [""], option3_values or [""]))
        total_rows = max(len(combinations), len(images), 1)

        for index in range(total_rows):
            row = {col: "" for col in SHOPIFY_COLUMNS}
            row["Link-Href"] = clean_cell(item.get("link-href", ""))
            row["Handle"] = handle
            row["Variant Weight Unit"] = "kg"

            if index == 0:
                row["Title"] = clean_cell(item.get("name", ""))
                row["Body (HTML)"] = clean_cell(item.get("details", ""))
                row["Collection"] = clean_cell(item.get("title", ""))
                row["Vendor"] = clean_cell(item.get("title", ""))
                row["Published"] = "TRUE"
                row["Gift Card"] = "FALSE"
                row["SEO Title"] = row["Title"]
                row["SEO Description"] = row["Title"]

            if index < len(combinations):
                combo = combinations[index]
                seg = parse_variant_segment(combo[0])
                row["Option1 Name"] = option1_name
                row["Option1 Value"] = seg["option1_value"] or clean_cell(combo[0])
                row["Option2 Name"] = seg["option2_name"] or option2_name
                row["Option2 Value"] = seg["option2_value"] or clean_cell(combo[1])
                row["Option3 Name"] = seg["option3_name"] or option3_name
                row["Option3 Value"] = seg["option3_value"] or clean_cell(combo[2])
                row["Variant SKU"] = generate_variant_sku(used_skus)
                row["Variant Grams"] = 0
                row["Variant Inventory Tracker"] = "shopify"
                row["Variant Inventory Qty"] = 999
                row["Variant Inventory Policy"] = "deny"
                row["Variant Fulfillment Service"] = "manual"
                row["Variant Price"] = seg["price1"] or clean_cell(item.get("price1", ""))
                row["Variant Compare At Price"] = seg["price2"] or clean_cell(item.get("price2", ""))
                row["Variant Requires Shipping"] = "TRUE"
                row["Variant Taxable"] = "FALSE"
                row["Variant Image"] = seg["image"]

            if index < len(images):
                row["Image Src"] = images[index]
                row["Image Position"] = index + 1

            rows.append(row)

    result_df = pd.DataFrame(rows, columns=SHOPIFY_COLUMNS)
    result_df.to_excel(output_file_name, index=False)
    result_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"已生成 Shopify 文件: {output_file_name}")
    print(f"已生成 CSV 文件: {csv_path}")
    print(f"商品数: {len(input_df)}，输出行数: {len(rows)}")

    price_matched = match_prices(str(output_file_name))
    return output_file_name, price_matched
