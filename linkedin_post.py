"""
LinkedIn REST poster (UGC Post)

Usage:
  - Set env `LINKEDIN_ACCESS_TOKEN` (user or organization access token)
  - Set env `LINKEDIN_AUTHOR_URN` (e.g., "urn:li:person:XXXX" or "urn:li:organization:YYYY")
  - Run: `python linkedin_post.py --title "Job Title" --company "Acme" --apply "https://..." --description "Short description..."`

This posts a simple text post. For images/media, extend to use media upload endpoints.
"""
import os
import requests
import argparse
import json

API_URL = "https://api.linkedin.com/v2/ugcPosts"

def build_post_payload(author_urn, text):
    return {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }

def post_text(text):
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    author = os.getenv("LINKEDIN_AUTHOR_URN")
    if not token or not author:
        raise ValueError("Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN env vars")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }

    payload = build_post_payload(author, text)
    resp = requests.post(API_URL, headers=headers, data=json.dumps(payload))
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"LinkedIn API error: {resp.status_code} {resp.text}")
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--apply", required=True)
    parser.add_argument("--description", default="")
    args = parser.parse_args()

    text = f"{args.title} at {args.company}\n\n{args.description}\n\nApply: {args.apply}"
    print("Posting to LinkedIn (REST)...")
    resp = post_text(text)
    print("Posted:", resp)


if __name__ == '__main__':
    main()
