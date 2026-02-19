"""
LinkedIn posting via Selenium (web automation) - fallback when API not available.

Requirements:
  - Python `selenium` package
  - Chrome and matching chromedriver in PATH (or change to use Firefox/geckodriver)

Usage:
  - Set env `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD` for login
  - Run: `python linkedin_selenium.py --title "Job Title" --company "Acme" --apply "https://..." --description "Short description..."`

Warning: automating browser may violate LinkedIn terms of service; use with caution.
"""
import os
import time
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def linkedin_login(driver, email, password):
    driver.get("https://www.linkedin.com/login")
    wait = WebDriverWait(driver, 15)
    email_el = wait.until(EC.presence_of_element_located((By.ID, "username")))
    email_el.clear()
    email_el.send_keys(email)
    pwd_el = driver.find_element(By.ID, "password")
    pwd_el.clear()
    pwd_el.send_keys(password)
    pwd_el.send_keys(Keys.ENTER)

    # wait for home page
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "global-nav-search")))


def create_linkedin_post(driver, text):
    wait = WebDriverWait(driver, 15)
    # Click start post
    start_post = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.share-box-feed-entry__trigger, button.share-box__open")))
    start_post.click()

    # Wait for composer
    composer = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ql-editor.ql-blank, div.share-box__open--legacy textarea, div.comments-comments-list")))
    # Try sending text via active contenteditable if present
    try:
        editable = driver.find_element(By.CSS_SELECTOR, "div.ql-editor")
        editable.click()
        editable.send_keys(text)
    except Exception:
        # fallback to textarea
        try:
            ta = driver.find_element(By.CSS_SELECTOR, "div.share-box__open--legacy textarea")
            ta.click()
            ta.send_keys(text)
        except Exception:
            # last resort paste via Actions
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(text)

    time.sleep(1)
    # Click Post button
    post_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Post') or contains(., 'Share')]")))
    post_btn.click()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--apply", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    email = os.getenv("LINKEDIN_EMAIL")
    pwd = os.getenv("LINKEDIN_PASSWORD")
    if not email or not pwd:
        raise ValueError("Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD env vars for Selenium login")

    text = f"{args.title} at {args.company}\n\n{args.description}\n\nApply: {args.apply}"

    options = webdriver.ChromeOptions()
    if args.headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        linkedin_login(driver, email, pwd)
        create_linkedin_post(driver, text)
        print("Posted via Selenium")
    finally:
        driver.quit()


if __name__ == '__main__':
    main()
