import pandas as pd
import random
import string
import re
from pathlib import Path
from tqdm import tqdm
import openpyxl

# ===== 配置：修改此处文件路径 =====
INPUT_FILE = r"C:\Users\Mrtx0\Desktop\合并1\shopunderstatement_styles.xlsx"

input_file_name = INPUT_FILE
input_path = Path(input_file_name)
output_file_name = str(input_path.with_name(f"{input_path.stem.replace('_styles', '_shopify')}_原价{input_path.suffix}"))


def generate_unique_handle(existing_handles):
    """生成不在 existing_handles 中的唯一句柄。"""
    while True:
        digits = ''.join(random.choices(string.digits, k=3))
        letters1 = ''.join(random.choices(string.ascii_lowercase, k=2))
        letters2 = ''.join(random.choices(string.ascii_lowercase, k=2))
        handle = f"-{letters1}{digits}{letters2}"
        if handle not in existing_handles:  # 检查唯一性
            existing_handles.add(handle)
            return handle


def generate_variant_sku():
    while True:
        digits = ''.join(random.choices(string.digits, k=1))
        if digits != '0':
            break
    digits1 = ''.join(random.choices(string.digits, k=2))
    letters1 = ''.join(random.choices(string.ascii_uppercase, k=2))
    letter1 = ''.join(random.choices(string.ascii_uppercase, k=1))
    digits2 = ''.join(random.choices(string.digits, k=2))
    letters2 = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits3 = ''.join(random.choices(string.digits, k=3))

    sku = f"{digits}{digits1}{letters1}-{letter1}{digits2}{letters2}-{digits3}{letters1}"
    return sku


def create_output_df(input_df):
    """创建输出数据框并填充数据。"""
    columns = [
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
        "Cost per item"
    ]

    output_df = pd.DataFrame(columns=columns)
    existing_handles = set()

    # 填充新 DataFrame 的列
    output_df['Link-Href'] = input_df.get('link-href', '')

    # 生成 Handle
    def clean_name(name):
        if pd.notna(name):
            # 清除非字母字符，并将字母转换为小写
            cleaned_name = re.sub(r'[^a-zA-Z\s]', '', name).lower()  # 允许空格
            # 将空格替换为连字符
            cleaned_name = cleaned_name.replace(' ', '-')
            return cleaned_name
        return ""

    # 生成 Handle
    base_handles = input_df['name'].apply(clean_name)  # 清理并转换为小写
    handles = input_df['name'].apply(lambda name: generate_unique_handle(existing_handles) if pd.notna(name) else "")
    output_df['Handle'] = [f"{base}{handle}" for base, handle in zip(base_handles, handles)]

    # 从其他列赋值
    output_df['Title'] = input_df['name']
    output_df['Body (HTML)'] = input_df['details']
    output_df['Collection'] = input_df['title']
    output_df['Vendor'] = input_df['title']
    output_df['Variant Compare At Price'] = input_df['price2']
    output_df['Variant Price'] = input_df['price1']
    output_df['Published'] = 'TRUE'
    output_df['Image Src'] = input_df['src_links'].str.split('#')
    output_df['Variant Weight Unit'] = 'kg'

    # 处理样式列，确保处理 NaN 值
    def safe_split(series):
        return series.fillna('').str.split('#')

    # 处理 Option 列，确保不会输出 NaN
    def handle_option(series):
        return safe_split(series).str[0].fillna('')  # 返回第一个值，若为空则填充为空字符串

    output_df['Option1 Name'] = handle_option(input_df['styles1'])
    output_df['Option1 Value'] = safe_split(input_df['styles1']).str[1:].apply(
        lambda x: x if isinstance(x, list) else []).apply(lambda x: x if len(x) > 0 else [''])

    output_df['Option2 Name'] = handle_option(input_df['styles2'])
    output_df['Option2 Value'] = safe_split(input_df['styles2']).str[1:].apply(
        lambda x: x if isinstance(x, list) else []).apply(lambda x: x if len(x) > 0 else [''])

    output_df['Option3 Name'] = handle_option(input_df['styles3'])
    output_df['Option3 Value'] = safe_split(input_df['styles3']).str[1:].apply(
        lambda x: x if isinstance(x, list) else []).apply(lambda x: x if len(x) > 0 else [''])

    return output_df


# 使用上下文管理器读取现有的 Excel 文件
with pd.ExcelFile(input_file_name) as xls:
    input_df = pd.read_excel(xls)

# 检查所需列是否存在
required_columns = ['title', 'name', 'price1', 'price2', 'details', 'src_links', 'styles1', 'styles2', 'styles3']
from itertools import product

if all(col in input_df.columns for col in required_columns):
    output_df = create_output_df(input_df)

    all_rows = []
    for _, row in tqdm(output_df.iterrows(), total=len(output_df), desc="Processing"):
        option1_values = row['Option1 Value'] or ['']
        option2_values = row['Option2 Value'] or ['']
        option3_values = row['Option3 Value'] or ['']
        image_srcs = row['Image Src'] if isinstance(row['Image Src'], list) else [row['Image Src']]

        # 生成 Option 组合
        combinations = list(product(option1_values, option2_values, option3_values))
        combination_count = len(combinations)
        image_count = len(image_srcs)

        # 计算需要添加的行数
        total_rows = max(combination_count, image_count)

        for i in range(total_rows):
            new_row = row.copy()

            # 处理选项组合
            if i < combination_count:
                combo = combinations[i]
                new_row['Option1 Value'] = combo[0]
                new_row['Option2 Value'] = combo[1]
                new_row['Option3 Value'] = combo[2]
            else:
                new_row['Option1 Value'] = ''
                new_row['Option2 Value'] = ''
                new_row['Option3 Value'] = ''

            # 处理标题和其他字段的逻辑
            if i == 0:
                new_row.update({
                    'Title': row['Title'],
                    'Body (HTML)': row['Body (HTML)'],
                    'Collection': row['Collection'],
                    'Vendor': row['Vendor'],
                    'Option1 Name': row['Option1 Name'],
                    'Option2 Name': row['Option2 Name'],
                    'Option3 Name': row['Option3 Name'],
                    'Published': row['Published'],
                    'Variant SKU': generate_variant_sku(),
                    'Variant Grams': 0,
                    'Variant Inventory Tracker': 'shopify',
                    'Variant Inventory Qty': 999,
                    'Variant Inventory Policy': 'deny',
                    'Variant Fulfillment Service': 'manual',
                    'Variant Requires Shipping': 'TRUE',
                    'Variant Taxable': 'FALSE',
                    'Gift Card': 'FALSE',
                    'SEO Title': row['Title'],
                    'SEO Description': row['Title'],
                })
            else:
                new_row.update({
                    'Title': '',
                    'Body (HTML)': '',
                    'Collection': '',
                    'Vendor': '',
                    'Published': '',
                    'Option1 Name': '',
                    'Option2 Name': '',
                    'Option3 Name': '',
                    'Variant SKU': generate_variant_sku(),
                    'Variant Grams': 0,
                    'Variant Inventory Tracker': 'shopify',
                    'Variant Inventory Qty': 999,
                    'Variant Inventory Policy': 'deny',
                    'Variant Fulfillment Service': 'manual',
                    'Variant Requires Shipping': 'TRUE',
                    'Variant Taxable': 'FALSE',
                })

            # 处理图片链接
            if i < image_count:
                new_row['Image Src'] = image_srcs[i]
                new_row['Image Position'] = i + 1
            else:
                new_row['Image Src'] = None  # 或者设置为默认值
                new_row['Image Position'] = None

            if i >= combination_count:
                # 使用 del 删除 Variant SKU
                if 'Variant SKU' in new_row:
                    del new_row['Variant SKU']
                    del new_row['Variant Grams']
                    del new_row['Variant Inventory Tracker']
                    del new_row['Variant Inventory Qty']
                    del new_row['Variant Inventory Policy']
                    del new_row['Variant Fulfillment Service']
                    del new_row['Variant Price']
                    del new_row['Variant Compare At Price']
                    del new_row['Variant Requires Shipping']
                    del new_row['Variant Taxable']
            all_rows.append(new_row)

    # 创建新的 DataFrame 以保存所有组合
    final_df = pd.DataFrame(all_rows)

    option1_value_split = final_df['Option1 Value'].apply(
        lambda x: x.split('@', 1) if isinstance(x, str) and '@' in x else [x, None])
    final_df['Option1 Value'] = option1_value_split.apply(lambda x: x[0])
    final_df['Variant Image'] = option1_value_split.apply(lambda x: x[1])

    # 保存新的 DataFrame 为 Excel 文件
    final_df.to_excel(output_file_name, index=False)

    print(f'数据已保存到 {output_file_name}')

    # ============ 第二步：拆分 Option1 Value 列 ============
    SOURCE_COL = 11
    TOTAL_COLS = 7
    SPLIT_HEADERS = [
        "Option1 Value", "Option2 Name", "Option2 Value",
        "Option3 Name", "Option3 Value", "Variant Price", "Variant Compare At Price",
    ]

    def split_prices(text):
        parts = text.rsplit("$", 2)
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        return text, "", ""

    def split_option_value(value):
        if value is None:
            return [""] * TOTAL_COLS
        text = str(value)
        option_text, price1, price2 = split_prices(text)
        option_parts = option_text.split("&") if option_text else []
        result = [""] * TOTAL_COLS
        for idx, part in enumerate(option_parts[:5]):
            result[idx] = part
        result[-2] = float(price1) if price1 else ""
        result[-1] = float(price2) if price2 else ""
        return result

    wb = openpyxl.load_workbook(output_file_name)
    ws = wb.active
    insert_at = SOURCE_COL + 1
    ws.insert_cols(insert_at, TOTAL_COLS - 1)
    for offset, header in enumerate(SPLIT_HEADERS):
        ws.cell(row=1, column=SOURCE_COL + offset, value=header)
    for row in range(2, ws.max_row + 1):
        source_value = ws.cell(row=row, column=SOURCE_COL).value
        values = split_option_value(source_value)
        for offset, val in enumerate(values):
            ws.cell(row=row, column=SOURCE_COL + offset, value=val)

    duplicate_option_start_col = SOURCE_COL + len(SPLIT_HEADERS)
    ws.delete_cols(duplicate_option_start_col, 4)

    split_variant_price_col = SOURCE_COL + 5
    split_compare_price_col = SOURCE_COL + 6
    target_variant_price_col = SOURCE_COL + len(SPLIT_HEADERS) + 6
    target_compare_price_col = target_variant_price_col + 1
    for row in range(2, ws.max_row + 1):
        variant_price = ws.cell(row=row, column=split_variant_price_col).value
        compare_price = ws.cell(row=row, column=split_compare_price_col).value
        if compare_price in (None, "", 0, 0.0, "0", "0.0"):
            compare_price = variant_price
        ws.cell(row=row, column=target_variant_price_col, value=variant_price)
        ws.cell(row=row, column=target_compare_price_col, value=compare_price)
    ws.delete_cols(split_variant_price_col, 2)

    # 如果 J 列（Option1 Name）为空，则清空 L 列（Option2 Name）和 N 列（Option3 Name）
    COL_J = 10
    COL_L = 12
    COL_N = 14
    for row in range(2, ws.max_row + 1):
        if not ws.cell(row=row, column=COL_J).value:
            ws.cell(row=row, column=COL_L, value="")
            ws.cell(row=row, column=COL_N, value="")

    wb.save(output_file_name)
    print(f'最终数据已保存到 {output_file_name}')

else:
    print("输入文件中缺少必要的列")
