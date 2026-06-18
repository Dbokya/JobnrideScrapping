"""
Cleanup expired "match_connect" chats.

The JobNRide app tags ride-match Connect chats with:
    kind:      'match_connect'
    expiresAt: <Timestamp>  (creation time + 30 hours)

The app already HIDES these chats from the user once expired, but the docs and
their `messages` subcollection still live in Firestore. This script permanently
deletes them so storage is reclaimed and the data is truly gone.

For each expired chat it removes:
  - chats/{chatId}/messages/*      (subcollection, batched)
  - chats/{chatId}/typing/*        (subcollection, if present)
  - users/{uid}/user_chats/{chatId} pointers for every participant
  - chats/{chatId}                 (the chat document itself)

Run locally:   python cleanup_match_chats.py
Run in CI:     scheduled GitHub Action (.github/workflows/cleanup_match_chats.yml)
"""

import datetime
import firebase_admin
from firebase_admin import credentials, firestore

SERVICE_ACCOUNT = "serviceaccount/jobnride-97d77-firebase-adminsdk-fbsvc-20ce6e6129.json"
BATCH_SIZE = 400  # < Firestore's 500-op batch limit

if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT)
    firebase_admin.initialize_app(cred)

db = firestore.client()


def delete_subcollection(chat_ref, name):
    """Delete every doc in chats/{id}/{name} in batches. Returns count."""
    deleted = 0
    while True:
        docs = list(chat_ref.collection(name).limit(BATCH_SIZE).stream())
        if not docs:
            break
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        deleted += len(docs)
        if len(docs) < BATCH_SIZE:
            break
    return deleted


def cleanup():
    now = datetime.datetime.now(datetime.timezone.utc)
    print(f"[cleanup] Scanning expired match_connect chats at {now.isoformat()}")

    query = (
        db.collection("chats")
        .where("kind", "==", "match_connect")
        .where("expiresAt", "<=", now)
    )

    chats = list(query.stream())
    if not chats:
        print("[cleanup] Nothing to delete.")
        return

    total_chats = 0
    total_msgs = 0
    for chat in chats:
        chat_ref = chat.reference
        data = chat.to_dict() or {}
        chat_id = chat.id

        # 1) subcollections
        msgs = delete_subcollection(chat_ref, "messages")
        delete_subcollection(chat_ref, "typing")

        # 2) per-user pointers
        users = data.get("users")
        if isinstance(users, list):
            uids = [str(u) for u in users if u]
        elif isinstance(users, str):
            uids = [u for u in users.split(",") if u]
        else:
            uids = []
        for uid in uids:
            try:
                db.collection("users").document(uid).collection(
                    "user_chats"
                ).document(chat_id).delete()
            except Exception as e:
                print(f"[cleanup]   warn: user_chats {uid}/{chat_id} -> {e}")

        # 3) the chat doc
        chat_ref.delete()

        total_chats += 1
        total_msgs += msgs
        print(f"[cleanup] Deleted chat {chat_id} ({msgs} messages)")

    print(f"[cleanup] Done. Removed {total_chats} chats, {total_msgs} messages.")


if __name__ == "__main__":
    cleanup()
