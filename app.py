from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import random
import time

app = Flask(__name__)
CORS(app)

BASE_URL = "https://www.dimakids.com/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Referer': BASE_URL
}

LETTERS_LIST = [
    ("الكل", "all-tri.html"), ("ا", "0-tri.html"), ("ب", "1-tri.html"), ("ت", "2-tri.html"),
    ("ث", "3-tri.html"), ("ج", "4-tri.html"), ("ح", "5-tri.html"), ("خ", "6-tri.html"),
    ("د", "7-tri.html"), ("ذ", "8-tri.html"), ("ر", "9-tri.html"), ("ز", "10-tri.html"),
    ("س", "11-tri.html"), ("ش", "12-tri.html"), ("ص", "13-tri.html"), ("ض", "14-tri.html"),
    ("ط", "15-tri.html"), ("ع", "16-tri.html"), ("غ", "17-tri.html"), ("ف", "18-tri.html"),
    ("ق", "19-tri.html"), ("ك", "20-tri.html"), ("ل", "21-tri.html"), ("م", "22-tri.html"),
    ("ن", "23-tri.html"), ("ه", "24-tri.html"), ("و", "25-tri.html"), ("ي", "26-tri.html")
]

def get_html(url):
    try:
        full_url = url if url.startswith('http') else urllib.parse.urljoin(BASE_URL, url)
        response = requests.get(full_url, headers=HEADERS, timeout=15)
        response.encoding = 'utf-8'
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def extract_items(soup, full_url):
    items_out = []
    grid = soup.find('div', class_='series-grid-swiper') or soup.find('div', class_='search-results-container')
    items = grid.find_all('a', href=True) if grid else soup.select('a[href*=".html"]')

    for item in items:
        title = item.get('title') or item.text.strip()
        href = item.get('href')
        if not href or 'javascript' in href or href == '#' or 'reading' in href:
            continue
        link = urllib.parse.urljoin(full_url, href)
        img_tag = item.find('img')
        thumb = img_tag.get('src') if img_tag else ""
        if thumb:
            thumb = urllib.parse.urljoin(full_url, thumb)
        if title:
            items_out.append({'title': title, 'link': link, 'thumb': thumb})
    return items_out

def find_next_page(soup, full_url):
    next_url = None
    current_page = 1
    nav = soup.find(class_=re.compile(r'pagin|page-nav', re.I))
    if nav:
        active_elem = nav.find(class_=re.compile(r'active|current|selected'))
        if active_elem and active_elem.text.strip().isdigit():
            current_page = int(active_elem.text.strip())
        else:
            m = re.search(r'(?:page|p)[=/](\d+)', full_url)
            if m: current_page = int(m.group(1))
        target_str = str(current_page + 1)
        for a in nav.find_all('a', href=True):
            if a.text.strip() == target_str:
                next_url = a['href']
                break
        if not next_url:
            for a in nav.find_all('a', href=True):
                txt = a.text.strip()
                if 'التالي' in txt or '»' in txt or 'next' in a.get('class', []) or '>' in txt:
                    next_url = a['href']
                    break
    if not next_url:
        for a in soup.find_all('a', href=True):
            if 'التالي' in a.text.strip() or 'الصفحة التالية' in a.text.strip():
                next_url = a['href']
                break
    if next_url:
        next_url = urllib.parse.urljoin(full_url, next_url)
    return next_url, current_page

def extract_stream_url(full_url, html, soup):
    stream_url = ""
    match = re.search(r'(https?://[^\s\'"]+\.mp4[^\s\'"]*)', html)
    if match: stream_url = match.group(1)
    if not stream_url:
        match_clappr = re.search(r'const\s+videoSrc\s*=\s*["\'](.*?)["\']', html)
        if match_clappr: stream_url = match_clappr.group(1)
    if not stream_url:
        video_tag = soup.find('video')
        if video_tag:
            if video_tag.get('src'): stream_url = video_tag['src']
            else:
                source_tag = video_tag.find('source')
                if source_tag and source_tag.get('src'): stream_url = source_tag['src']
    if not stream_url:
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'): stream_url = iframe['src']
    if stream_url and 'foupix' in stream_url and '&_=' not in stream_url:
        stream_url += f"&_={int(time.time() * 1000)}"
    return stream_url

@app.route('/api/series', methods=['GET'])
def api_series():
    page = request.args.get('page', '1')
    url = f"cartoon.php?page={page}" if page != '1' else "cartoon.php"
    full_url = urllib.parse.urljoin(BASE_URL, url)
    html = get_html(full_url)
    soup = BeautifulSoup(html, 'html.parser')
    items = extract_items(soup, full_url)
    next_url, current_page = find_next_page(soup, full_url)
    return jsonify({'items': items, 'next_page': next_url, 'current_page': current_page})

@app.route('/api/letters', methods=['GET'])
def api_letters():
    return jsonify([{'label': l, 'url': u} for l, u in LETTERS_LIST])

@app.route('/api/movies', methods=['GET'])
def api_movies():
    page = request.args.get('page', '1')
    url = f"movies.php?page={page}" if page != '1' else "movies.php"
    full_url = urllib.parse.urljoin(BASE_URL, url)
    html = get_html(full_url)
    soup = BeautifulSoup(html, 'html.parser')
    items = extract_items(soup, full_url)
    next_url, current_page = find_next_page(soup, full_url)
    return jsonify({'items': items, 'next_page': next_url, 'current_page': current_page})

@app.route('/api/episodes', methods=['GET'])
def api_episodes():
    url = request.args.get('url')
    if not url: return jsonify({'error': 'URL required'}), 400
    full_url = urllib.parse.urljoin(BASE_URL, url)
    html = get_html(full_url)
    soup = BeautifulSoup(html, 'html.parser')
    grid = soup.find('div', class_='episodes-grid')
    if not grid: return jsonify({'items': [], 'error': 'No episodes found'})
    episodes = grid.find_all('a', href=True)
    items = []
    for ep in episodes:
        href = ep.get('href')
        title = ep.get('title') or ep.find('div', class_='cinema-title').text.strip() if ep.find('div', class_='cinema-title') else "حلقة"
        img_tag = ep.find('img')
        thumb = img_tag.get('src') if img_tag else ""
        link = urllib.parse.urljoin(full_url, href)
        if thumb: thumb = urllib.parse.urljoin(full_url, thumb)
        items.append({'title': title, 'link': link, 'thumb': thumb})
    return jsonify({'items': items})

@app.route('/api/play', methods=['GET'])
def api_play():
    url = request.args.get('url')
    if not url: return jsonify({'error': 'URL required'}), 400
    full_url = urllib.parse.urljoin(BASE_URL, url)
    html = get_html(full_url)
    soup = BeautifulSoup(html, 'html.parser')
    stream_url = extract_stream_url(full_url, html, soup)
    if stream_url:
        return jsonify({'stream_url': stream_url, 'referer': full_url})
    return jsonify({'error': 'Video stream not found'}), 404

@app.route('/api/search', methods=['GET'])
def api_search():
    q = request.args.get('q')
    if not q: return jsonify({'items': []})
    search_url = f"search_results.php?q={urllib.parse.quote_plus(q)}"
    full_url = urllib.parse.urljoin(BASE_URL, search_url)
    html = get_html(full_url)
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find_all('a', class_='result-card')
    results = []
    for item in items:
        href = item.get('href')
        if not href: continue
        link = urllib.parse.urljoin(full_url, href)
        title_tag = item.find('h3', class_='result-title')
        title = title_tag.text.strip() if title_tag else "بدون عنوان"
        img_tag = item.find('img', class_='result-image')
        thumb = img_tag.get('src') if img_tag else ""
        if thumb: thumb = urllib.parse.urljoin(full_url, thumb)
        type_span = item.find('span', class_='result-type')
        type_class = type_span.get('class', []) if type_span else []
        if 'book' in type_class: continue
        results.append({'title': title, 'link': link, 'thumb': thumb, 'type': 'movie' if 'movie' in type_class else 'series'})
    return jsonify({'items': results})

@app.route('/api/random', methods=['GET'])
def api_random():
    force_series = request.args.get('series_only', 'false').lower() == 'true'
    for _ in range(10):
        if force_series: content_type = 'series'
        else: content_type = random.choice(['series', 'movies'])
        if content_type == 'series':
            letters_only = [u for l, u in LETTERS_LIST if l != "الكل"]
            full_url = urllib.parse.urljoin(BASE_URL, random.choice(letters_only))
        else:
            full_url = urllib.parse.urljoin(BASE_URL, 'movies.php')
        html = get_html(full_url)
        soup = BeautifulSoup(html, 'html.parser')
        items = extract_items(soup, full_url)
        if not items: continue
        chosen = random.choice(items)
        if content_type == 'movies':
            page_url = chosen['link']
        else:
            html2 = get_html(chosen['link'])
            soup2 = BeautifulSoup(html2, 'html.parser')
            grid = soup2.find('div', class_='episodes-grid')
            episodes = grid.find_all('a', href=True) if grid else []
            if not episodes: page_url = chosen['link']
            else:
                ep = random.choice(episodes)
                page_url = urllib.parse.urljoin(chosen['link'], ep.get('href', ''))
        html3 = get_html(page_url)
        soup3 = BeautifulSoup(html3, 'html.parser')
        stream_url = extract_stream_url(page_url, html3, soup3)
        if stream_url:
            return jsonify({'title': chosen['title'], 'stream_url': stream_url, 'referer': page_url})
    return jsonify({'error': 'Could not find random video'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
