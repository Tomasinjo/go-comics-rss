# go-comics-rss
Scrapes GoComics and publishes a RSS feed for selected authors every 10 minutes.

# Installation
1. Download `docker-compose.yml` and `config.toml`  
2. Modify `docker-compose.yml` variables:  
   `GO_COMICS_AUTHORS` - list of GoComics authors to publish  
   `FEED_DOMAIN` - domain where your RSS feed will be hosted  
   `FEED_MAX_AGE_DAYS` - maximum age (days) of comics in the feed  
   `FEED_INITIAL_FETCH_DAYS_BACK` - (optional) on the first run, fetch comics of selected authors for X days back.  
3. Modify config.toml: change `host` to same domain as `FEED_DOMAIN`  
4. Run with `docker-compose up -d`  
5. Go to set domain e.g. `http://rss.example.com:8882`  
