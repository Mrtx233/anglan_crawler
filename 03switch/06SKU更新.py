"""
06SKU更新.py
读取 wp-*.csv，用原始生成逻辑完全替换所有 SKU（父级 + 变体），
保持 Parent 引用关系正确。

用法:
    python 06SKU更新.py <wp文件路径>
    python 06SKU更新.py                         # 使用下方默认路径

输出: 在同目录下生成 {原文件名}_新SKU.csv
"""

import csv
import random
import string
import sys
import time
from pathlib import Path


# ===== 配置：修改此处文件路径 =====
INPUT_FILE = r"C:\Users\Mrtx0\Desktop\新建文件夹\wp-sexikinis_价格匹配.csv"


# ── 原始 SKU 生成逻辑（来自 01转shopify.py） ─────────────────────────
def generate_variant_sku(used_skus=None):
    """生成随机变体 SKU，格式: 3位-5位-6位 字母数字混合，自动去重"""
    while True:
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
        if used_skus is None or sku not in used_skus:
            if used_skus is not None:
                used_skus.add(sku)
            return sku


# ── 原始父级 SKU 生成逻辑（来自 03shopify转WP.py） ───────────────────
def generate_parent_sku(line_number, used_skus=None):
    """生成父级 SKU，格式: SKU{时间戳}{行号}，自动去重"""
    while True:
        sku = f"SKU{int(time.time())}{line_number}"
        if used_skus is None or sku not in used_skus:
            if used_skus is not None:
                used_skus.add(sku)
            return sku
        line_number += 1


def detect_encoding(path):
    """尝试 utf-8-sig，失败则回退 gbk"""
    for enc in ("utf-8-sig", "gbk", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "utf-8-sig"

def main():
    input_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else INPUT_FILE
    )

    encoding = detect_encoding(input_path)
    print(f"读取: {input_path} (编码: {encoding})")

    # ── 第一遍：读取所有行 ──
    rows = []
    with open(input_path, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    print(f"总行数: {len(rows)}")

    # ── 第二遍：更新 SKU（带去重） ──
    old_to_new_parent = {}   # 旧父级 SKU → 新父级 SKU
    used_skus = set()        # 已生成的所有 SKU
    line_number = 0
    parent_count = 0
    variation_count = 0

    for row in rows:
        row_type = row.get("Type", "").strip()

        if row_type in ("variable", "simple"):
            old_sku = row["SKU"]
            new_sku = generate_parent_sku(line_number, used_skus)
            row["SKU"] = new_sku
            old_to_new_parent[old_sku] = new_sku
            parent_count += 1

        elif row_type == "variation":
            row["SKU"] = generate_variant_sku(used_skus)
            old_parent = row.get("Parent", "").strip()
            if old_parent in old_to_new_parent:
                row["Parent"] = old_to_new_parent[old_parent]
            variation_count += 1

        line_number += 1

    total = parent_count + variation_count
    unique = len(used_skus)
    print(f"更新: {parent_count} 个父级 SKU, {variation_count} 个变体 SKU")
    if unique < total:
        print(f"警告: 存在 {total - unique} 个重复 SKU！")
    else:
        print(f"验证: {unique} 个 SKU 全部唯一")

    # ── 输出 ──
    output_path = input_path.parent / f"{input_path.stem}_新SKU.csv"
    with open(output_path, "w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"输出: {output_path}")


if __name__ == "__main__":
    main()
