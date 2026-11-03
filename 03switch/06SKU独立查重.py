"""
06SKU独立查重.py
读取 wp-*.csv，检查并打印所有重复的 SKU（variable 和 variation 均检查）。

用法:
    python 06SKU独立查重.py <wp文件路径>
    python 06SKU独立查重.py                         # 使用下方默认路径
"""

import csv
import sys
from collections import Counter
from pathlib import Path


# ===== 配置：修改此处文件路径 =====
INPUT_FILE = r"C:\Users\Mrtx0\Desktop\新建文件夹\wp-sexikinis_价格匹配.csv"


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

    # ── 读取所有行 ──
    rows = []
    with open(input_path, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total = len(rows)

    # ── 分类型统计 SKU ──
    sku_rows = {}   # sku -> list[(行号, Type, Name)]
    for i, row in enumerate(rows, start=2):  # 行号从 2 开始（跳过表头）
        sku = row.get("SKU", "").strip()
        if not sku:
            continue
        if sku not in sku_rows:
            sku_rows[sku] = []
        sku_rows[sku].append((i, row.get("Type", ""), row.get("Name", "")))

    # ── 找出重复 ──
    duplicates = {sku: entries for sku, entries in sku_rows.items() if len(entries) > 1}

    # ── 统计概览 ──
    parent_count = sum(1 for r in rows if r.get("Type", "") in ("variable", "simple"))
    variation_count = sum(1 for r in rows if r.get("Type", "") == "variation")
    unique_skus = len(sku_rows)
    total_skus = sum(len(v) for v in sku_rows.values())

    print(f"\n{'='*60}")
    print(f"总行数: {total}")
    print(f"  variable/simple: {parent_count}")
    print(f"  variation:       {variation_count}")
    print(f"总 SKU 数: {total_skus}")
    print(f"唯一 SKU 数: {unique_skus}")
    print(f"重复 SKU 数: {len(duplicates)}")
    print(f"{'='*60}")

    if not duplicates:
        print("\n没有重复 SKU。")
        return

    # ── 分类打印重复 ──
    parent_dups = {}
    variation_dups = {}

    for sku, entries in duplicates.items():
        types = {e[1] for e in entries}
        if "variable" in types or "simple" in types:
            parent_dups[sku] = entries
        else:
            variation_dups[sku] = entries

    if parent_dups:
        print(f"\n--- 重复的 variable/simple SKU ({len(parent_dups)} 个) ---")
        for sku, entries in sorted(parent_dups.items()):
            print(f"\n  SKU: {sku} (出现 {len(entries)} 次)")
            for line_no, typ, name in entries:
                print(f"    行 {line_no}: Type={typ}, Name={name[:50]}")

    if variation_dups:
        print(f"\n--- 重复的 variation SKU ({len(variation_dups)} 个) ---")
        for sku, entries in sorted(variation_dups.items()):
            print(f"\n  SKU: {sku} (出现 {len(entries)} 次)")
            for line_no, typ, name in entries:
                parent = ""
                for r in rows:
                    if r.get("SKU", "").strip() == sku:
                        parent = r.get("Parent", "")
                        break
                print(f"    行 {line_no}: Name={name[:50]}, Parent={parent}")

    # ── 额外检查：孤立变体（Parent 指向不存在的父级） ──
    parent_skus = {r["SKU"] for r in rows if r.get("Type", "") in ("variable", "simple")}
    orphans = [
        (i, r) for i, r in enumerate(rows, start=2)
        if r.get("Type", "") == "variation" and r.get("Parent", "").strip() not in parent_skus
    ]
    if orphans:
        print(f"\n--- 孤立变体（Parent 无对应父级）: {len(orphans)} 个 ---")
        for line_no, r in orphans[:20]:
            print(f"  行 {line_no}: SKU={r['SKU']}, Parent={r['Parent']}, Name={r.get('Name','')[:40]}")
        if len(orphans) > 20:
            print(f"  ... 还有 {len(orphans) - 20} 个")


if __name__ == "__main__":
    main()
