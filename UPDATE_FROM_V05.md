# v0.5.1 Streamlit import hotfix

- Keeps `app.py` and `search.py` from the same release in sync.
- Adds `lxml_html_clean` for cloud environments where lxml HTML Cleaner is a separate package.
- Makes Trafilatura optional at startup; if unavailable, HTML extraction falls back to BeautifulSoup.
- No changes to API keys, database schema, or search behavior.
