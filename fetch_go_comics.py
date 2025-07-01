import os
import re
import time
import json
import logging
from datetime import datetime, timedelta
import requests
from feedgen.feed import FeedGenerator

host_domain = os.getenv("FEED_DOMAIN", "localhost")
authors = os.getenv("GO_COMICS_AUTHORS", "clayjones, michaelramirez").split(",")
max_age_days = int(os.getenv("FEED_MAX_AGE_DAYS", "10")) # Maximum age of entries in days

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "RSC": "1",
    "baggage": ",sentry-environment=production,sentry-public_key=d737dd1e081a47368ee702bbceead4b7,sentry-trace_id=5e697e58545149458e1a82739be86050,sentry-sampled=false,sentry-sample_rand=0.7335553986901457,sentry-sample_rate=0.02",
    "Priority": "u=4",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

feed_info = {
    "title": "GoComics Daily",
    "link": f"https://{host_domain}/feed.xml",
    "description": "Fresh comics from GoComics",
    "language": "en"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_today_date() -> tuple[str, datetime]:
    now = datetime.now()
    date_str = now.strftime("%Y/%m/%d")
    return date_str

def load_past_entries() -> dict:
    try:
        with open("output/feed.json", "rb") as f:
            all_feeds = f.read()
    except FileNotFoundError:
        all_feeds = "{}"
    if not all_feeds:
        all_feeds = "{}"
    return json.loads(all_feeds)


def get_comic_data(date, author) -> tuple[str, str]:
    id_ = None
    title = None
    url = f"https://www.gocomics.com/{author}/{date}?_rsc=14q28"
    logging.info(f"Fetching comic data from: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred: {e}")

    for line in response.text.split("\n"):
        if "og:image" in line:
            id_ = re.search(r'gocomics.com/assets/([a-zA-Z0-9_]*)', line)
            title = re.search(r'children":"(.*?)"', line)
            if id_:
                id_ = id_.group(1)
            if title:
                title = title.group(1)
            return id_, title
    return id_, title


def fetch_comic_metadata(image_id: str) -> tuple[str, str, str]:
    image_url = f"https://featureassets.gocomics.com/assets/{image_id}"
    image_mime_type = "image/jpeg"
    image_length = "0"
    logging.info(f"Fetching metadata for: {image_url}")
    try:
        # Use a HEAD request to be efficient (don"t download the whole image)
        response = requests.head(image_url, allow_redirects=True, timeout=10)
        response.raise_for_status()

        # Get the required metadata
        image_mime_type = response.headers.get("Content-Type", "image/jpeg")
        image_length = response.headers.get("Content-Length", "0")

        logging.info(f"-> Success! Type: {image_mime_type}, Size: {image_length} bytes")

    except requests.RequestException as e:
        logging.error(f"Error fetching image metadata: {e}")
    
    return image_url, image_mime_type, image_length


def initialize_feed() -> FeedGenerator:
    fg = FeedGenerator()
    fg.title(feed_info["title"])
    fg.link(href=feed_info["link"], rel="self")
    fg.description(feed_info["description"])
    fg.language(feed_info["language"])
    return fg


def create_feed_entry(fg, all_feeds: dict) -> str:
    for author, comics in all_feeds.items():
        for comic in comics:
            fe = fg.add_entry() # Create a new entry (item)

            fe.title(comic["title"])
            fe.description(
                f"""<p>{comic["title"]}</p><img src="{comic["image_url"]}" alt="{comic["title"]}" />"""
            )
    return fg.rss_str(pretty=True)


def cleanup_feed(all_feeds: dict) -> dict:
    """
    Cleanup the feed by removing entries older than defined days.
    """
    now = datetime.now()
    cutoff_date = now.timestamp() - (max_age_days * 24 * 3600)
    for author, comics in all_feeds.items():
        all_feeds[author] = [
            comic for comic in comics if datetime.strptime(comic["date"], "%Y/%m/%d").timestamp() > cutoff_date
        ]
    
    return all_feeds


def main(date_str):
    #date_str = "2025/06/30"  # For testing purposes, use a fixed date
    all_feeds = load_past_entries()

    fg = initialize_feed()
    changes_cnt = 0
    for author in authors:
        author = author.strip()
        if not all_feeds.get(author):
            all_feeds[author] = []
        
        if [i for i in all_feeds[author] if i["date"] == date_str]:
            logging.info(f"Comic for {author} on {date_str} already exists. Skipping...")
            continue

        id_, title = get_comic_data(date_str, author)
        if not id_ or not title:
            logging.info(f"Failed to fetch comic data for {author} on {date_str}. Skipping...")
            continue

        image_url, image_mime_type, image_length = fetch_comic_metadata(id_)
        all_feeds[author].append({
            "title": title,
            "image_url": image_url,
            "image_mime_type": image_mime_type,
            "image_length": image_length,
            "date": date_str
        })
        changes_cnt += 1

    if changes_cnt == 0:
        logging.debug(f"No new comics found for {date_str}. Skipping feed generation.")
        return
    
    rss_feed_str = create_feed_entry(fg, all_feeds)
    all_feeds = cleanup_feed(all_feeds)

    with open("output/feed.rss", "wb") as f:
        f.write(rss_feed_str)
    with open("output/feed.json", "wb") as f:
        f.write(json.dumps(all_feeds, indent=4).encode("utf-8"))

    logging.info(f"\nSuccessfully generated RSS feed and saved it")


if __name__ == "__main__":
    days_back = os.getenv("FEED_INITIAL_FETCH_DAYS_BACK")
    if not load_past_entries() and days_back:
        logging.info(f"No past entries found. Fetching comics from {days_back} days ago...")
        for days in range(int(days_back)):
            date_str = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
            logging.info(f"Fetching comics for date: {date_str}")
            main(date_str)

    while True:
        try:
            date_str = get_today_date()
            main(date_str)
        except Exception as e:
            logging.error(f"An error occurred: {e}")
        time.sleep(600)