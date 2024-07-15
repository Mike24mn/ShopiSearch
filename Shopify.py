import requests
from bs4 import BeautifulSoup
import concurrent.futures
import queue
import time
from ratelimit import limits, sleep_and_retry
import logging

## BASH SCRIPT, RUN WITH TERMINAL COMMAND 'python Shopify.py' within the project folder!

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CALLS = 40
RATE_LIMIT = 60
EXCLUDE_TERMS = ["sample", "test", "dummy"]  # Add more as needed

@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def rate_limited_get(url):
    logging.info(f"Requesting URL: {url}")
    response = requests.get(url)
    response.raise_for_status()
    return response


def discover_shopify_stores():
    shopify_stores = []
    try:
        logging.info("Attempting to discover Shopify stores...")
        response = rate_limited_get("https://www.shopify.com/examples")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Print the entire HTML content for debugging
        logging.debug(f"HTML content: {soup.prettify()}")

        # Look for all 'a' tags that might contain store URLs
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Check if the href looks like a store URL
            if href.startswith('http') and 'myshopify.com' not in href:
                shopify_stores.append(href)

        logging.info(f"Discovered {len(shopify_stores)} potential Shopify stores")
        # Print discovered stores for debugging
        for store in shopify_stores:
            logging.debug(f"Discovered store: {store}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error discovering Shopify stores: {e}")
    return shopify_stores

def get_cheap_products(shopify_store_url, query_term, max_price):
    cheap_products = []
    try:
        logging.info(f"Searching for cheap products in {shopify_store_url}")
        response = rate_limited_get(f"{shopify_store_url}/products.json")
        products = response.json().get('products', [])
        logging.info(f"Found {len(products)} products in total")
        for product in products:
            if any(term.lower() in product.get('title', '').lower() for term in EXCLUDE_TERMS):
                continue

            product_matches_query = query_term.lower() in product.get('title', '').lower()
            variant_matches_query = any(
                query_term.lower() in variant.get('title', '').lower() for variant in product.get('variants', []))

            if product_matches_query or variant_matches_query:
                for variant in product.get('variants', []):
                    price = float(variant.get('price', '0'))
                    if price <= max_price and product.get('images'):
                        cheap_products.append({
                            'title': product.get('title'),
                            'variant': variant.get('title'),
                            'price': price,
                            'product_id': variant.get('id'),
                            'url': f"{shopify_store_url}/cart/{variant.get('id')}:1?payment=shop_pay&discount=FREESHIPPING,FREESHIP,SHIPFREE,FREE,SHIP,firstorder"
                        })
        logging.info(f"Found {len(cheap_products)} cheap products matching the query")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error accessing {shopify_store_url}: {e}")
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {shopify_store_url}")
    except Exception as e:
        logging.error(f"Unexpected error processing {shopify_store_url}: {e}")
    return cheap_products

def process_store(store_url, query_term, max_price, result_queue):
    products = get_cheap_products(store_url, query_term, max_price)
    if products:
        result_queue.put((store_url, products))

def scan_stores(query_term, max_price):
    shopify_stores = discover_shopify_stores()
    logging.info(f"Scanning {len(shopify_stores)} stores for query: {query_term} with max price: ${max_price}")
    result_queue = queue.Queue()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_store, store, query_term, max_price, result_queue) for store in shopify_stores]
        for future in concurrent.futures.as_completed(futures):
            logging.info("Completed processing a store")

    all_cheap_products = []
    while not result_queue.empty():
        store_url, products = result_queue.get()
        all_cheap_products.extend(products)
        logging.info(f"Found {len(products)} cheap products from {store_url}")

    return all_cheap_products

def main():
    query_term = input("Enter a product search term: ")
    max_price = float(input("Enter maximum price (default 1.00): ") or 1.00)
    logging.info(f"Starting search for '{query_term}' with max price ${max_price}")
    cheap_products = scan_stores(query_term, max_price)

    if cheap_products:
        logging.info(f"\nFound {len(cheap_products)} cheap products related to '{query_term}':")
        for product in cheap_products:
            logging.info(f"Title: {product['title']} - {product['variant']}, Price: ${product['price']}, URL: {product['url']}")
    else:
        logging.info(f"No cheap products related to '{query_term}' found.")

# Don't forget to update the scan_stores and get_cheap_products function calls to include max_price

if __name__ == '__main__':
    main()
