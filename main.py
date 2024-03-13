from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from openai import OpenAI
import re
import requests


# Specify the path to your geckodriver here
geckodriver_path = r"C:\Users\admin\Desktop\gecko\geckodriver.exe"
api_key = ""

def load_file(file_name):
    with open(file_name, 'r') as file:
        return file.read().splitlines()

def save_existing_articles(existing_articles):
    with open('existingarticles.txt', 'w') as file:
        for line in existing_articles:
            file.write(line + '\n')

def save_hyperlinks(existing_hyperlinks):
    with open('hyperlinks.txt', 'w') as file:
        for line in existing_hyperlinks:
            file.write(line + '\n')

def extract_keywords(line):
    return re.findall(r"'(.*?)'", line)

def initialize_driver(executable_path):
    options = Options()
    options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"  # Replace with your Firefox binary path
    options.headless = True  # Run headless or not depending on preference
    service = Service(executable_path=executable_path)
    driver = webdriver.Firefox(service=service, options=options)
    return driver

def summary_generator(text):
    headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
    }
    payload = {
    "model": "gpt-4-vision-preview",
    "messages": [
        {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": f"Given the following text, give me a short summary of it :{text}"
            },
            
        ]
        }
    ],
    "max_tokens": 100
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    print(response.json())
    datele=response.json()
    summary=datele['choices'][0]['message']['content']
    return summary

driver = None
try:
    driver = initialize_driver(geckodriver_path)
    
    sites = load_file('sites.txt')
    keywords_list = load_file('keywords.txt')
    existing_articles_lines = load_file('existingarticles.txt')
    existing_hyperlinks_lines = load_file('hyperlinks.txt')

    existing_articles_lines += [""] * (len(sites) - len(existing_articles_lines))
    existing_hyperlinks_lines += [""] * (len(sites) - len(existing_hyperlinks_lines))

    
    for i, site in enumerate(sites):
        try:
            driver.get(site)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            print(f"Timeout while loading {site}")
            continue
        
        keywords = extract_keywords(keywords_list[i])
        existing_articles = existing_articles_lines[i].split(", ") if existing_articles_lines[i] else []
        existing_hyperlinks = existing_hyperlinks_lines[i].split(", ") if existing_hyperlinks_lines[i] else []
    
        for keyword in keywords:
            try:
                articles = driver.find_elements(By.PARTIAL_LINK_TEXT, keyword)
                for article in articles:
                    title = article.get_attribute('textContent').strip()
                    link = article.get_attribute('href').strip()
                    if title:
                        print(f"Found article with keyword '{keyword}': '{title}'")
                        # Only add the hyperlink if the title hasn't been added yet
                        if all(title.lower() != ea.lower().strip("'") for ea in existing_articles):
                            existing_articles.append(f"'{title}'")
                        if all(link.lower() != eh.lower().strip("'") for eh in existing_hyperlinks):
                            print(f"Saving hyperlink for found article: {link}")
                            existing_hyperlinks.append(f"'{link}'")  # Always save unique hyperlink
                            
                    try:
                        driver1=r"C:\Users\admin\Desktop\gecko\geckodriver.exe"
                        driver1.get(link)
                        body_element=driver1.find_element_by_tag_name('body')
                        article_text=body_element.text
                        summarized=summary_generator(article_text)
                    # Remove 'break' to allow processing of all articles that match the keyword
    
            except NoSuchElementException:
                print(f"No elements found for keyword '{keyword}' on site {site}")
            except WebDriverException as e:
                print(f"Error processing articles for keyword '{keyword}' on site {site}: {e}")
    
        existing_articles_lines[i] = ", ".join(existing_articles)
        existing_hyperlinks_lines[i] = ", ".join(existing_hyperlinks)

    save_existing_articles(existing_articles_lines)
    save_hyperlinks(existing_hyperlinks_lines)

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    if driver:
        driver.quit()
