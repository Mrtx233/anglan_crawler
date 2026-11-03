# not_shopify 技术文档

`not_shopify` 是一个 Scrapy 项目，用于处理没有可用 Shopify 商品 JSON 接口、需要 JS 渲染或需要自定义 XPath 的商品页。

当前仓库实际启用的 Spider 是：

```text
not_shopify/not_shopify/spiders/quince.py
```

旧文档中提到的 `baggu.py` 当前不在仓库中，不应作为运行入口。

## 1. 项目结构

```text
not_shopify/
├─ scrapy.cfg
└─ not_shopify/
   ├─ items.py
   ├─ middlewares.py
   ├─ pipelines.py
   ├─ settings.py
   ├─ shopify_converter.py
   ├─ utils.py
   └─ spiders/
      └─ quince.py
```

## 2. 运行

```powershell
cd D:\C_code\anglan_crawler\not_shopify
scrapy list
scrapy crawl quince
```

`quince.py` 顶部包含：

```python
INPUT_FILE = PROJECT_ROOT / "../01xlsx/quince.xlsx"
TEST_MODE = False
TEST_COUNT = 10
```

输入表的第 1 列是分类名，第 2 列是商品 URL，从第 2 行读取。测试时可把 `TEST_MODE` 改为 `True`。

## 3. Selenium 下载中间件

`SeleniumDownloaderMiddleware` 在 Scrapy 启动时创建 Chrome：

- 关闭自动化提示并隐藏 `navigator.webdriver`。
- 使用 `webdriver-manager` 获取 ChromeDriver。
- 打开请求 URL。
- 等待 `request.meta["wait_xpath"]`，没有配置时等待 `body`。
- 额外等待 `wait_extra` 秒。
- 读取最终 `outerHTML`。
- 按 `PAGE_RANDOM_WAIT_MIN` 到 `PAGE_RANDOM_WAIT_MAX` 随机等待。
- 返回 Scrapy `HtmlResponse`。

Spider 通过 `meta` 传递等待参数：

```python
meta={
    "category": category,
    "wait_xpath": XPATH_NAME,
    "wait_extra": 3,
}
```

关键配置：

```python
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
SELENIUM_REQUEST_TIMEOUT = 30
PAGE_RANDOM_WAIT_MIN = 2.0
PAGE_RANDOM_WAIT_MAX = 4.0
```

## 4. 空数据重试

`ValidateSpiderMiddleware` 检查以下字段：

```text
title, name, price1, price2,
styles1, styles2, styles3, src_links, details
```

`link_href` 只表示请求 URL，不参与“页面是否提取成功”的判断。

当连续 3 个结果的核心字段全部为空时：

1. 记录失败请求。
2. 重启 Selenium 浏览器。
3. 重新排队失败请求。
4. 清空连续失败计数。

## 5. Quince Spider

`quince.py` 使用 XPath 提取：

| 配置 | 当前用途 |
|---|---|
| `XPATH_NAME` | 商品名 |
| `XPATH_PRICE1` | 销售价 |
| `XPATH_PRICE2` | 原价 |
| `XPATH_STYLES1` | 选项标签 |
| `XPATH_DETAILS` | 商品描述段落 |

Spider 的处理逻辑：

1. 使用 `read_quince_targets()` 读取 Excel。
2. 生成 Scrapy Request。
3. Selenium 等待商品名出现。
4. 使用 `get_text()`、`get_texts()` 提取文本。
5. 使用 `extract_price()` 提取数字价格。
6. 将 `Color: White` 规范化为 `Color#White`。
7. 从 `__NEXT_DATA__` 提取商品图片，失败时回退到 DOM `srcSet`。
8. 生成 `NotShopifyItem`。

Quince 图片处理会尝试：

- 从 `script#__NEXT_DATA__` 中读取商品图片 JSON。
- 按页面中的图片 ID 匹配高清图。
- 将 `images.ctfassets.net` 地址转换为 `images.quince.com`。
- 追加 `w=600`、`h=750`、`q=50` 和 `reqOrigin=website-ssr` 参数。
- 多张图片用 `#` 连接。

## 6. Pipeline 输出

`NotShopifyPipeline` 在以下目录创建时间戳目录：

```text
not_shopify/output/<YYYYMMDD_HHMMSS>/
```

正常运行会输出：

```text
quince.csv
quince.xlsx
quince_原价.xlsx
quince_原价_拆分.xlsx
```

CSV 编码为 `utf-8-sig`。Pipeline 会先输出统一 10 列，再调用 `shopify_converter.py` 生成 Shopify 表和选项拆分表。

## 7. 转换规则

`shopify_converter.py` 会：

1. 检查统一字段是否齐全。
2. 生成 Shopify 标准列。
3. 根据 `styles1`、`styles2`、`styles3` 的 `#` 分隔内容提取选项。
4. 根据选项组合和图片数量展开行。
5. 生成变体 SKU。
6. 把 `@image` 从选项值拆出到 `Variant Image`。
7. 写出 Shopify 原价表。
8. 将 `Option1 Value` 中的组合、价格和比较价拆成标准列。

与 `shopify_json` 不同，`not_shopify` 不执行内置价格库匹配；价格匹配可在后续使用 `03switch` 工具完成。

## 8. 新增非 Shopify Spider

建议复制 `quince.py` 后按以下步骤修改：

1. `name` 和 `allowed_domains`。
2. `INPUT_FILE`、`TEST_MODE` 和 `TEST_COUNT`。
3. 商品名、价格、选项、详情的 XPath。
4. `request.meta` 中的等待 XPath 和等待时间。
5. `parse()` 中的站点特殊逻辑。
6. 如果图片来自 JSON 或懒加载数据，将逻辑放入 `utils.py` 的独立函数。

Spider 必须生成以下字段：

```text
title, name, price1, price2,
styles1, styles2, styles3,
src_links, link_href, details
```

Pipeline 会把内部字段 `link_href` 写成表头 `link-href`。

## 9. 常见问题

- 页面打开但字段为空：先检查 `wait_xpath` 和 XPath 是否仍匹配当前页面。
- 连续触发浏览器重启：检查反爬、加载等待时间和页面是否需要登录。
- 图片为空：检查 `__NEXT_DATA__` 路径、图片 ID XPath 或 DOM `srcSet`。
- ChromeDriver 启动失败：确认 Chrome 已安装，并清理 webdriver-manager 缓存后重试。
- 输出目录与预期不同：以当前 Pipeline 的 `output` 相对项目目录为准，不要套用旧文档中的固定绝对路径。
