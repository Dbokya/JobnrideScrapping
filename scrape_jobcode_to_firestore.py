import requests
import json
import time

base_url = "https://jobcode.in/wp-json/wp/v2/posts"
all_jobs = []
page = 1

while True:
    print(f"Fetching page {page} from API...")
    url = f"{base_url}?per_page=100&page={page}"

    response = requests.get(url)

    if response.status_code != 200:
        print("No more pages.")
        break

    posts = response.json()

    if not posts:
        break

    for post in posts:
        job = {
            "id": post["id"],
            "title": post["title"]["rendered"],
            "slug": post["slug"],
            "link": post["link"],
            "date": post["date"],
            "content": post["content"]["rendered"],
            "excerpt": post["excerpt"]["rendered"],
            "author_id": post["author"],
            "categories": post["categories"],
            "tags": post["tags"]
        }

        all_jobs.append(job)

    page += 1
    time.sleep(1)

# Save to JSON
with open("jobcode_all_jobs.json", "w", encoding="utf-8") as f:
    json.dump(all_jobs, f, indent=4, ensure_ascii=False)

print("✅ Done. Total jobs fetched:", len(all_jobs))
