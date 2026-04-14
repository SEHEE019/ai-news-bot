import requests
import feedparser
from datetime import datetime

# 뉴스 수집 (무료 RSS)
RSS_FEEDS = [
    "https://feeds.feedburner.com/venturebeat/SZYF",  # VentureBeat AI
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.technologyreview.com/feed/",
]

TEAMS_WEBHOOK = "https://defaultf9619945fe764aaaac97c8ae5d21f1.1b.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/5706e373f72147afab217aa81adced2d/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=liCIkLkEsnOgJ-e2YM48eIL7mXRy3ntOBQefMblUGSs"

def get_news(limit=10):
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", "")[:150],
                "source": feed.feed.title
            })
    return articles[:limit]

def send_to_teams(articles):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    # Workflows는 Adaptive Card 형식 사용
    body_text = "\n\n".join([
        f"**{i+1}. [{a['title']}]({a['link']})**\n{a['source']} — {a['summary']}..."
        for i, a in enumerate(articles)
    ])
    
    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.2",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": f"🤖 AI 뉴스 브리핑 — {today}",
                        "size": "Medium",
                        "weight": "Bolder"
                    },
                    {
                        "type": "TextBlock",
                        "text": body_text,
                        "wrap": True
                    }
                ]
            }
        }]
    }
    
    requests.post(TEAMS_WEBHOOK, json=payload)

articles = get_news(10)
send_to_teams(articles)
