import sys

import requests
from bs4 import BeautifulSoup

if len(sys.argv) < 2:
    print("Usage: python try_googlemap.py <short_url>")
    sys.exit(1)

short_url = sys.argv[1]

response = requests.get(short_url, allow_redirects=True)


soup = BeautifulSoup(response.text, 'html.parser')

meta_tag = soup.find('meta', property='og:title')
if meta_tag and meta_tag.get('content'):
    shop_name = meta_tag['content']
    print("Shop name (from meta):", shop_name)
else:
    print("Shop name not found in meta tag.")
