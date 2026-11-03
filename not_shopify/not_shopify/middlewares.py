import random
import time

from scrapy import signals
from scrapy.http import HtmlResponse, Request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class NotShopifySpiderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        return None

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    async def process_start(self, start):
        # Called with an async iterator over the spider start() method or the
        # matching method of an earlier spider middleware.
        async for item_or_request in start:
            yield item_or_request

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class NotShopifyDownloaderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class SeleniumDownloaderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        middleware.page_wait_min = crawler.settings.getfloat("PAGE_RANDOM_WAIT_MIN", 2.0)
        middleware.page_wait_max = crawler.settings.getfloat("PAGE_RANDOM_WAIT_MAX", 4.0)
        middleware.request_timeout = crawler.settings.getint("SELENIUM_REQUEST_TIMEOUT", 30)
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def spider_opened(self, spider):
        spider.selenium_middleware = self
        self._init_driver()

    def _init_driver(self):
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def restart(self):
        self.driver.quit()
        time.sleep(5)
        self._init_driver()

    def process_request(self, request, spider):
        self.driver.get(request.url)
        wait_xpath = request.meta.get("wait_xpath")
        wait_extra = request.meta.get("wait_extra", 3)
        if wait_xpath:
            WebDriverWait(self.driver, self.request_timeout).until(
                EC.presence_of_element_located((By.XPATH, wait_xpath))
            )
        else:
            WebDriverWait(self.driver, self.request_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

        time.sleep(wait_extra)
        body = self.driver.execute_script("return document.documentElement.outerHTML;")
        time.sleep(random.uniform(self.page_wait_min, self.page_wait_max))
        return HtmlResponse(
            url=self.driver.current_url,
            body=body,
            encoding="utf-8",
            request=request,
        )

    def spider_closed(self, spider):
        self.driver.quit()


class ValidateSpiderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        middleware.validate_fields = crawler.settings.getlist("EMPTY_CHECK_FIELDS")
        middleware.ignore_fields = set(
            crawler.settings.getlist("EMPTY_CHECK_IGNORE_FIELDS", ["link_href"])
        )
        middleware.empty_threshold = crawler.settings.getint("EMPTY_THRESHOLD", 3)
        return middleware

    def __init__(self):
        self.empty_count = 0
        self.failed_requests = []

    def _handle_output(self, output, response, spider):
        if isinstance(output, Request):
            return [output]

        fields = self.validate_fields or [
            field for field in output.fields
            if field not in self.ignore_fields
        ]
        all_fields_empty = all(not output.get(field) for field in fields)
        if all_fields_empty:
            self.empty_count += 1
            self.failed_requests.append(response.request.replace(dont_filter=True))
            print(f"[EMPTY] {response.url} ({self.empty_count}/{self.empty_threshold})")
            if self.empty_count >= self.empty_threshold:
                print("[RESTART] empty data threshold reached, restarting browser")
                spider.selenium_middleware.restart()
                retry_requests = self.failed_requests
                self.empty_count = 0
                self.failed_requests = []
                return retry_requests
            return []

        self.empty_count = 0
        self.failed_requests = []
        return [output]

    def process_spider_output(self, response, result, spider):
        for output in result:
            yield from self._handle_output(output, response, spider)

    async def process_spider_output_async(self, response, result, spider):
        async for output in result:
            for handled_output in self._handle_output(output, response, spider):
                yield handled_output
