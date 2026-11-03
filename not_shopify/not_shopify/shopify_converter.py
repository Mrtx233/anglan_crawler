import random
import re
import string
from itertools import product
from pathlib import Path

import openpyxl
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


def generate_unique_handle(existing_handles):
    while True:
        digits = "".join(random.choices(string.digits, k=3))
        letters1 = "".join(random.choices(string.ascii_lowercase, k=2))
        letters2 = "".join(random.choices(string.ascii_lowercase, k=2))
        handle = f"-{letters1}{digits}{letters2}"
        if handle not in existing_handles:
            existing_handles.add(handle)
            return handle


def generate_variant_sku():
    while True:
        first_digit = "".join(random.choices(string.digits, k=1))
        if first_digit != "0":
            break

    digits1 = "".join(random.choices(string.digits, k=2))
    letters1 = "".join(random.choices(string.ascii_uppercase, k=2))
    letter1 = "".join(random.choices(string.ascii_uppercase, k=1))
    digits2 = "".join(random.choices(string.digits, k=2))
    letters2 = "".join(random.choices(string.ascii_uppercase, k=2))
    digits3 = "".join(random.choices(string.digits, k=3))
    return f"{first_digit}{digits1}{letters1}-{letter1}{digits2}{letters2}-{digits3}{letters1}"


def clean_name(name):
    if pd.isna(name):
        return ""
    cleaned_name = re.sub(r"[^a-zA-Z\s]", "", str(name)).lower()
    return cleaned_name.replace(" ", "-")


def safe_split(series):
    return series.fillna("").astype(str).str.split("#")


def handle_option(series):
    return safe_split(series).str[0].fillna("")


def create_output_df(input_df):
    output_df = pd.DataFrame(columns=SHOPIFY_COLUMNS)
    existing_handles = set()

    output_df["Link-Href"] = input_df.get("link-href", "")
    base_handles = input_df["name"].apply(clean_name)
    handles = input_df["name"].apply(
        lambda name: generate_unique_handle(existing_handles) if pd.notna(name) else ""
    )
    output_df["Handle"] = [
        f"{base}{handle}"
        for base, handle in zip(base_handles, handles)
    ]

    output_df["Title"] = input_df["name"]
    output_df["Body (HTML)"] = input_df["details"]
    output_df["Collection"] = input_df["title"]
    output_df["Vendor"] = input_df["title"]
    output_df["Variant Compare At Price"] = input_df["price2"]
    output_df["Variant Price"] = input_df["price1"]
    output_df["Published"] = "TRUE"
    output_df["Image Src"] = input_df["src_links"].fillna("").astype(str).str.split("#")
    output_df["Variant Weight Unit"] = "kg"

    output_df["Option1 Name"] = handle_option(input_df["styles1"])
    output_df["Option1 Value"] = safe_split(input_df["styles1"]).str[1:].apply(
        lambda value: value if isinstance(value, list) and value else [""]
    )

    output_df["Option2 Name"] = handle_option(input_df["styles2"])
    output_df["Option2 Value"] = safe_split(input_df["styles2"]).str[1:].apply(
        lambda value: value if isinstance(value, list) and value else [""]
    )

    output_df["Option3 Name"] = handle_option(input_df["styles3"])
    output_df["Option3 Value"] = safe_split(input_df["styles3"]).str[1:].apply(
        lambda value: value if isinstance(value, list) and value else [""]
    )

    return output_df


def expand_shopify_rows(output_df):
    all_rows = []
    for _, row in output_df.iterrows():
        option1_values = row["Option1 Value"] or [""]
        option2_values = row["Option2 Value"] or [""]
        option3_values = row["Option3 Value"] or [""]
        image_srcs = row["Image Src"] if isinstance(row["Image Src"], list) else [row["Image Src"]]

        combinations = list(product(option1_values, option2_values, option3_values))
        combination_count = len(combinations)
        image_count = len(image_srcs)
        total_rows = max(combination_count, image_count)

        for index in range(total_rows):
            new_row = row.copy()

            if index < combination_count:
                combo = combinations[index]
                new_row["Option1 Value"] = combo[0]
                new_row["Option2 Value"] = combo[1]
                new_row["Option3 Value"] = combo[2]
            else:
                new_row["Option1 Value"] = ""
                new_row["Option2 Value"] = ""
                new_row["Option3 Value"] = ""

            common_variant_values = {
                "Variant SKU": generate_variant_sku(),
                "Variant Grams": 0,
                "Variant Inventory Tracker": "shopify",
                "Variant Inventory Qty": 999,
                "Variant Inventory Policy": "deny",
                "Variant Fulfillment Service": "manual",
                "Variant Requires Shipping": "TRUE",
                "Variant Taxable": "FALSE",
            }

            if index == 0:
                new_row.update({
                    "Title": row["Title"],
                    "Body (HTML)": row["Body (HTML)"],
                    "Collection": row["Collection"],
                    "Vendor": row["Vendor"],
                    "Option1 Name": row["Option1 Name"],
                    "Option2 Name": row["Option2 Name"],
                    "Option3 Name": row["Option3 Name"],
                    "Published": row["Published"],
                    "Gift Card": "FALSE",
                    "SEO Title": row["Title"],
                    "SEO Description": row["Title"],
                    **common_variant_values,
                })
            else:
                new_row.update({
                    "Title": "",
                    "Body (HTML)": "",
                    "Collection": "",
                    "Vendor": "",
                    "Published": "",
                    "Option1 Name": "",
                    "Option2 Name": "",
                    "Option3 Name": "",
                    **common_variant_values,
                })

            if index < image_count:
                new_row["Image Src"] = image_srcs[index]
                new_row["Image Position"] = index + 1
            else:
                new_row["Image Src"] = None
                new_row["Image Position"] = None

            if index >= combination_count:
                for column in [
                    "Variant SKU",
                    "Variant Grams",
                    "Variant Inventory Tracker",
                    "Variant Inventory Qty",
                    "Variant Inventory Policy",
                    "Variant Fulfillment Service",
                    "Variant Price",
                    "Variant Compare At Price",
                    "Variant Requires Shipping",
                    "Variant Taxable",
                ]:
                    if column in new_row:
                        new_row.pop(column)

            all_rows.append(new_row)

    return pd.DataFrame(all_rows)


def split_prices(text):
    parts = text.rsplit("$", 2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return text, "", ""


def split_option_value(value):
    if value is None:
        return [""] * 7

    text = str(value)
    option_text, price1, price2 = split_prices(text)
    option_parts = option_text.split("&") if option_text else []
    result = [""] * 7
    for index, part in enumerate(option_parts[:5]):
        result[index] = part
    result[-2] = float(price1) if price1 else ""
    result[-1] = float(price2) if price2 else ""
    return result


def split_shopify_option_file(output_file_name):
    source_col = 11
    total_cols = 7
    split_headers = [
        "Option1 Value",
        "Option2 Name",
        "Option2 Value",
        "Option3 Name",
        "Option3 Value",
        "Variant Price",
        "Variant Compare At Price",
    ]

    output_path = Path(output_file_name)
    split_output = output_path.with_name(f"{output_path.stem}_拆分{output_path.suffix}")

    wb = openpyxl.load_workbook(output_file_name)
    ws = wb.active
    ws.insert_cols(source_col + 1, total_cols - 1)
    for offset, header in enumerate(split_headers):
        ws.cell(row=1, column=source_col + offset, value=header)

    for row in range(2, ws.max_row + 1):
        source_value = ws.cell(row=row, column=source_col).value
        values = split_option_value(source_value)
        for offset, value in enumerate(values):
            ws.cell(row=row, column=source_col + offset, value=value)

    col_j = 10
    col_l = 12
    col_n = 14
    for row in range(2, ws.max_row + 1):
        if not ws.cell(row=row, column=col_j).value:
            ws.cell(row=row, column=col_l, value="")
            ws.cell(row=row, column=col_n, value="")

    wb.save(split_output)
    return split_output


def convert_to_shopify(input_file_name):
    input_path = Path(input_file_name)
    output_file_name = input_path.with_name(f"{input_path.stem}_原价{input_path.suffix}")

    with pd.ExcelFile(input_path) as xls:
        input_df = pd.read_excel(xls)

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in input_df.columns
    ]
    if missing_columns:
        raise ValueError(f"输入文件缺少必要列: {', '.join(missing_columns)}")

    output_df = create_output_df(input_df)
    final_df = expand_shopify_rows(output_df)

    option1_value_split = final_df["Option1 Value"].apply(
        lambda value: value.split("@", 1)
        if isinstance(value, str) and "@" in value
        else [value, None]
    )
    final_df["Option1 Value"] = option1_value_split.apply(lambda value: value[0])
    final_df["Variant Image"] = option1_value_split.apply(lambda value: value[1])

    final_df.to_excel(output_file_name, index=False)
    split_output = split_shopify_option_file(output_file_name)
    return output_file_name, split_output
