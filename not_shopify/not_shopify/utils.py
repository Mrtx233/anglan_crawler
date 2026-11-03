import json
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import openpyxl


XPATH_NEXT_DATA = "//script[@id='__NEXT_DATA__']/text()"

QUINCE_IMAGE_ID_XPATH = (
    "//div[contains(@class,'sliderImagesV2_container__left__slider__image')]"
    "//img/@id"
)

QUINCE_SRCSET_FALLBACK_XPATH = (
    "//div[contains(@class,'sliderImagesV2_container__left__slider__image')]"
    "//picture/source/@srcSet"
)


def extract_text(value):
    if isinstance(value, str):
        return value.strip()
    if hasattr(value, "text_content"):
        return value.text_content().strip()
    if hasattr(value, "text"):
        return (value.text or "").strip()
    return str(value).strip()


def get_text(response, xpath):
    if not xpath:
        return ""
    values = response.xpath(xpath)
    if not values:
        return ""
    value = values[0].xpath("string(.)").get()
    if value is None:
        value = values[0].get()
    return extract_text(value) if value else ""


def get_texts(response, xpath, sep=" | "):
    if not xpath:
        return ""
    parts = []
    for selector in response.xpath(xpath):
        value = selector.xpath("string(.)").get()
        if value is None:
            value = selector.get()
        text = extract_text(value)
        if text:
            parts.append(text)
    return sep.join(parts) if parts else ""


def extract_price(text):
    match = re.search(r"[\d]+\.?\d*", (text or "").replace(",", ""))
    return match.group() if match else ""


def read_quince_targets(filepath):
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    targets = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        category = row[0] if row[0] else "unknown"
        url = row[1]
        if url and str(url).startswith("http"):
            targets.append((str(category), str(url)))
    wb.close()
    return targets


def normalize_quince_style(text):
    return re.sub(r":\s+", "#", text or "")


def process_quince_image_url(raw_url):
    if raw_url.startswith("//"):
        url = "https:" + raw_url
    elif raw_url.startswith("http"):
        url = raw_url
    else:
        url = "https://www.quince.com" + raw_url

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["w"] = ["600"]
    params["h"] = ["750"]
    params.setdefault("q", ["50"])
    params.setdefault("reqOrigin", ["website-ssr"])

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode(params, doseq=True),
        parsed.fragment,
    ))


def extract_next_data(response):
    raw = response.xpath(XPATH_NEXT_DATA).get()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_quince_image_links_from_next_data(next_data, response, style_xpath):
    try:
        product = next_data["props"]["pageProps"]["pageData"]["context"]["pageDataJson"]["product"]
        images_data = product.get("images", [])
    except (KeyError, TypeError):
        return ""

    json_img_map = {}
    for img_entry in images_data:
        image = img_entry.get("image", {})
        img_id = image.get("id", "")
        img_url = image.get("url", "")
        if img_id and img_url:
            json_img_map[img_id] = img_url

    links = []
    dom_img_ids = response.xpath(QUINCE_IMAGE_ID_XPATH).getall()
    if dom_img_ids:
        for img_id in dom_img_ids:
            if img_id in json_img_map:
                url = json_img_map[img_id]
                url = url.replace("images.ctfassets.net/afruo3gr1g6h/", "images.quince.com/")
                links.append(process_quince_image_url(url))
        return "#".join(links) if links else ""

    current_color = ""
    raw_style = get_text(response, style_xpath)
    match = re.search(r":\s*(.+)", raw_style)
    if match:
        current_color = match.group(1).strip()

    seen_ids = set()
    for img_entry in images_data:
        options = img_entry.get("options", [])
        if current_color:
            color_match = any(
                opt.get("name") == "Color" and current_color in opt.get("values", [])
                for opt in options
            )
            if not color_match:
                continue

        image = img_entry.get("image", {})
        img_id = image.get("id", "")
        if img_id in seen_ids:
            continue
        seen_ids.add(img_id)

        url = image.get("url", "")
        if url:
            url = url.replace("images.ctfassets.net/afruo3gr1g6h/", "images.quince.com/")
            links.append(process_quince_image_url(url))

    return "#".join(links) if links else ""


def extract_quince_image_links(response, style_xpath):
    """Extract Quince images from __NEXT_DATA__, then fall back to DOM srcSet."""
    next_data = extract_next_data(response)
    if next_data:
        result = _extract_quince_image_links_from_next_data(next_data, response, style_xpath)
        if result:
            return result

    links = []
    seen_paths = set()
    for srcset in response.xpath(QUINCE_SRCSET_FALLBACK_XPATH).getall():
        raw = srcset.strip().split(",")[0].strip().split(" ")[0].strip()
        if not raw:
            continue
        parsed = urlparse(("https:" + raw) if raw.startswith("//") else raw)
        if parsed.path in seen_paths:
            continue
        seen_paths.add(parsed.path)
        links.append(process_quince_image_url(raw))
    return "#".join(links) if links else ""
