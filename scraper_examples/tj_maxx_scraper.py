import re

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .base import BaseStoreLocationWebdriverScraper
from src.engine.models import StoreLocation, Merchant


class TJMaxxScraper(BaseStoreLocationWebdriverScraper):
    base_url = "https://m.tjmaxx.tjx.com/m/stores/storeLocator.jsp#"
    merchant_name = 'T.J. Maxx'
    geolocator = Nominatim(user_agent='finhance-api')
    use_proxy = True

    def process(self):
        try:
            self.persist_stores()
            print('Complete')
        except Exception as e:
            import pdb; pdb.set_trace()
            print(e)
        self.driver.close()

    def persist_stores(self):
        merchant_name = self.merchant_name or self.__class__.__name__.split('Scraper')[
            0]
        merchant, created = Merchant.objects.get_or_create(name=merchant_name)

        for zipcode in self.zipcodes[::10]:
            self.driver.get(self.base_url)
            self.get_stores_by_zipcode(zipcode)
            try:
                self.driver.find_element_by_css_selector('div.alert')
                continue
            except NoSuchElementException:
                self.scrape_store_results(merchant)

    def get_stores_by_zipcode(self, zipcode):
        try:
            self.driver.find_element_by_css_selector('svg.close').click()
        except NoSuchElementException:
            print('No modal present')

        input = self.driver.find_element_by_css_selector(
            'input#store-locator-search')
        button = self.driver.find_element_by_css_selector(
            'input#store-locator-search-submit-locate')
        input.send_keys(zipcode)
        button.click()

    def scrape_store_results(self, merchant):
        WebDriverWait(self.driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ul#store-list'))
        )
        stores = self.driver.find_elements_by_css_selector(
            'li.store-list-item')

        for store in stores:
            self.persist_store_location(store, merchant)

    def persist_store_location(self, store, merchant):
        store_num = store.find_element_by_css_selector(
            'a').get_attribute('href').split('/')[-3]
        full_address = store.find_element_by_css_selector(
            'div.adr').get_attribute('innerText').strip()
        locality, address = full_address.split('\n')
        cleaned_address = re.sub("[\(\[].*?[\)\]]", "", address)
        city, state_zip = cleaned_address.split(', ')
        state, zip = state_zip.split(' ')

        try:
            coordinates = (self.geolocator.geocode(f'{locality}, {cleaned_address}') or
                           self.geolocator.geocode(address))
            lat = coordinates.latitude
            lng = coordinates.longitude
        except (GeocoderTimedOut, AttributeError) as e:
            coordinates = self.get_coordinates(zip)
            lat = coordinates['lat']
            lng = coordinates['lng']

        print(
            f'Scraping information for store number: {store_num} in {city}, {state}')

        StoreLocation.objects.update_or_create(
            merchant=merchant,
            store_id=store_num,
            defaults={
                'city': city,
                'state': state,
                'zip': zip,
                'lat': lat,
                'lng': lng
            }
        )