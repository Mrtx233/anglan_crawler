import json
import urllib.request
from itertools import product
from html import escape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse, urlunparse


def to_shopify_json_url(url):
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path.endswith(".json"):
        path = f"{path}.json"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def get_variant_id_from_url(url):
    query = parse_qs(urlparse(url).query)
    variant_values = query.get("variant", [])
    if not variant_values:
        return None
    try:
        return int(variant_values[0])
    except ValueError:
        return None


def group_targets_by_json_url(targets):
    json_url_groups = {}
    duplicate_product_count = 0

    for title, url in targets:
        original_url = str(url).strip()
        if not original_url:
            continue

        json_url = to_shopify_json_url(original_url)
        if json_url in json_url_groups:
            duplicate_product_count += 1
            continue

        title_text = str(title).strip() if title is not None else ""
        json_url_groups[json_url] = {
            "title": title_text,
            "original_url": urlunparse(urlparse(original_url)._replace(query="", fragment="")),
        }

    return json_url_groups, duplicate_product_count


# ── 汇率转换 ──────────────────────────────────────────────
_exchange_rates_cache = {}


def fetch_exchange_rates():
    """获取最新汇率（以 USD 为基准），带缓存避免重复请求。"""
    global _exchange_rates_cache
    if _exchange_rates_cache:
        return _exchange_rates_cache
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        _exchange_rates_cache = data.get("rates", {})
        print(f"[exchange_rates] fetched {len(_exchange_rates_cache)} rates")
    except Exception as e:
        print(f"[exchange_rates] fetch failed: {e}")
    return _exchange_rates_cache


def convert_price_to_usd(price_str, currency, rates=None):
    """将价格转换为 USD。如果已经是 USD 或无法识别货币则直接返回原价。"""
    if not price_str or not currency:
        return price_str
    if rates is None:
        rates = _exchange_rates_cache
    if not rates:
        return price_str

    currency = str(currency).upper().strip()
    if currency == "USD":
        return price_str

    rate = rates.get(currency)
    if not rate or rate == 0:
        return price_str

    try:
        amount = float(str(price_str).strip())
    except (ValueError, TypeError):
        return price_str

    usd_amount = amount / rate
    return f"{usd_amount:.2f}"


def find_variant_by_id(product, variant_id):
    if variant_id is None:
        return {}
    for variant in product.get("variants", []):
        if variant.get("id") == variant_id:
            return variant
    return {}


def find_fallback_variant(product):
    variants = product.get("variants", [])
    for variant in variants:
        if variant.get("position") == 1:
            return variant
    return variants[0] if variants else {}


def get_sorted_options(product, skip_options=None):
    options = sorted(
        product.get("options", []),
        key=lambda option: option.get("position") or 0,
    )
    if skip_options:
        skip_lower = [s.lower() for s in skip_options]
        options = [
            opt for opt in options
            if not any(s in (opt.get("name") or "").lower() for s in skip_lower)
        ]
    multi_value = [opt for opt in options if len(opt.get("values") or []) > 1]
    # 优先把 Color 提到第一位
    color_idx = next(
        (i for i, opt in enumerate(multi_value)
         if (opt.get("name") or "").lower() == "color"),
        None,
    )
    if color_idx is not None and color_idx > 0:
        color_opt = multi_value.pop(color_idx)
        multi_value.insert(0, color_opt)
    return multi_value


def format_combo_value(value):
    return "" if value is None else str(value)


def format_price(value, rates=None, currency=None):
    if value in (None, ""):
        return ""
    raw = str(value).strip()
    if not raw:
        return ""

    if rates and currency:
        raw = convert_price_to_usd(raw, currency, rates)

    if "." in raw:
        try:
            amount = float(raw)
        except ValueError:
            return raw
    else:
        try:
            amount = int(raw) / 100
        except ValueError:
            return raw

    return str(int(amount)) if amount.is_integer() else f"{amount:.2f}".rstrip("0").rstrip(".")


def format_price2(variant, rates=None):
    currency = variant.get("price_currency", "")
    compare_at_price = variant.get("compare_at_price")
    if compare_at_price and str(compare_at_price).strip():
        return format_price(compare_at_price, rates=rates, currency=currency)
    return format_price(variant.get("price", ""), rates=rates, currency=currency)


def format_image_url(url, size="600x600"):
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path
    dot_index = path.rfind(".")
    slash_index = path.rfind("/")
    if dot_index > slash_index:
        path = f"{path[:dot_index]}_{size}{path[dot_index:]}"
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))


def build_images_by_id(product, skip_positions=None):
    images = product.get("images", [])
    if skip_positions:
        images = [img for img in images if (img.get("position") or 0) not in skip_positions]
    return {
        image.get("id"): format_image_url(image.get("src", ""))
        for image in images
    }


def build_first_image_srcs(product, variant_id=None, limit=None, skip_positions=None):
    images = sorted(
        product.get("images", []),
        key=lambda image: image.get("position") or 0,
    )

    if skip_positions:
        images = [img for img in images if (img.get("position") or 0) not in skip_positions]

    if variant_id is not None:
        variant_images = [
            image for image in images
            if variant_id in (image.get("variant_ids") or [])
        ]
        if variant_images:
            images = variant_images

    selected_images = images if limit is None else images[:limit]
    srcs = [
        format_image_url(image.get("src", ""))
        for image in selected_images
        if image.get("src")
    ]
    return "#".join(srcs)


def _option_field(options, combo_index):
    """Return the variant field name (option1/option2/option3) for a given combo index,
    based on the actual position of the filtered option."""
    if combo_index < len(options):
        return f"option{options[combo_index].get('position', combo_index + 1)}"
    return f"option{combo_index + 1}"


def variant_matches_combo(variant, combo, options):
    for index, value in enumerate(combo):
        field = _option_field(options, index)
        if format_combo_value(variant.get(field)) != format_combo_value(value):
            return False
    return True


def find_variant_by_combo(product, combo, options):
    for variant in product.get("variants", []):
        if variant_matches_combo(variant, combo, options):
            return variant
    return {}


def find_variant_by_first_option(product, first_option_value, options):
    target = format_combo_value(first_option_value)
    field = _option_field(options, 0)
    for variant in product.get("variants", []):
        if format_combo_value(variant.get(field)) == target:
            return variant
    return {}


def build_option_combos(options):
    value_groups = [
        [format_combo_value(value) for value in option.get("values", [])]
        for option in options
    ]
    if not value_groups:
        return [()]
    return list(product(*value_groups))


def resolve_variant_list(product, variant_ids):
    valid_ids = [variant_id for variant_id in variant_ids if variant_id is not None]
    if valid_ids:
        return [find_variant_by_id(product, variant_id) for variant_id in valid_ids]

    options = get_sorted_options(product)
    combos = build_option_combos(options)
    fallback_variant = find_fallback_variant(product)
    result = []
    for combo in combos:
        variant = find_variant_by_combo(product, combo, options)
        if not variant:
            variant = find_variant_by_first_option(product, combo[0], options) if combo else {}
        if not variant:
            variant = fallback_variant
        result.append(variant)
    return result


def build_images_by_first_option(product, options, skip_positions=None):
    """按过滤后的第一个 option 值（如颜色）分组，每组取第一张关联图片。"""
    images_by_id = build_images_by_id(product, skip_positions=skip_positions)
    field = _option_field(options, 0)
    result = {}
    for variant in product.get("variants", []):
        opt_value = format_combo_value(variant.get(field))
        if opt_value and opt_value not in result:
            image_id = variant.get("image_id")
            if image_id and image_id in images_by_id:
                result[opt_value] = images_by_id[image_id]
    return result


def build_segment(combo, options, variant, images_by_first_option, rates=None):
    segment_parts = []
    if combo:
        segment_parts.append(format_combo_value(combo[0]))
        for index, value in enumerate(combo[1:], start=1):
            option_name = format_combo_value(options[index].get("name", ""))
            segment_parts.extend([option_name, format_combo_value(value)])

    currency = variant.get("price_currency", "")
    price1 = format_price(variant.get("price"), rates=rates, currency=currency)
    price2 = format_price(variant.get("compare_at_price") or variant.get("price"), rates=rates, currency=currency)
    first_opt_value = format_combo_value(combo[0]) if combo else ""
    image_src = images_by_first_option.get(first_opt_value, "")

    segment = f"{'&'.join(segment_parts)}${price1}${price2}"
    if image_src:
        segment = f"{segment}@{image_src}"
    return segment


def build_variant_combo(product, skip_positions=None, skip_options=None, rates=None):
    options = get_sorted_options(product, skip_options=skip_options)
    combos = build_option_combos(options)
    fallback_variant = find_fallback_variant(product)
    images_by_first_opt = build_images_by_first_option(product, options, skip_positions=skip_positions)

    segments = []
    for combo in combos:
        variant = find_variant_by_combo(product, combo, options)
        if not variant:
            variant = find_variant_by_first_option(product, combo[0], options) if combo else {}
        if not variant:
            variant = fallback_variant
        segments.append(build_segment(combo, options, variant, images_by_first_opt, rates=rates))

    first_option_name = format_combo_value(options[0].get("name", "")) if options else ""
    if first_option_name:
        return f"{first_option_name}#{'#'.join(segments)}"
    return "#".join(segments)


class CleanBodyHtmlParser(HTMLParser):
    void_tags = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            return
        if tag == "img":
            src = dict(attrs).get("src", "")
            self.parts.append(f'<img src="{escape(src, quote=True)}">' if src else "<img>")
        else:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag == "a" or tag in self.void_tags:
            return
        self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag == "a":
            return
        if tag == "img":
            src = dict(attrs).get("src", "")
            self.parts.append(f'<img src="{escape(src, quote=True)}">' if src else "<img>")
        else:
            self.parts.append(f"<{tag}>")

    def handle_data(self, data):
        data = "".join(ch for ch in data if ord(ch) <= 0xFFFF)
        self.parts.append(escape(data, quote=False))

    def get_html(self):
        return "".join(self.parts).strip()


def clean_body_html(body_html):
    if not body_html:
        return ""
    parser = CleanBodyHtmlParser()
    parser.feed(str(body_html))
    parser.close()
    return parser.get_html()
