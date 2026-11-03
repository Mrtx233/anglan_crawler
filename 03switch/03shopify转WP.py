import csv
import time
from pathlib import Path

# ===== 配置：修改此处文件路径 =====
INPUT_FILE = r"D:\C_code\anglan_crawler\A产出\A0701\heroim.com（原价）\thecaselane化妆包5\20260706_175052\thecaselane_原价.csv"
def WPTitle(row):
    title = ''
    if row['Option1 Value'] != "":
        title += "-" + row['Option1 Value']
        if row['Option2 Value'] != "":
            title += "," + row['Option2 Value']
            if row['Option3 Value'] != "":
                title += "," + row['Option3 Value']
    return title


def WPAdd(value, obj):
    if value != "" and value not in obj.split(','):
        obj += "," + value
    return obj


def ShopifyWP(rows, folder_path, filename):
    list_items = {}
    line_number = 0

    for row in rows:
        entity = {}

        if row['Handle'] not in list_items:
            list_items[row['Handle']] = []

            if row['Option1 Value'] != "" and row['Option1 Value'] != "Default Title":
                entity["Type"] = "variable"
                entity["SKU"] = f'SKU{int(time.time())}{line_number}'
            else:
                entity["Type"] = "simple"
                entity["SKU"] = row['Variant SKU']

            entity["Name"] = row['Title']
            entity["Published"] = "1"
            entity["Visibility in catalog"] = "visible"
            entity["Description"] = row['Body (HTML)']
            entity["In stock?"] = "1"
            entity["Stock"] = "99999"

            entity["Sale price"] = row['Variant Price']
            entity["Regular price"] = row['Variant Compare At Price'] if row['Variant Compare At Price'] != '' else row[
                'Variant Price']
            entity["Categories"] = row['Collection'] if row['Collection'] != '' else row['Type']
            entity["Tags"] = row['Tags']
            entity["Images"] = row['Image Src']
            entity["Parent"] = ""
            entity["Position"] = "0"
            entity["Attribute 1 name"] = "" if row['Option1 Name'] == 'Title' else row['Option1 Name']
            entity["Attribute 1 value(s)"] = "" if row['Option1 Value'] == 'Default Title' else row['Option1 Value']
            entity["Attribute 1 visible"] = "1" if entity["Attribute 1 name"] != "" else ""
            entity["Attribute 1 global"] = "1" if entity["Attribute 1 name"] != "" else ""
            entity["Attribute 2 name"] = row['Option2 Name']
            entity["Attribute 2 value(s)"] = row['Option2 Value']
            entity["Attribute 2 visible"] = "1" if row['Option2 Name'] != "" else ""
            entity["Attribute 2 global"] = "1" if row['Option2 Name'] != "" else ""
            entity["Attribute 3 name"] = row['Option3 Name']
            entity["Attribute 3 value(s)"] = row['Option3 Value']
            entity["Attribute 3 visible"] = "1" if row['Option3 Name'] != "" else ""
            entity["Attribute 3 global"] = "1" if row['Option3 Name'] != "" else ""

            list_items[row['Handle']].append(entity)

            if entity["Type"] == "variable":
                variation_entity = {}
                variation_entity["Type"] = "variation"
                variation_entity["SKU"] = row['Variant SKU']
                variation_entity["Name"] = list_items[row['Handle']][0]["Name"] + WPTitle(row)
                variation_entity["Published"] = "1"
                variation_entity["Visibility in catalog"] = "visible"
                variation_entity["Description"] = ""
                variation_entity["In stock?"] = "1"
                variation_entity["Stock"] = "99999"
                variation_entity["Sale price"] = row['Variant Price']
                variation_entity["Regular price"] = row['Variant Compare At Price'] if row[
                                                                                           'Variant Compare At Price'] != '' else \
                    row['Variant Price']
                variation_entity["Categories"] = ""
                variation_entity["Tags"] = ''
                variation_entity["Images"] = row['Variant Image']
                variation_entity["Parent"] = list_items[row['Handle']][0]["SKU"]
                variation_entity["Position"] = len(list_items[row['Handle']])
                variation_entity["Attribute 1 name"] = list_items[row['Handle']][0]["Attribute 1 name"]
                variation_entity["Attribute 1 value(s)"] = row['Option1 Value']
                variation_entity["Attribute 1 visible"] = ""
                variation_entity["Attribute 1 global"] = "1" if row['Option1 Value'] != "" else ""
                variation_entity["Attribute 2 name"] = list_items[row['Handle']][0]["Attribute 2 name"]
                variation_entity["Attribute 2 value(s)"] = row['Option2 Value']
                variation_entity["Attribute 2 visible"] = ""
                variation_entity["Attribute 2 global"] = "1" if row['Option2 Value'] != "" else ""
                variation_entity["Attribute 3 name"] = list_items[row['Handle']][0]["Attribute 3 name"]
                variation_entity["Attribute 3 value(s)"] = row['Option3 Value']
                variation_entity["Attribute 3 visible"] = ""
                variation_entity["Attribute 3 global"] = "1" if row['Option3 Value'] != "" else ""

                list_items[row['Handle']].append(variation_entity)
        else:
            if row['Option1 Value'] != "" and row['Option1 Value'] != "Default Title":
                variation_entity = {}
                variation_entity["Type"] = "variation"
                variation_entity["SKU"] = row['Variant SKU']
                variation_entity["Name"] = list_items[row['Handle']][0]["Name"] + WPTitle(row)
                variation_entity["Published"] = "1"
                variation_entity["Visibility in catalog"] = "visible"
                variation_entity["Description"] = ""
                variation_entity["In stock?"] = "1"
                variation_entity["Stock"] = "99999"
                variation_entity["Sale price"] = row['Variant Price']
                variation_entity["Regular price"] = row['Variant Compare At Price'] if row[
                                                                                           'Variant Compare At Price'] != '' else \
                    row['Variant Price']
                variation_entity["Categories"] = ""
                variation_entity["Tags"] = ''
                variation_entity["Images"] = row['Variant Image']
                variation_entity["Parent"] = list_items[row['Handle']][0]["SKU"]
                variation_entity["Position"] = len(list_items[row['Handle']])
                variation_entity["Attribute 1 name"] = list_items[row['Handle']][0]["Attribute 1 name"]
                variation_entity["Attribute 1 value(s)"] = row['Option1 Value']
                variation_entity["Attribute 1 visible"] = ""
                variation_entity["Attribute 1 global"] = "1" if row['Option1 Value'] != "" else ""
                variation_entity["Attribute 2 name"] = list_items[row['Handle']][0]["Attribute 2 name"]
                variation_entity["Attribute 2 value(s)"] = row['Option2 Value']
                variation_entity["Attribute 2 visible"] = ""
                variation_entity["Attribute 2 global"] = "1" if row['Option2 Value'] != "" else ""
                variation_entity["Attribute 3 name"] = list_items[row['Handle']][0]["Attribute 3 name"]
                variation_entity["Attribute 3 value(s)"] = row['Option3 Value']
                variation_entity["Attribute 3 visible"] = ""
                variation_entity["Attribute 3 global"] = "1" if row['Option3 Value'] != "" else ""

                list_items[row['Handle']].append(variation_entity)

                list_items[row['Handle']][0]["Images"] = WPAdd(row['Image Src'], list_items[row['Handle']][0]["Images"])
                list_items[row['Handle']][0]["Attribute 1 value(s)"] = WPAdd(row['Option1 Value'],
                                                                             list_items[row['Handle']][0][
                                                                                 "Attribute 1 value(s)"])
                list_items[row['Handle']][0]["Attribute 2 value(s)"] = WPAdd(row['Option2 Value'],
                                                                             list_items[row['Handle']][0][
                                                                                 "Attribute 2 value(s)"])
                list_items[row['Handle']][0]["Attribute 3 value(s)"] = WPAdd(row['Option3 Value'],
                                                                             list_items[row['Handle']][0][
                                                                                 "Attribute 3 value(s)"])
            else:
                list_items[row['Handle']][0]["Images"] = WPAdd(row['Image Src'], list_items[row['Handle']][0]["Images"])

        line_number += 1

    if list_items:
        folder_path = Path(folder_path)
        csv_fname = folder_path / f"wp-{filename}"  # 使用 / 运算符拼接

        csv_head = ["Type", "SKU", "Name", "Published", "Visibility in catalog", "Description", "In stock?", "Stock",
                    "Sale price", "Regular price", "Categories", "Tags", "Images", "Parent", "Position",
                    "Attribute 1 name", "Attribute 1 value(s)", "Attribute 1 visible", "Attribute 1 global",
                    "Attribute 2 name", "Attribute 2 value(s)", "Attribute 2 visible", "Attribute 2 global",
                    "Attribute 3 name", "Attribute 3 value(s)", "Attribute 3 visible", "Attribute 3 global"]

        with open(csv_fname, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_head)
            writer.writeheader()

            for handle, items in list_items.items():
                for item in items:
                    writer.writerow(item)

        print(f'WP文件 {csv_fname} 已生成！')


def main():
    # 输入完整文件路径
    input_path = Path(INPUT_FILE)

    # 用于存储从CSV文件读取的数据
    rows = []

    # 打开CSV文件并读取数据
    with input_path.open(newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(dict(row))  # 将每一行转换为字典并添加到列表中

    # 调用 ShopifyWP 函数，将读取的数据传递进去
    ShopifyWP(rows, input_path.parent, input_path.name)


if __name__ == "__main__":
    main()
