import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re

class BBCNewsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.5'
        })
        self.base_url = 'https://www.bbc.com'
        self.visited_urls = set()
        self.rate_limit_delay = 0.5  # seconds between requests

    def get_page(self, url):
        """Fetch a page with error handling"""
        try:
            time.sleep(self.rate_limit_delay)
            response = self.session.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_category_links(self, category_url, max_pages=3):
        """Extract article links from a category page with pagination"""
        article_links = set()
        page_num = 1

        while page_num <= max_pages:
            if page_num == 1:
                page_url = category_url
            else:
                page_url = f"{category_url}?page={page_num}"

            print(f"Scraping page {page_num}: {page_url}")
            html = self.get_page(page_url)
            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')

            # Extract article links (adjust selector as needed)
            links = soup.select('a[data-testid="internal-link"]')
            new_links = {
                      urljoin(self.base_url, link['href'])
                      for link in links
                      if (
                          re.match(r'^/news/articles/[a-z0-9]+$', link['href'])  # only exact article URLs
                          and 'live' not in link['href'].lower()  # still exclude live coverage
                      )
                  }


            if not new_links:
                break

            article_links.update(new_links)
            page_num += 1

            # Check if there's a next page
            next_page = soup.select_one('a[aria-label="Next"]')
            if not next_page:
                break

        return list(article_links)[:50]  # Limit to 50 articles max

    def parse_article(self, article_url, category=None):
      """Parse a full article page"""
      if article_url in self.visited_urls:
          return None

      self.visited_urls.add(article_url)
      html = self.get_page(article_url)
      if not html:
          return None

      soup = BeautifulSoup(html, 'html.parser')

      article_data = {
          'url': article_url,
          'title': self._extract_title(soup),
          'timestamp': self._extract_timestamp(soup),
          'author': self._extract_author(soup),
          'category': category or self._extract_category(article_url),
          'tags': self._extract_tags(soup),
          'content': self._extract_content(soup),
          'images': self._extract_images(soup),
          'scraped_at': datetime.utcnow().isoformat()
      }

      return article_data


    def _extract_title(self, soup):
        """Extract article title"""
        title = soup.find('h1', {'class': 'sc-f98b1ad2-0 dfvxux'})
        return title.get_text(strip=True) if title else None

    def _extract_timestamp(self, soup):
        """Extract publication timestamp"""
        time_tag = soup.find('time', class_=re.compile(r'sc-801dd632-2|IvNnh'))
        if time_tag and 'datetime' in time_tag.attrs:
            return time_tag['datetime']
        return None

    def _extract_author(self, soup):
        """Extract author information"""
        author_div = soup.find('div', {'class': 'ssrcss-68pt20-Text-TextContributorName'})
        return author_div.get_text(strip=True) if author_div else None

    def _extract_category(self, url):
        """Extract category name from URL (last part of path)"""
        path = urlparse(url).path
        parts = [p for p in path.split('/') if p]
        return parts[-3] if parts else None

    def _extract_tags(self, soup):
        """Extract article tags"""
        tags = []
        tags_container = soup.find('div', {'class': 'ssrcss-1sh5v2i-TagListWrapper'})
        if tags_container:
            tags = [tag.get_text(strip=True) for tag in tags_container.find_all('li')]
        return tags

    def _extract_content(self, soup):
        """Extract main article content"""
        content_blocks = soup.select('div[data-component="text-block"]')
        return '\n\n'.join(block.get_text(strip=True) for block in content_blocks)

    def _extract_images(self, soup):
        """Extract only the highest resolution image URLs"""
        urls = []

        for img in soup.find_all('img', srcset=True):
            try:
                # Get the largest image from srcset
                largest = max(
                    (entry.strip().split() for entry in img['srcset'].split(',')),
                    key=lambda x: int(x[1].replace('w', '')) if len(x) == 2 else 0
                )
                urls.append(urljoin(self.base_url, largest[0]))
            except:
                continue

        return urls

    def scrape_category(self, category_url, max_pages=3, max_articles=20):
      """Scrape a full category with articles"""
      article_links = self.extract_category_links(category_url, max_pages)
      articles = []

      # Extract category from category_url itself
      category_path = urlparse(category_url).path
      category = category_path.strip('/').split('/')[-1]

      for link in article_links[:max_articles]:
          print(f"Processing: {link}")
          article = self.parse_article(link, category)
          if article:
              articles.append(article)

      return articles


# Example Usage
if __name__ == "__main__":
    scraper = BBCNewsScraper()

    # Scrape business news
    business_articles = scraper.scrape_category(
        category_url='https://www.bbc.com/innovation',
        max_pages=2,
        max_articles=4
    )

    # Save results
    with open('bbc_business_news.json', 'w', encoding='utf-8') as f:
        json.dump(business_articles, f, indent=2, ensure_ascii=False)

    print(f"Scraped {len(business_articles)} articles. Saved to bbc_business_news.json")

