# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class NotShopifyItem(scrapy.Item):
    title = scrapy.Field()
    name = scrapy.Field()
    price1 = scrapy.Field()
    price2 = scrapy.Field()
    styles1 = scrapy.Field()
    styles2 = scrapy.Field()
    styles3 = scrapy.Field()
    src_links = scrapy.Field()
    link_href = scrapy.Field()
    details = scrapy.Field()
