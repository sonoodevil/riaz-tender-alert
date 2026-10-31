import os
import json
import csv
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Environment Variables
TENDER_URLS = os.environ.get("TENDER_URLS", "").split(",")
TARGET_KEYWORDS = [k.strip().lower() for k in os.environ.get("TARGET_KEYWORDS", "").split(",") if k.strip()]
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
WHATSAPP_TO = os.environ.get("WHATSAPP_TO")
CSV_PATH = os.environ.get("CSV_PATH", "tender_results.csv")
STATE_FILE = "tender_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"seen": {}, "last_run": None}

def save_state(state):
    state["last_run"] = datetime.utcnow().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def append_to_csv(matches):
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date Found", "Title", "URL", "Matched Keywords"])
        for item in matches:
            writer.writerow([
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                item["title"],
                item["url"],
                ", ".join(item["keywords"])
            ])

def send_whatsapp(message):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID or not WHATSAPP_TO:
        print("WhatsApp credentials missing. Skipping notification.")
        return
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_TO,
        "type": "text",
        "text": {"body": message}
    }
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code == 200:
        print("WhatsApp message sent successfully!")
    else:
        print(f"Failed to send WhatsApp message: {res.text}")

def scrape_url(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    found = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return found
        soup = BeautifulSoup(response.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            link_text = a_tag.get_text(strip=True)
            link_url = urllib.parse.urljoin(url, a_tag["href"])
            combined_text = f"{link_text} {link_url}".lower()
            matched = [kw for kw in TARGET_KEYWORDS if kw in combined_text]
            if matched and link_text:
                found.append({
                    "title": link_text,
                    "url": link_url,
                    "keywords": list(set(matched))
                })
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return found

def main():
    state = load_state()
    seen = state.get("seen", {})
    new_matches = []

    for site_url in TENDER_URLS:
        site_url = site_url.strip()
        if not site_url:
            continue
        print(f"Scraping {site_url}...")
        results = scrape_url(site_url)
        for item in results:
            item_id = item["url"]
            if item_id not in seen:
                seen[item_id] = datetime.utcnow().isoformat()
                new_matches.append(item)

    if new_matches:
        print(f"Found {len(new_matches)} new matches.")
        append_to_csv(new_matches)
        save_state(state)
        
        # Prepare WhatsApp Message
        msg_lines = ["🚨 *New Tenders Found!* 🚨\n"]
        for m in new_matches[:5]:  # limit to top 5 in alert
            msg_lines.append(f"📌 *{m['title']}*\n🔗 {m['url']}\n🏷️ {', '.join(m['keywords'])}\n")
        if len(new_matches) > 5:
            msg_lines.append(f"...and {len(new_matches) - 5} more added to CSV.")
        
        send_whatsapp("\n".join(msg_lines))
    else:
        print("No new tenders found today.")

if __name__ == "__main__":
    main()
  
