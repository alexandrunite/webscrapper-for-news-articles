import asyncio
import aiohttp
import aiosqlite
import configparser
import logging
import os
import re
import sys
from aiofiles import open as aio_open
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template
from textblob import TextBlob
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
import requests
import threading
from flask_socketio import SocketIO, emit
import eventlet
from flask import Flask, jsonify, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import User
from flask_bcrypt import Bcrypt
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import pandas as pd
from fpdf import FPDF
from flask import send_file
import random
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration


config = configparser.ConfigParser()
config.read('config.ini')

API_KEY = config.get('openai', 'api_key')
GECKODRIVER_PATH = config.get('webdriver', 'geckodriver_path')
FIREFOX_BINARY_PATH = config.get('webdriver', 'firefox_binary_path')
HEADLESS_MODE = config.getboolean('webdriver', 'headless')
PROXY_LIST = config.get('proxy', 'proxies').split(',')

DATABASE_PATH = 'articles.db'

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

app = Flask(__name__)
eventlet.monkey_patch()
socketio = SocketIO(app, async_mode='eventlet')
# In scraper.py or a separate init script
async def init_database():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT,
                title TEXT,
                link TEXT UNIQUE,
                summary TEXT,
                sentiment REAL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT
            )
        ''')
        await db.commit()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

bcrypt = Bcrypt(app)

sentry_sdk.init(
    dsn=config.get('sentry', 'dsn'),
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0
)

async def load_proxies(file_name):
    if not os.path.exists(file_name):
        logging.error(f"Proxies file not found: {file_name}")
        return []
    async with aio_open(file_name, 'r', encoding='utf-8') as file:
        return [line.strip() for line in await file.readlines() if line.strip()]
    
class WebScraper:
    def __init__(self, sites, keywords):
        self.sites = sites
        self.keywords_list = keywords
        self.proxies = proxies
        self.driver = self.initialize_driver()

    def get_random_proxy(self):
        if self.proxies:
            return random.choice(self.proxies)
        return None
    
    def initialize_driver(self):
        options = Options()
        options.binary_location = FIREFOX_BINARY_PATH
        options.headless = HEADLESS_MODE
        proxy = self.get_random_proxy()
        if proxy:
            options.set_preference("network.proxy.type", 1)
            proxy_parts = proxy.split(':')
            if proxy_parts[0].startswith('http'):
                proxy_type = 'http'
            else:
                proxy_type = 'http'
            options.set_preference("network.proxy.http", proxy_parts[1].replace('//', ''))
            options.set_preference("network.proxy.http_port", int(proxy_parts[2]))
            options.set_preference("network.proxy.ssl", proxy_parts[1].replace('//', ''))
            options.set_preference("network.proxy.ssl_port", int(proxy_parts[2]))
        service = Service(executable_path=GECKODRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=options)
        return driver

    def rotate_proxy(self):
        proxy = self.get_random_proxy()
        if proxy:
            self.driver.quit()
            self.driver = self.initialize_driver()
            logging.info(f"Rotated to new proxy: {proxy}")

    def extract_keywords(self, line):
        return re.findall(r"'(.*?)'", line)

    def get_proxy(self, site):
        if PROXY_LIST:
            return PROXY_LIST[hash(site) % len(PROXY_LIST)]
        return None

    def process_site(self, site, keywords):
        try:
            self.driver.get(site)
            WebDriverWait(self.driver, 10).until(lambda d: d.find_element(By.TAG_NAME, "body"))
        except TimeoutException:
            logging.error(f"Timeout while loading {site}")
            self.rotate_proxy()
            return
        except WebDriverException as e:
            logging.error(f"WebDriverException while loading {site}: {e}")
            self.rotate_proxy()
            return
        for keyword in keywords:
            try:
                articles = self.driver.find_elements(By.PARTIAL_LINK_TEXT, keyword)
                for article in articles:
                    title = article.get_attribute('textContent').strip()
                    link = article.get_attribute('href').strip()
                    if title and link:
                        logging.info(f"Found article with keyword '{keyword}': '{title}'")
                        summary = self.generate_summary(self.fetch_page(link, self.get_random_proxy()))
                        sentiment = self.analyze_sentiment(summary)
                        self.save_article(site, title, link, summary, sentiment)
            except NoSuchElementException:
                logging.warning(f"No elements found for keyword '{keyword}' on site {site}")
            except WebDriverException as e:
                logging.error(f"WebDriverException for keyword '{keyword}' on site {site}: {e}")
                self.rotate_proxy()

    def fetch_page(self, url, proxy=None):
        try:
            session = requests.Session()
            if proxy:
                session.proxies.update({
                    'http': proxy,
                    'https': proxy
                })
            response = session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None

    def generate_summary(self, text):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": f"Given the following text, give me a short summary of it :{text}"
                }
            ],
            "max_tokens": 100
        }
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            summary = data['choices'][0]['message']['content'].strip()
            return summary
        except requests.RequestException as e:
            logging.error(f"OpenAI API error: {e}")
            return None

    def analyze_sentiment(self, text):
        if text:
            analysis = TextBlob(text)
            return analysis.sentiment.polarity
        return 0

    def save_article(self, site, title, link, summary, sentiment):
        asyncio.run(self.async_save_article(site, title, link, summary, sentiment))

    # scraper.py
async def async_save_article(self, site, title, link, summary, sentiment):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute('''
                INSERT INTO articles (site, title, link, summary, sentiment)
                VALUES (?, ?, ?, ?, ?)
            ''', (site, title, link, summary, sentiment))
            await db.commit()
            logging.info(f"Article saved: {title}")
            # Emit real-time update
            socketio.emit('new_article', {
                'site': site,
                'title': title,
                'link': link,
                'summary': summary,
                'sentiment': sentiment
            })
            # Send email notifications
            await self.send_email_notifications(site, title, link, summary, sentiment)
        except aiosqlite.IntegrityError:
            logging.debug(f"Article already exists: {title}")

async def send_email_notifications(self, site, title, link, summary, sentiment):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute('SELECT email FROM users') as cursor:
            users = await cursor.fetchall()
            for user in users:
                email = user[0]
                msg = Message('New Article Alert',
                              sender=app.config['MAIL_USERNAME'],
                              recipients=[email])
                msg.body = f"""
                A new article has been scraped:

                Site: {site}
                Title: {title}
                Link: {link}
                Summary: {summary}
                Sentiment: {sentiment}
                """
                try:
                    mail.send(msg)
                    logging.info(f"Email sent to {email} for article '{title}'")
                except Exception as e:
                    logging.error(f"Failed to send email to {email}: {e}")


    def process_site(self, site, keywords):
        try:
            self.driver.get(site)
            WebDriverWait(self.driver, 10).until(lambda d: d.find_element(By.TAG_NAME, "body"))
        except TimeoutException:
            logging.error(f"Timeout while loading {site}")
            return
        for keyword in keywords:
            try:
                articles = self.driver.find_elements(By.PARTIAL_LINK_TEXT, keyword)
                for article in articles:
                    title = article.get_attribute('textContent').strip()
                    link = article.get_attribute('href').strip()
                    if title and link:
                        logging.info(f"Found article with keyword '{keyword}': '{title}'")
                        summary = self.generate_summary(self.fetch_page(link, self.get_proxy(site)))
                        sentiment = self.analyze_sentiment(summary)
                        self.save_article(site, title, link, summary, sentiment)
            except NoSuchElementException:
                logging.warning(f"No elements found for keyword '{keyword}' on site {site}")
            except WebDriverException as e:
                logging.error(f"WebDriverException for keyword '{keyword}' on site {site}: {e}")

    def scrape(self):
        sites = asyncio.run(self.load_file('sites.txt'))
        keywords_list = asyncio.run(self.load_file('keywords.txt'))
        if len(sites) != len(keywords_list):
            logging.error("The number of sites and keywords must match.")
            return
        for i, site in enumerate(sites):
            keywords = self.extract_keywords(keywords_list[i])
            self.process_site(site, keywords)
        self.driver.quit()

    async def load_file(self, file_name):
        if not os.path.exists(file_name):
            logging.error(f"File not found: {file_name}")
            return []
        async with aio_open(file_name, 'r', encoding='utf-8') as file:
            return [line.strip() for line in await file.readlines()]

# scraper.py
async def scrape_task():
    try:
        sites = await load_file('sites.txt')
        keywords_list = await load_file('keywords.txt')
        proxies = await load_proxies(config.get('proxy', 'proxies_file'))
        scraper = WebScraper(sites, keywords_list, proxies)
        scraper.scrape()
    except Exception as e:
        logging.error(f"An unexpected error occurred during scraping: {e}")
        sentry_sdk.capture_exception(e)

async def load_file(file_name):
    if not os.path.exists(file_name):
        logging.error(f"File not found: {file_name}")
        return []
    async with aio_open(file_name, 'r', encoding='utf-8') as file:
        return [line.strip() for line in await file.readlines()]

@login_manager.user_loader
async def load_user(user_id):
    return await User.get(user_id)

@app.route('/register', methods=['GET', 'POST'])
async def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        success = await User.create(username, email, password)
        if success:
            user = await User.find_by_username(username)
            login_user(user)
            flash('Registration successful.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Username or email already exists.', 'danger')
    return await render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = await User.find_by_username(username)
        if user and user.verify_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    return await render_template('login.html')

@app.route('/logout')
@login_required
async def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/api/articles', methods=['GET'])
async def get_articles():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute('SELECT site, title, link, summary, sentiment FROM articles')
        articles = await cursor.fetchall()
    return jsonify(articles)


@app.route('/export/csv')
@login_required
async def export_csv():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute('SELECT site, title, link, summary, sentiment FROM articles')
        articles = await cursor.fetchall()
    df = pd.DataFrame(articles, columns=['Site', 'Title', 'Link', 'Summary', 'Sentiment'])
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    mem = io.BytesIO()
    mem.write(csv_buffer.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, mimetype='text/csv', attachment_filename='articles.csv', as_attachment=True)

@app.route('/export/pdf')
@login_required
async def export_pdf():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute('SELECT site, title, link, summary, sentiment FROM articles')
        articles = await cursor.fetchall()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for article in articles:
        pdf.multi_cell(0, 10, f"Site: {article[0]}\nTitle: {article[1]}\nLink: {article[2]}\nSummary: {article[3]}\nSentiment: {article[4]}\n\n")
    mem = io.BytesIO()
    pdf.output(mem)
    mem.seek(0)
    return send_file(mem, mimetype='application/pdf', attachment_filename='articles.pdf', as_attachment=True)

@app.route('/')
async def index():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute('SELECT site, title, link, summary, sentiment FROM articles')
        articles = await cursor.fetchall()
    return await render_template('index.html', articles=articles)

@app.route('/analytics')
@login_required
async def analytics():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute('SELECT sentiment FROM articles')
        sentiments = await cursor.fetchall()
        cursor = await db.execute('SELECT site, COUNT(*) as count FROM articles GROUP BY site')
        site_counts = await cursor.fetchall()

    # Sentiment Distribution Plot
    sentiments = [s[0] for s in sentiments]
    plt.figure(figsize=(8, 6))
    sns.histplot(sentiments, bins=20, kde=True)
    plt.title('Sentiment Distribution')
    plt.xlabel('Sentiment Polarity')
    plt.ylabel('Frequency')
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    sentiment_plot = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    # Articles per Site Plot
    sites = [s[0] for s in site_counts]
    counts = [s[1] for s in site_counts]
    plt.figure(figsize=(10, 6))
    sns.barplot(x=sites, y=counts)
    plt.title('Number of Articles per Site')
    plt.xlabel('Site')
    plt.ylabel('Number of Articles')
    plt.xticks(rotation=45)
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    site_plot = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    return await render_template('analytics.html', sentiment_plot=sentiment_plot, site_plot=site_plot)

def run_flask():
    socketio.run(app, host='0.0.0.0', port=5000, use_reloader=False)

async def scrape_task():
    sites = await load_file('sites.txt')
    keywords_list = await load_file('keywords.txt')
    proxies = await load_proxies(config.get('proxy', 'proxies_file'))
    scraper = WebScraper(sites, keywords_list, proxies)
    scraper.scrape()

def main():
    asyncio.run(init_database())
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scrape_task, 'interval', hours=6)
    scheduler.start()
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        flask_thread.join()


if __name__ == "__main__":
    main()
