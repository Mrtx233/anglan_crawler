# anglan_crawler

面向跨境电商选品与铺货的**商品数据采集与格式转换工具集**。它解决的是一条完整业务链路：从若干品牌官网把商品明细抓下来，统一成一套内部字段，再转换成 Shopify / WooCommerce 可直接导入的表格，并按价格库完成改价。

项目不是单一程序，而是四个阶段各司其职的脚本与两个 Scrapy 子项目的集合，阶段之间**以 Excel / CSV 文件为交接契约**，可以单独运行任意一段。

## 流水线总览

```text
① 链接采集          ② 详情采集              ③ 格式转换 + 改价        ④ 平台导入
02crawler/detail_link  ──►  shopify_json / not_shopify  ──►  03switch  ──►  Shopify / WooCommerce
（分类页 → 商品URL）      （商品URL → 10列统一字段）      （统一字段 → 平台表）    （CSV 直接上传）
        │                                                          │
        └── 输出 title,link 两列 xlsx ──► 作为 ② 的输入表 ─────────┘
```

| 阶段 | 目录 | 输入 | 输出 |
|---|---|---|---|
| ① 链接采集 | `02crawler/detail_link/` | 分类页 URL（写在脚本顶部配置里） | `<域名>.xlsx`，两列 `title,link` |
| ① 详情采集（早期版本） | `02crawler/Crawl/` | 商品 URL 表 | 10 列统一字段 CSV/XLSX |
| ② 详情采集（主力） | `shopify_json/` | 商品 URL 表 | `<spider>_styles.xlsx` + Shopify 原价表 + 价格匹配表 |
| ② 详情采集（渲染型） | `not_shopify/` | 商品 URL 表 | CSV/XLSX + Shopify 原价表 + 拆分表 |
| ③ 转换改价 | `03switch/` | 统一字段表 / Shopify 表 | `_原价`、`_价格匹配`、`wp-` 等产出 |
| ④ 辅助 | `04utils/` | 产出文件 | 品牌词替换、WebP→JPG |

## 目录结构

```text
anglan_crawler/
├─ 00md/                    三份技术文档（流程 / shopify_json / not_shopify）
├─ 01xlsx/                  输入：按批次-负责人-目标店铺组织的产品 URL 表（113 个文件）
├─ 02crawler/
│   ├─ detail_link/         分类页商品链接采集：page / scroll / click 三种翻页策略
│   └─ Crawl/               7 个站点定制版详情采集脚本
├─ 03switch/                格式转换与改价工具（7 个脚本 + GUI）
│   └─ exe/switch_gui.py    tkinter 图形界面，同时是 Scrapy Spider 生成器
├─ 04utils/                 品牌词替换 GUI、WebP 转 JPG
├─ shopify_json/            Shopify .json 接口采集（Scrapy 子项目，11 个在用 Spider / 88 个历史模板）
├─ not_shopify/             Selenium 渲染采集（Scrapy 子项目，quince）
├─ A产出/                   业务产出归档，按批次 A0630…A0730 组织（1046 个文件）
├─ requirements.txt
└─ README.md
```

`01xlsx/` 与 `A产出/` 是业务数据，不是 Python 包；`shopify_json/` 和 `not_shopify/` 是两个互相独立的 Scrapy 项目，各自带 `scrapy.cfg`。

## 环境准备

需要 Python 3.10+ 与本机 Chrome。

```powershell
cd D:\C_code\anglan_crawler
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`requirements.txt` 覆盖 Scrapy 采集与转换全流程（scrapy、selenium、webdriver-manager、openpyxl、pandas、itemadapter、lxml、requests、tqdm）。`02crawler/` 里的 DrissionPage 脚本和 `04utils/webp_to_jpg.py` 属于按需安装的额外依赖：

```powershell
python -m pip install DrissionPage Pillow
```

**代理说明**：只有 `02crawler/` 的浏览器脚本内置本地代理 `http://127.0.0.1:7897`（`detail_link_page.py` 的 Chrome 启动参数、`Crawl/macandclay.py` 的 `requests` 配置，后者支持用环境变量 `CRAWLER_PROXY` 覆盖）。两个 Scrapy 项目**均无代理配置**，如目标站需要代理，得自行在 Spider 的 `custom_settings` 里加 `DOWNLOADER_PROXY` 或下载中间件。

## 核心数据契约

### 统一字段（10 列）

所有详情采集器的输出都是同一套列，顺序固定（见 `shopify_json/shopify_json/pipelines.py:41`）：

```text
title, name, price1, price2, styles1, styles2, styles3, src_links, link-href, details
```

| 字段 | 含义 |
|---|---|
| `title` | 取自输入表第 1 列的分类名，下游映射为 Shopify 的 `Collection` 与 `Vendor` |
| `name` | 商品标题 |
| `price1` | 现价（销售价），统一折算为 USD |
| `price2` | 划线价（compare-at price），缺失时回退为 `price1` |
| `styles1/2/3` | 变体组合编码串（见下） |
| `src_links` | 主图列表，`#` 分隔 |
| `link-href` | 原始商品页 URL。因含连字符不是合法属性名，Item 里动态注册 |
| `details` | 清洗后的 `body_html`：去掉 `<a>`、保留 `<img src>`、剔除增补字符 |

当前实现里只有 `styles1` 有值，`styles2`/`styles3` 恒为空串——这是转换器保留的扩展位。

### `styles` 编码文法

这是贯穿全项目的内部约定，被采集端生成、转换端解析：

```text
<Option1名称>#<段1>#<段2>#<段3>...

段 = <值1>&<名2>&<值2>&<名3>&<值3>$price1$price2@<该变体图>
```

- `#` 分隔「选项名前缀」与各个变体段
- `&` 交错拼接选项名与选项值；第一段值不带名字
- `$` 分隔现价与划线价（用 `rsplit` 取末两段，因此选项值里允许出现 `$`）
- `@` 追加该变体对应图片，按第一个选项的值归组

单色商品实例：

```text
Color#Red$19.99$29.99@https://cdn.example.com/red.jpg
```

双色双码商品实例：

```text
Color#White&Size&M$19.99$29.99@https://cdn/white-m.jpg#Black&Size&L$22.00$33.00@https://cdn/black-l.jpg
```

生成端：`shopify_json/shopify_json/utils/json_variants.py:325` 的 `build_variant_combo()` 与 `:305` 的 `build_segment()`。
解析端：`03switch/05wp还原为styles.py:72` 的 `build_styles_segment()`、`03switch/exe/switch_gui.py:178`。

### 价格语义

`_原价` = 已完成 Shopify 表结构转换、**尚未**改价的中间态；`_价格匹配` = 从内置价格库取到目标价的结果；`_未匹配到的价格` = 价格库里剩余未被取走的价格。

## ① 链接采集：`02crawler/detail_link/`

三个脚本对应三种真实站点翻页形态，共用输出格式：**单个 xlsx，两列 `title,link`**，文件名用域名并把 `.` 换成 `_`（如 `shophoneydew_com.xlsx`），一次运行一个文件、不带时间戳。三者都**不接受命令行参数**，运行前必须改脚本顶部的配置常量。

| 脚本 | 浏览器库 | 翻页策略 | 关键配置（行号） |
|---|---|---|---|
| `detail_link_page.py` | DrissionPage + lxml | URL 分页：首页用 base，后续拼 `?page=N` | `XPATH_LINK`:23、`MAX_PAGES`:24、`START_PAGE`:25、`PAGES`:26-36、代理:50、重试/延时:41-43 |
| `detail_link_scroll.py` | Selenium + lxml | 无限滚动，`scrollBy(SCROLL_STEP)` 直到底部无新增 | `XPATH_LINK`:26、`PAGES`:28-43、`SCROLL_PAUSE`/`MAX_NO_CHANGE`/`SCROLL_STEP`:48-50 |
| `detail_link_click.py` | Selenium + lxml | 反复点击「加载更多」按钮直到按钮消失 | `XPATH_LINK`:28、`XPATH_LOAD_MORE`:29、`PAGES`:31-33、`CLICK_PAUSE`/`MAX_NO_CHANGE`:38-39 |

`PAGES` 是「批次 → 目标站点 + 分类名 + 分类页 URL」的多站点配置列表，换站点通常只需在这里增删条目并同步 `XPATH_LINK`。

值得留意的两点实现细节：
- `detail_link_page.py` 对首页为空的情况做了反爬重试（`:184-201`），并在每页执行滚动到底（`:85-94`）以触发懒加载。
- `detail_link_scroll.py` 含 `dismiss_popup()`（`:121-170`），用于自动关掉站点弹出的地区/币种选择框（选美国、USD）。
- ⚠️ `detail_link_scroll.py:46` 的 `OUTPUT_DIR` 写成了字面量 `r"/02crawler/output"`（根路径相对，非仓库相对），直接运行会写到盘符根目录下，用前请改成绝对路径。

运行：

```powershell
python 02crawler\detail_link\detail_link_page.py
```

## ② 详情采集（主力）：`shopify_json/`

Shopify 架构站点的采集器。核心思路：把商品页 URL 直接改写成同路径的 `.json`（`https://host/products/<handle>` → `https://host/products/<handle>.json`），拿结构化数据，绕开 DOM 解析。

### 输入表

`.xlsx`，从**第 2 行**起读：第 1 列分类名 → `title`，第 2 列商品详情 URL。URL 为空的行跳过。`group_targets_by_json_url()`（`utils/json_variants.py:28`）按规范化后的 JSON URL 去重并统计跳过数，原始 URL 会剥掉 query 与 fragment。

### 关键模块

| 文件 | 职责 |
|---|---|
| `utils/json_variants.py` | 从 `product` JSON 抽取变体。`to_shopify_json_url`:9、`get_variant_id_from_url`:17、`group_targets_by_json_url`:28、`fetch_exchange_rates`:55（带缓存）、`convert_price_to_usd`:72（**除以汇率**）、`find_fallback_variant`:107（优先 `position==1`）、`get_sorted_options`:115（按 position 排序、**只保留多值选项**、Color 前置）、`format_image_url`:175（注入 `_600x600`）、`build_first_image_srcs`:204、`build_variant_combo`:325、`clean_body_html`:399 |
| `utils/shopify_converter.py` | `convert_to_shopify()`:207，产出 Shopify 批量导入 CSV（模板 `SHOPIFY_COLUMNS` 为 **49 列**，校验 `REQUIRED_COLUMNS`:32）；内置价格库 `PRICE_LIBRARY`:44 与 `match_prices()`:137 |
| `pipelines.py` | `ShopifyJsonPipeline`（`ITEM_PIPELINES` 优先级 300，唯一启用的 pipeline）。`open_spider`:54 建目录、`process_item`:79 取前 5 张 `src_links` 并追变体图去重、`close_spider`:100 写 `_styles.xlsx` 后调用转换器 |
| `middlewares.py` | **Scrapy 脚手架样板，未被注册**（`settings.py:43-51` 两处 `SPIDER_MIDDLEWARES`/`DOWNLOADER_MIDDLEWARES` 均被注释）。不要被它的存在误导 |

### 全局设置

`settings.py`：`ROBOTSTXT_OBEY = False`:22、`CONCURRENT_REQUESTS_PER_DOMAIN = 1`:26、`DOWNLOAD_DELAY = 1`:27、`FEED_EXPORT_ENCODING = "utf-8"`:87、`LOG_LEVEL = INFO`:90。无代理、无 DOWNLOAD_HANDLERS、AutoThrottle 与 HTTPCache 均注释。

### 429 处理在 Spider 里，不在中间件

每个 Spider 自己声明 `handle_httpstatus_list = [429]` 与 `custom_settings`（`CONCURRENT_REQUESTS`、`DOWNLOAD_DELAY`、`RETRY_TIMES = 5`），并用 `reactor.callLater(30 * n)` 做最多 5 次的延迟重试，配合 `_pending_retries` 计数与 `DontCloseSpider` 防止 crawler 提前关闭（代表实现 `spiders/workinstyleboutique.py:96-124`）。

### 新增一个站点 Spider

1. 复制 `spiders/` 下任一在用 Spider（`workinstyleboutique.py` 是最干净的样板），文件名为站点 slug。
2. 改文件顶部常量：`PROJECT_ROOT`（`Path(__file__).resolve().parents[3]`，通常不用动）、`INPUT_FILE`、`allowed_domains`、`TEST_MODE`、`TEST_COUNT`、`SKIP_POSITIONS`、`SKIP_OPTIONS`。
3. 改类属性 `name` 与 `custom_settings` 里的并发。
4. `spiders/` 会被 Scrapy 自动发现；历史站点模板放在 `spiders/Historical/`（88 个），不自动注册，需要时复制出来。

`SKIP_POSITIONS`/`SKIP_OPTIONS` 是图片与选项的裁剪钩子：例如 `mmlafleur13.py` 设 `SKIP_POSITIONS=[1,3]` 丢弃第 2、4 张图。当前 11 个在用 Spider 里只有个别设置，`SKIP_OPTIONS` 仅在 `Historical/akiso_store.py` 用过。

并发档位按站点承受能力调：`workinstyleboutique`/`mmlafleur`/`mnml` 用 `CONCURRENT_REQUESTS=2, DOWNLOAD_DELAY=1`，而 `meuboutique`/`shophoneydew`/`tresbienboutique` 用 `CONCURRENT_REQUESTS=8, DOWNLOAD_DELAY=0.5`。

### 输出布局

```text
shopify_json/shopify_json/output/<输入分组名>/<YYYYMMDD_HHMMSS>/
├─ <spider>_styles.xlsx                     统一字段表（③ 的输入）
├─ xlsx/<spider>_styles_Shopify_原价.xlsx
├─ xlsx/<spider>_styles_Shopify_价格匹配.xlsx
├─ xlsx/<spider>_styles_Shopify_未匹配到的价格.xlsx
└─ csv/  同名 CSV 三件
```

`<输入分组名>` 取自 `INPUT_FILE` 的**父目录名**（失败时回退到 `spider.name`），因此把输入表按目标店铺归档，产出就会自动落到对应店铺目录。

### 价格匹配规则（`shopify_converter.py:137`）

价格库 `PRICE_LIBRARY` 是硬编码常量表。按 `Handle` 分组、变体价升序处理，为每个原始价在 `[0.75×, 1.25×]` 区间内取**最小的未被占用**价格，全局一次性消费（同一价格不会在两行重复使用）。取不到价格的商品行进入 `_未匹配到的价格`，跑完后可据此判断价格库是否够用。

运行：

```powershell
cd D:\C_code\anglan_crawler\shopify_json
scrapy list
scrapy crawl workinstyleboutique
```

## ② 详情采集（渲染型）：`not_shopify/`

非 Shopify 架构、必须真实渲染才能拿到内容的站点。当前仓库实际在用的 Spider 只有 `quince`。

### Selenium 下载中间件

`SeleniumDownloaderMiddleware` 是唯一启用的下载中间件（`settings.py`，优先级 543），在 `spider_opened` 时创建**一个共享 Chrome 实例**。`process_request()` 流程：`driver.get(url)` → `WebDriverWait` 等待 `meta["wait_xpath"]` 出现（`SELENIUM_REQUEST_TIMEOUT=30s`，未指定则等 `<body>`）→ 再睡 `wait_extra`（默认 3s）→ 取 `documentElement.outerHTML` → 随机延时 `PAGE_RANDOM_WAIT_MIN..MAX`（2.0–4.0s）→ 包装成 `HtmlResponse` 交回 Spider 解析。最终 DOM 序列化后返回，所以 XPath 拿到的是渲染后的内容。

Chrome 反自动化特征处理：`--start-maximized`、`--disable-blink-features=AutomationControlled`、`excludeSwitches=[enable-automation]`、`useAutomationExtension=False`，并注入 JS 隐藏 `navigator.webdriver`；驱动由 `webdriver_manager` 的 `ChromeDriverManager().install()` 管理。**无代理配置**。

并发强制 `CONCURRENT_REQUESTS=1`、`CONCURRENT_REQUESTS_PER_DOMAIN=1`、`DOWNLOAD_DELAY=0`、`ROBOTSTXT_OBEY=False`——单浏览器实例无法并行，改这里会崩。

### 空数据自愈

`ValidateSpiderMiddleware`（Spider 中间件，优先级 543）检查 `EMPTY_CHECK_FIELDS` 这 9 个字段（不含 `link-href`）。若**连续 3 条** item 全空（`EMPTY_THRESHOLD=3`），调用 `selenium_middleware.restart()`（quit → 睡 5s → 重启浏览器），并把已保存的失败请求以 `dont_filter=True` 重新入队。这是应对长时间运行后页面渲染退化的兜底。

### 输出布局

```text
not_shopify/output/<YYYYMMDD_HHMMSS>/
├─ <spider>.csv / <spider>.xlsx        统一字段（test 模式加 _test 后缀）
├─ <spider>_原价.xlsx                   Shopify 49 列结构
└─ <spider>_原价_拆分.xlsx              选项 × 图片笛卡尔展开行
```

`NotShopifyPipeline`（优先级 300）负责写文件，`shopify_converter.py` 负责结构转换，SKU 由 `generate_variant_sku()` 随机生成、handle 保证唯一、`@image` 拆到 `Variant Image`。

**与 `shopify_json` 的关键差异**：`not_shopify` **不做价格库匹配**，产出到 `_原价` 为止，改价要走到 ③ 的 `03switch/02价格排序.py`。

```powershell
cd D:\C_code\anglan_crawler\not_shopify
scrapy list
scrapy crawl quince
```

### quince Spider 的取值方式

输入表固定 `../01xlsx/quince.xlsx`。类属性定义 XPath：`h1` 取标题、销售价/原价 span、`legend` 取尺码（打包成 `Color#White$price1$price2`，无 `@image` 段）、描述 `<p>`。图片走另一条路：解析页面 `__NEXT_DATA__` JSON，按 DOM 中的 img id 匹配 `ctfassets` 资源，改写为 `images.quince.com` 并强制 `w=600&h=750&q=50&reqOrigin=website-ssr`，`#` 拼接；失配时回退 `srcSet`。`TEST_MODE=False`、`TEST_COUNT=10`。

## ① 早期定制版详情采集：`02crawler/Crawl/`

7 个站点定制脚本，是 Scrapy 项目之前的形态，输出与统一字段一致的 10 列 CSV/XLSX。它们同样读顶部硬编码的 `INPUT_FILE`，无命令行参数。两条技术路线：

| 脚本 | 路线 | 特殊点 |
|---|---|---|
| `aliciaswim.py`、`en_gringaswimwear.py`、`shopdressup.py` | Selenium 打开 `<url>.json`，读 `body.innerText` 后 `json.loads` | Shopify 接口的浏览器版实现 |
| `shopdolcessa.py` | 同上 | `build_src_links(..., skip_positions=[2])`:254 丢弃第 2 张图 |
| `macandclay.py` | `requests` 直取 `.json`（**无需浏览器**），失败回退内嵌 JSON / HTML 解析 | `:289-410`；`CRAWLER_PROXY`:64、`IMAGE_LIMIT=5`:75 |
| `quince.py` | Selenium 渲染 + XPath（`og:title`、`product:price:amount`、`select`） | `:45-52`；弹窗处理 `:232`；**默认 `TEST_MODE=True` 只跑 10 条** |
| `jimiss.py` | 同上（`h1.product-single__title`、`itemprop=price`、`select[@data-name='Size']`） | 只处理 Size 一个选项；Cloudflare 重试 `:158-199` |

配置常量位置（`INPUT_FILE` / `OUTPUT_DIR` / `TEST_MODE`+`TEST_COUNT` / `DELAY_RANGE`）：`quince` L55/56/59、`macandclay` L53/55/78、`jimiss` L46/47/50、`aliciaswim` L29/30/33、`en_gringaswimwear` L29/30/33、`shopdolcessa` L29/30/33、`shopdressup` L41/42/45。

输出：`02crawler/output/<YYYYMMDD_HHMMSS>_<站点>[_test].csv` 与同名 xlsx（`_test` 后缀在 `TEST_MODE` 下追加）。

> 这些脚本与新 Spider 功能重叠，新增站点请优先走 `shopify_json`；`02crawler/Json_Crawl/run.py`、`run2.py`（通用 CLI 版采集脚本）已从工作区移除。

## ③ 格式转换与改价：`03switch/`

| 脚本 | 输入 | 输出 | 作用 |
|---|---|---|---|
| `01转shopify.py` | `<stem>_styles.xlsx`（9 列校验 `:129`） | `<stem去_styles>_shopify_原价.xlsx`（`:14`） | 按 `#` 拆 `styles1/2/3`（`:98-119`），`itertools.product` 组合选项，套 Shopify 模板铺成商品行+变体行；openpyxl 二次遍历按 `$`/`&` 拆 `Option1 Value`（`:243-296`）。**不改价** |
| `02价格排序.py` | `<stem>_原价.xlsx`（`:31`） | `_价格匹配.xlsx`（`:105`）、`_未匹配到的价格.xlsx`（`:114-122`） | 硬编码 `price_library`（`:6-25`，约 200 个价格）。按 `Handle` 分组、`Variant Price` 升序，`global_used_prices`（`:53,81,95-97`）保证全局不重复取价，区间 `[0.75×, 1.25×]`（`:86-98`）。会剥掉 `_待匹配`/`_原价_拆分` 后缀（`:37-42`） |
| `03shopify转WP.py` | Shopify CSV（`:6`） | `wp-<filename>.csv`（`:156`，utf-8-sig） | 字段映射见下 |
| `04价格检查.py` | `wp-*.csv`（`:4`） | 仅控制台 | 用 `price_library` 模糊匹配 sale/regular 列（`:37-41`），打印**未被使用**的价格（`:63-70`） |
| `05wp还原为styles.py` | `wp-*.csv` | `<stem去wp->_styles.xlsx`（`:153-156`） | 逆向重建 `#/$/@/&` 文法，`build_styles_segment`:72-93 |
| `06SKU更新.py` | `wp-*.csv` | `<stem>_新SKU.csv`（`:125`） | 重生成父/变体 SKU，`used_skus` 去重并回指 `Parent`（`:91-112`） |
| `06SKU独立查重.py` | `wp-*.csv` | 仅控制台 | 只读审计：父/变体重复 SKU 分类，并检出 `Parent` 找不到父行的孤儿变体（`:112-123`） |

### Shopify → WooCommerce 映射（`03shopify转WP.py`）

```text
Title                  → Name
Body (HTML)            → Description
Collection / Vendor    → Categories
Variant Price          → Sale price
Variant Compare At Price → Regular price（缺失时回退用 Sale）
Image Src              → 父产品 Images（WPAdd 逗号拼接并去重，:18-21,139）
Option1..3             → Attribute1..3
Default Title          → 简单产品（无变体）
```

可变产品父行 SKU：`SKU{int(time.time())}{行号}`（`:36`）；变体行用 `Variant SKU`、`Parent` 指向父 SKU、`Images` 填 `Variant Image`、`Name` = 父名 + `-选项1,选项2,选项3`（`WPTitle`:7-15）。

> 注意 SKU 策略不一致：命令行脚本用**时间戳+行号**（不稳定、重跑会变），GUI 用**MD5 确定性派生**（`generate_parent_sku`, `switch_gui.py:162-175`）。要可复现的 SKU 就用 GUI 路径。

### 命令行支持

只有三个脚本接受 `sys.argv[1]`（缺省回落到顶部 `INPUT_FILE`）：

```powershell
python 03switch\05wp还原为styles.py   "D:\path\wp-products.csv"
python 03switch\06SKU更新.py          "D:\path\wp-products.csv"
python 03switch\06SKU独立查重.py      "D:\path\wp-products.csv"
```

`01转shopify.py`（`:10`）、`02价格排序.py`（`:31`）、`03shopify转WP.py`（`:6`）、`04价格检查.py`（`:5`）**只认硬编码 `INPUT_FILE`**，运行前必须编辑文件。

## GUI：`03switch/exe/switch_gui.py`

tkinter/ttk 单窗口工具（`SwitchToolGui`:944），把 ③ 的多步串成一键操作，用线程跑任务（`:1227`）并带日志面板。7 个标签页工具（`:1037-1053`）：

- styles 转 Shopify + 价格匹配（`price_match`:297-301 链式调用）
- Shopify CSV 转 WooCommerce CSV
- WP 价格检查
- WP 还原 styles
- SKU 查重
- SKU 更新
- WP 图片去重（`wp_images_trim`:709-750，就地清洗 `Images` 列）
- 从 `SPIDER_TEMPLATE` 生成 Scrapy Spider（`:787-880`，写入 `shopify_json/.../spiders`，路径基准 `:77`）

**重要**：GUI **不复用** `03switch/*.py`，而是各自独立实现（`PRICE_LIBRARY`:20-39、`price_match()`:304-370 与 `02价格排序.py` 同算法）。因此两者行为有差异：GUI 产出后缀为 `_Shopify_原价`、`_Shopify_价格匹配`，写入 `xlsx/`+`csv/` 子目录，父 SKU 用 MD5 派生。**改转换逻辑时必须同时改两处**，否则命令行与 GUI 结果会分叉。

```powershell
python 03switch\exe\switch_gui.py
```

## ④ 辅助工具：`04utils/`

- `replace_brands_gui.py` —— tkinter GUI（`BrandReplacerApp`:17）。**只改 CSV/XLSX 的 `Name` 列文本内容**，不重命名文件或目录：关键词按长度降序、大小写不敏感、`\b` 词边界正则替换（`:188-193`），相邻命中用哨兵合并避免碎片化改写（`:199-224`），输出 `<base>_replaced<ext>`（`:273`）。用于把源品牌名替换为目标店铺的品牌词。
- `webp_to_jpg.py` —— 无 GUI。自动安装 Pillow（`:15-20`）；把 `images_dir` 下所有 `*.webp` 转 `.jpg`（RGBA 铺白底、质量 90）并删除原图（`:64`）；随后把 CSV 的 `Images` 列 `.webp` 改写为 `.jpg`（`:95-98`），原 CSV 备份为 `.bak`（`:101-102`）。路径配在 `:23-24` 的 `images_dir`/`csv_file`。

## 业务数据目录约定

### 输入 `01xlsx/`（113 个文件）

```text
01xlsx/<批次 Axxxx>/<负责人>/<目标店铺域名 + 中文品类>/<源品牌>.xlsx
01xlsx/Historical content/...          历史散件输入
```

批次：`A0701`（22 个店铺目录 / 44 表）、`A0710`（11 / 26）、`A0721`（8 / 18）、`A0730`（8 / 11）。每个目标店铺下挂 2–5 个源品牌 URL 表，对应同一目标店铺要采集的多个来源站点。

### 产出 `A产出/`（1046 个文件）

```text
A产出/<批次>/[<负责人>/]<目标店铺 + 中文品类>/<源品牌>/<运行时间戳>/[csv/ xlsx/]
                                       └─ 同级 <...>合并[N]/ 目录放该目标店铺的合并结果
```

`A0630` 226 / `A0701` 220 / `A0710` 286 / `A0721` 250 / `A0730` 64 个文件。目录结构在演进：`A0630` 无负责人层，`A0701`/`A0710` 引入，`A0721`/`A0730` 在产出侧又去掉（输入侧保留）。

文件名后缀对应的阶段：

| 后缀 | 阶段 |
|---|---|
| `<brand>.csv/.xlsx` | ② 原始采集 |
| `_styles` | 统一字段表，③ 的入口 |
| `_待匹配` | 匹配前排队表 |
| `_原价` / `_Shopify_原价` | Shopify 结构化，未改价 |
| `_原价_拆分` | 选项 × 图片展开行 |
| `_价格匹配` / `_Shopify_价格匹配` | 已从价格库取到价 |
| `_未匹配到的价格` | 价格库剩余 / 未取到价 |
| `合并-*` | 按目标店铺合并多来源 |
| `wp-` 前缀 | ④ WooCommerce 最终导入表 |
| `_新SKU` | SKU 重生成结果 |

`A0730`（最新批次）的 5 个目标店铺：`aurelinas.com` 礼服 ← lovedandco；`halcys.com` 内衣家居服 ← shophoneydew；`kestrs.com` 男装 ← mnml_la；`lindvs.com` 连衣裙 ← meuboutique / shopinkeriboutique / shopkla / swagg-boutique-llc / tresbienboutique；`vestf.com` 职业装-女 ← mmlafleur / workinstyleboutique。

## 端到端 Runbook

一条完整链路的推荐顺序：

```powershell
# 0) 激活环境
.\.venv\Scripts\Activate.ps1

# 1) 采链接（改脚本顶部 PAGES / XPATH_LINK 后）
python 02crawler\detail_link\detail_link_page.py
#    → 02crawler\output\<domain_underscored>.xlsx

# 2) 把链接表整理成输入表放到 01xlsx\<批次>\<负责人>\<目标店铺>\<源品牌>.xlsx

# 3) 采详情 + 自动转 Shopify + 自动改价（Shopify 站点）
cd shopify_json
scrapy crawl <spider_name>
#    → shopify_json\shopify_json\output\<分组>\<时间戳>\ 下 styles / 原价 / 价格匹配 / 未匹配

# 3') 非 Shopify 站点
cd ..\not_shopify
scrapy crawl quince
#    → not_shopify\output\<时间戳>\ 只到 _原价，需继续第 4 步

# 4) 补齐改价（not_shopify 产出）
#    编辑 03switch\02价格排序.py 的 INPUT_FILE 后
python 03switch\02价格排序.py

# 5) 转 WooCommerce
#    编辑 03switch\03shopify转WP.py 的 INPUT_FILE 后
python 03switch\03shopify转WP.py
#    → wp-<filename>.csv

# 6) 收尾核查
python 03switch\06SKU独立查重.py "D:\path\wp-products.csv"
python 03switch\05wp还原为styles.py "D:\path\wp-products.csv"

# 7) 图片与品牌名处理（按需）
python 04utils\webp_to_jpg.py
```

如果不想逐步编辑路径，`python 03switch\exe\switch_gui.py` 用界面把 3~6 串起来，并可顺带生成新站点的 Spider 骨架。

## 配置项速查

| 我要改… | 位置 |
|---|---|
| 分类页 URL 与商品链接 XPath | `02crawler/detail_link/detail_link_page.py:23,26-36` |
| 「加载更多」按钮 XPath | `02crawler/detail_link/detail_link_click.py:29` |
| 采集输入表路径 | Spider / Crawl 脚本顶部 `INPUT_FILE` |
| 试跑开关与条数 | `TEST_MODE` / `TEST_COUNT` |
| 丢图 / 丢选项 | `SKIP_POSITIONS` / `SKIP_OPTIONS` |
| 并发与延时 | Spider 的 `custom_settings`、`settings.py:26-27` |
| 价格库 | `shopify_json/shopify_json/utils/shopify_converter.py:44`、`03switch/02价格排序.py:6-25`、`switch_gui.py:20-39`（**三份副本，需同步**） |
| 匹配区间 | 上述三处各自的 `0.75× / 1.25×` 常量 |
| Shopify 列模板 | `shopify_converter.py:10-30`（49 列） |
| 代理 | `detail_link_page.py:50`、`macandclay.py:64`（或 `CRAWLER_PROXY`） |
| 等待 XPath（渲染型站点） | Spider `meta["wait_xpath"]`、`SELENIUM_REQUEST_TIMEOUT`、`wait_extra` |

## 文档

- [通用流程文档](00md/通用流程文档.md)
- [shopify_json 技术文档](00md/shopify_json技术文档.md)
- [not_shopify 技术文档](00md/not_shopify技术文档.md)

阅读这两份文档时请注意以下与代码不符之处（截至本次更新）：`shopify_json技术文档.md` 第 6 节把 `<spider>_原价.xlsx` 列为独立产出，实际只有 `xlsx/<spider>_styles_Shopify_原价.xlsx`；未说明 `styles` 串首段是选项名、`&` 交错选项名与值；`convert_price_to_usd` 是**除以**汇率而非乘以；未提及 `middlewares.py` 是未注册的样板、429 重试实现在各 Spider 内。第 9 节引用的 `02crawler/Json_Crawl/run2.py` 已移除。`not_shopify技术文档.md` 基本准确，仅遗漏 `--start-maximized`、重启时的 5s 等待、`_test` 后缀命名。

## 注意事项

- **合规**：只对有权访问、且目标站点服务条款允许处理的网站与商品数据运行采集器。
- **生产前必查**：Spider 顶部的 `INPUT_FILE`、`allowed_domains`、`SKIP_*`、`TEST_MODE` 与并发档位。`02crawler/Crawl/quince.py` 默认 `TEST_MODE=True`，`detail_link_click.py` 的 XPath 与 `PAGES` 默认为空。
- **先小样本**：以 `TEST_MODE=True` 或小表验证 10 列字段与 `styles` 编码是否正确，再全量跑。全量前确认 Chrome/ChromeDriver 可用。
- **改价不可逆**：价格库全局一次性消费，同一次运行里重复跑 `02价格排序.py` 会消耗不同价格集合；需要重匹配请从 `_原价` 重新开始。
- **两份实现需同步**：`03switch/*.py` 与 `switch_gui.py` 逻辑重复但彼此独立，转换规则变更必须双改。
- **无测试套件**：项目没有单元或集成测试。当前验证手段是小样本运行 + 输出字段人工检查 + 转换结果对照，改动后建议保留一份已知正确的输入表做回归对照。
- **路径硬编码**：多数脚本靠编辑源码里的 `INPUT_FILE`/`OUTPUT_DIR` 运行，仅 3 个支持命令行参数。这是有意的取舍，但也意味着换输入必改源码。
