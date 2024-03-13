# Web Scraping and Text Summarization Using Selenium and OpenAI

This is a Python application that uses the `Selenium` library for web scraping and `OpenAi` API for generating summaries of the scraped articles.

## Setup and Requirements

Make sure you have Python installed on your system. You can download it from [here](https://www.python.org/downloads/). 

The required modules are:

- selenium
- requests
- re
- openai (Make sure to have an API key as well)

You can install them using pip:

```bash
pip install selenium requests openai
```

**Geckodriver**
You'll need the geckodriver for Firefox, which you can download it from [here](https://github.com/mozilla/geckodriver/releases). The driver must be in PATH or specify its location when initializing WebDriver.

```python
geckodriver_path = r"C:\Users\admin\Desktop\gecko\geckodriver.exe"
```

**OpenAI**
For OpenAI API key, sign up on their website and replace the `api_key` variable with your API key.

```python
api_key = "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"
```

## How It Works

It scrapes multiple websites for any articles containing specified keywords. The script saves any new articles found and it also generates a short summary of them using the 'openai' API.

A sample structure of `sites.txt`, `keywords.txt`, `existingarticles.txt`, `hyperlinks.txt` must be prepared before running the script.

Run the script with command:
```bash
python main.py
```
Finally, the processed information is saved in `existingarticles.txt` and `hyperlinks.txt`.

**Note:** Error handling is included to handle circumstances where a website doesn't load, an article doesn't exist, or if other Selenium WebDriver exceptions occur.

Please make sure you have all the necessary permissions before scraping any website and respect their `robots.txt` and usage policies.