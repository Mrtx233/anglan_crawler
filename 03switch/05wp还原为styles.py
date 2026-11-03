"""
将 wp-*.csv（WooCommerce 格式）一步还原为 _styles.xlsx 格式。
合并了 wp→shopify→styles 两步操作。

用法:
    python 05wp还原为styles.py <wp文件路径>
    python 05wp还原为styles.py                         # 使用下方默认路径

输出: 在同目录下生成 {文件名去掉wp-前缀}_styles.xlsx
"""

import csv
import sys
from pathlib import Path

import openpyxl


# ===== 配置：修改此处文件路径 =====
INPUT_FILE = r"D:\C_code\anglan_crawler\A产出\cytheras.com\sexikinis\合并\wp-sexikinis_原价.csv"


# ── _styles.xlsx 的 10 列 ────────────────────────────────────────────
STYLES_HEADERS = [
    "title", "name", "price1", "price2",
    "styles1", "styles2", "styles3",
    "src_links", "link-href", "details",
]


def format_price(val):
    """将价格值格式化为干净的数字字符串"""
    if val is None or str(val).strip() == "":
        return "0"
    s = str(val).strip()
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
        return str(f)
    except ValueError:
        return s


def parse_wp_csv(input_path):
    """
    读取 wp CSV，按商品分组。
    返回 list[dict]，每个 dict 包含 parent（父行）和 variations（变体行列表）。
    """
    products = []
    sku_to_product = {}

    with open(input_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_type = row.get("Type", "").strip()

            if row_type in ("variable", "simple"):
                prod = {"parent": row, "variations": []}
                products.append(prod)
                sku_to_product[row["SKU"]] = prod

            elif row_type == "variation":
                parent_sku = row.get("Parent", "").strip()
                prod = sku_to_product.get(parent_sku)
                if prod:
                    prod["variations"].append(row)

    return products


def build_styles_segment(var):
    """
    从 WP variation 行直接构建 styles1 的一个 segment。
    格式: opt1_val&opt2_name&opt2_val&opt3_name&opt3_val$price1$price2@image
    """
    parts = [var.get("Attribute 1 value(s)", "") or ""]
    for name_key, val_key in [("Attribute 2 name", "Attribute 2 value(s)"),
                               ("Attribute 3 name", "Attribute 3 value(s)")]:
        opt_name = var.get(name_key, "") or ""
        opt_val = var.get(val_key, "") or ""
        if opt_name and opt_val:
            parts.extend([opt_name, opt_val])
    opt_text = "&".join(parts)

    p1 = format_price(var.get("Sale price", ""))
    p2 = format_price(var.get("Regular price", ""))
    img = (var.get("Images", "") or "").split(",")[0].strip()

    segment = f"{opt_text}${p1}${p2}"
    if img:
        segment += f"@{img}"
    return segment


def reconstruct_product(prod):
    """
    从一个 WP 商品组（parent + variations）还原出一条 _styles.xlsx 行。
    """
    p = prod["parent"]
    variations = prod["variations"]
    product = {h: "" for h in STYLES_HEADERS}

    # ── 商品级字段 ──
    product["name"] = p.get("Name", "")
    product["details"] = p.get("Description", "")
    product["title"] = p.get("Categories", "")
    product["link-href"] = p.get("Link-Href", "")

    # price1/price2 取第一个变体的价格
    if variations:
        product["price1"] = variations[0].get("Sale price", "")
        product["price2"] = variations[0].get("Regular price", "")
    else:
        product["price1"] = p.get("Sale price", "")
        product["price2"] = p.get("Regular price", "")

    # ── 重建 styles1 ──
    option1_name = p.get("Attribute 1 name", "")
    segments = []
    for var in variations:
        opt1_val = var.get("Attribute 1 value(s)", "")
        if not opt1_val or opt1_val == "Default Title":
            continue
        segments.append(build_styles_segment(var))

    if option1_name and segments:
        product["styles1"] = f"{option1_name}#{'#'.join(segments)}"
    elif segments:
        product["styles1"] = "#".join(segments)

    # ── 重建 src_links ──
    # 父行 Images 字段（逗号分隔）转为 # 分隔
    parent_images = p.get("Images", "") or ""
    if parent_images:
        imgs = [img.strip() for img in parent_images.split(",") if img.strip()]
        product["src_links"] = "#".join(imgs)

    return product

def main():
    input_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else INPUT_FILE
    )

    print(f"读取: {input_path}")
    products = parse_wp_csv(input_path)
    print(f"解析到 {len(products)} 个商品")

    # 输出文件名：去掉 wp- 前缀，加 _styles.xlsx
    stem = input_path.stem
    if stem.startswith("wp-"):
        stem = stem[3:]
    output_path = input_path.parent / f"{stem}_styles.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = stem[:31]
    ws.append(STYLES_HEADERS)

    for prod in products:
        product = reconstruct_product(prod)
        ws.append([product.get(h, "") for h in STYLES_HEADERS])

    wb.save(output_path)
    print(f"输出: {output_path} ({ws.max_row - 1} 行)")


if __name__ == "__main__":
    main()
