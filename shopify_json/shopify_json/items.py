# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ShopifyJsonItem(scrapy.Item):
    title = scrapy.Field()
    name = scrapy.Field()
    price1 = scrapy.Field()
    price2 = scrapy.Field()
    styles1 = scrapy.Field()
    styles2 = scrapy.Field()
    styles3 = scrapy.Field()
    src_links = scrapy.Field()
    details = scrapy.Field()


# "link-href" 含连字符，无法作为 Python 类属性名，动态注册到 fields
ShopifyJsonItem.fields["link-href"] = scrapy.Field()
