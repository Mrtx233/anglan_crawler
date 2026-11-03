# shopify_json 技术文档

`shopify_json` 是一个 Scrapy 项目，面向标准 Shopify 商品页。它不依赖 DOM 选择器抓商品详情，而是把商品 URL 转为 `.json` 地址，读取 `product` 数据并生成统一商品表。

## 1. 项目结构

```text
shopify_json/
├─ scrapy.cfg
└─ shopify_json/
   ├─ items.py
   ├─ middlewares.py
   ├─ pipelines.py
   ├─ settings.py
   ├─ utils/
   │  ├─ json_variants.py
   │  └─ shopify_converter.py
   └─ spiders/
      ├─ 当前站点 Spider
      └─ Historical/       历史站点 Spider
```

当前目录有 11 个非归档 Spider；`Historical` 中保存大量已接入过的站点模板。

## 2. 运行

```powershell
cd D:\C_code\anglan_crawler\shopify_json
scrapy list
scrapy crawl workinstyleboutique
```

每个 Spider 文件顶部配置：

```python
INPUT_FILE = PROJECT_ROOT / "01xlsx/..."
TEST_MODE = False
TEST_COUNT = 10
SKIP_POSITIONS = None
SKIP_OPTIONS = None
```

首次运行建议将 `TEST_MODE` 设为 `True`，确认少量结果后再全量运行。

## 3. 请求和去重

Spider 从 Excel 读取 `(title, url)`，然后：

1. 去掉商品 URL 的 query 和 fragment，保留原始商品 URL。
2. 把路径规范化为 `.json`。
3. 按 JSON URL 去重。
4. 对每个唯一商品发起 Scrapy 请求。

Spider 对 HTTP 429 做延迟重试，最多 5 次；重试延迟为 `30 * retry_count` 秒，并使用 `DontCloseSpider` 防止重试请求尚未入队时提前结束。

`settings.py` 的关键配置：

```python
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1
ITEM_PIPELINES = {
    "shopify_json.pipelines.ShopifyJsonPipeline": 300,
}
```

## 4. JSON 解析

`json_variants.py` 提供以下核心逻辑：

- `find_fallback_variant()`：优先取 `position == 1` 的变体。
- `get_sorted_options()`：按 option position 排序，只保留多值选项，并优先把 `Color` 放在第一项。
- `build_option_combos()`：生成选项笛卡尔积。
- `find_variant_by_combo()`：按 option position 匹配实际变体。
- `build_variant_combo()`：生成 `styles1`。
- `build_first_image_srcs()`：提取前若干商品图。
- `clean_body_html()`：移除链接标签并清洁商品描述 HTML。

`styles1` 的 segment 格式：

```text
第一选项值&第二选项名&第二选项值&第三选项名&第三选项值$price1$price2@variant_image
```

多个 segment 用 `#` 连接，第一段前可带 option 名：

```text
Color#Red$19.99$29.99@https://example.com/red.jpg#Blue$19.99$29.99@https://example.com/blue.jpg
```

## 5. 价格和图片

商品价格可能来自整数分值或带小数的字符串。`format_price()` 会：

- 空值返回空字符串。
- 无小数点时按 Shopify JSON 的分值转换为金额。
- 保留最多两位小数，并去除无意义的尾零。

代码会调用 `https://open.er-api.com/v6/latest/USD` 获取汇率，并将已识别的非 USD 价格换算为 USD。汇率只在当前进程内缓存；请求失败时保留原值。

图片 URL 会根据文件扩展名插入 `_600x600` 尺寸后缀。`SKIP_POSITIONS` 可跳过指定图片 position，`SKIP_OPTIONS` 可按 option 名称过滤选项。

## 6. Pipeline 输出

`ShopifyJsonPipeline` 在 Spider 启动时创建：

```text
shopify_json/shopify_json/output/<输入文件父目录名>/<输入文件名去扩展名>/<时间戳>/
```

输出文件：

```text
<spider>_styles.xlsx
<spider>_原价.xlsx
<spider>_Shopify_原价.xlsx
<spider>_Shopify_价格匹配.xlsx
<spider>_Shopify_未匹配到的价格.xlsx
```

具体文件名会受输入文件 stem 和转换器命名规则影响；同时会在 `xlsx`、`csv` 子目录生成相应 CSV/XLSX。

Pipeline 会把 `src_links` 中的图片与 styles 中的 `@image` 合并去重，普通图片最多取 5 张。

## 7. Shopify 转换器

`utils/shopify_converter.py` 的转换步骤：

1. 检查 9 个输入字段：`title`、`name`、`price1`、`price2`、`details`、`src_links`、`styles1`、`styles2`、`styles3`。
2. 生成 Shopify 导入所需的标准列。
3. 按选项组合和图片数量展开多行。
4. 生成唯一 Handle 和变体 SKU。
5. 将商品信息写入第一行，将后续变体的商品级字段留空。
6. 解析 `Option1 Value` 中的选项、价格和变体图片。
7. 按 `Handle` 分组，用内置价格库匹配新价格。
8. 输出匹配结果和未使用价格列表。

匹配规则：

- 每个商品按 `Handle` 分组。
- 变体按原价从低到高处理。
- 候选价格必须位于原价的 `0.75 ~ 1.25` 倍范围内。
- 同一运行中同一个价格只使用一次。
- 匹配不到的价格写入“未匹配到的价格”文件。

## 8. 新增 Shopify Spider

推荐复制一个当前 Spider，再修改：

1. `name`
2. `allowed_domains`
3. `INPUT_FILE`
4. `TEST_MODE` / `TEST_COUNT`
5. `SKIP_POSITIONS` / `SKIP_OPTIONS`

标准 `parse_json()` 应该至少生成：

```python
{
    "title": ...,
    "name": ...,
    "price1": ...,
    "price2": ...,
    "styles1": ...,
    "styles2": "",
    "styles3": "",
    "src_links": ...,
    "link-href": ...,
    "details": ...,
}
```

如果商品页不能访问 `/<product-path>.json`，或者数据只在前端状态树中，需要改用 `not_shopify`。

## 9. 独立脚本

`02crawler/Json_Crawl/run2.py` 是不依赖项目内部导入的独立采集脚本：

```powershell
python 02crawler\Json_Crawl\run2.py "D:\path\products.xlsx" `
  --output "D:\path\products.csv" `
  --skip-positions 1,3
```

它使用 DrissionPage，支持：

- `.json` URL 转换
- 重复商品去重
- 429 和其他请求失败重试
- 已有 CSV 的断点续传
- 每 20 条增量保存
- 图片 position 跳过

该脚本使用独立浏览器配置和本地代理，不能把它的输出目录规则与 Scrapy Pipeline 混为一谈。
