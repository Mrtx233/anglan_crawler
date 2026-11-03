import pandas as pd
import random
from pathlib import Path

# 新价格库
price_library = [
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

# 将价格库排序（从小到大）
price_library_sorted = sorted(price_library)

# ===== 配置：修改此处文件路径 =====
INPUT_FILE = r"C:\Users\Mrtx0\Desktop\andieswim_原价.xlsx"
input_path = Path(INPUT_FILE)

input_folder = input_path.parent
filename = input_path.name
source_stem = input_path.stem
if source_stem.endswith('_待匹配'):
    output_stem = source_stem[:-len('_待匹配')]
elif source_stem.endswith('_原价_拆分'):
    output_stem = source_stem[:-len('_原价_拆分')]
else:
    output_stem = source_stem

# 读取Excel文件（保留所有行）
df = pd.read_excel(input_path)
# 重置索引确保是整数
df = df.reset_index(drop=True)

# 初始化匹配列为空
df['匹配价格'] = None

# 全局已使用价格集合
global_used_prices = set()

# 按Handle分组处理
for handle, group in df.groupby('Handle'):
    # 跳过空Handle
    if pd.isna(handle):
        continue

    # 获取该组中有效的价格数据（跳过空价格）
    valid_rows = []
    for idx, row in group.iterrows():
        price = row['Variant Price']
        if pd.isna(price):
            continue
        try:
            price = float(price)
            valid_rows.append((idx, price))
        except (ValueError, TypeError):
            continue

    # 如果没有有效价格，跳过该组
    if not valid_rows:
        continue

    # 按原价格从低到高排序
    valid_rows_sorted = sorted(valid_rows, key=lambda x: x[1])

    # 获取该组可用的价格库（排除全局已使用的）
    available_prices = [p for p in price_library_sorted if p not in global_used_prices]

    # 为排序后的每个价格匹配
    for position, (idx, original_price) in enumerate(valid_rows_sorted):
        # 计算价格范围
        lower_bound = original_price * 0.75
        upper_bound = original_price * 1.25

        # 在可用价格中查找候选（按顺序从低到高查找）
        candidates = [p for p in available_prices if lower_bound <= p <= upper_bound]

        if candidates:
            # 选择第一个匹配的（最小的匹配价格）
            matched = candidates[0]
            global_used_prices.add(matched)
            # 从可用价格列表中移除已使用的价格
            available_prices.remove(matched)
            df.at[idx, '匹配价格'] = matched


# 计算未被匹配的价格
unused_prices = [p for p in price_library_sorted if p not in global_used_prices]

# 输出新文件
output_filename = f'{output_stem}_价格匹配{input_path.suffix}'
output_path = input_folder / output_filename
df.to_excel(output_path, index=False)

print(f"\n处理完成: {filename} -> {output_filename}")
print(f"已使用价格数量: {len(global_used_prices)}")
print(f"未使用价格数量: {len(unused_prices)}")

# 保存未匹配价格信息到单独文件（每个价格占一行）
if unused_prices:
    # 创建DataFrame，每个价格占一行
    unused_df = pd.DataFrame({
        '未匹配价格': unused_prices
    })
    unused_filename = f'{output_stem}_未匹配到的价格{input_path.suffix}'
    not_found_output = input_folder / unused_filename
    unused_df.to_excel(not_found_output, index=False)
    print(f"未匹配价格信息已保存到: {not_found_output} (共{len(unused_prices)}个价格)")
else:
    print("所有价格都已成功匹配")
