import os
import re
import requests
import feedparser
from datetime import datetime

RSS_FEEDS = [
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.technologyreview.com/feed/",
]

TEAMS_WEBHOOK = os.environ.get("TEAMS_WEBHOOK")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

def clean_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()

def get_news(limit=10):
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            articles.append({
                "title": clean_html(entry.title),
                "link": entry.link,
                "summary": clean_html(entry.get("summary", ""))[:300],
                "source": feed.feed.title
            })
    return articles[:limit]

def translate_and_summarize(articles):
    text = "\n".join([
        f"{i+1}. 제목: {a['title']}\n내용: {a['summary']}"
        for i, a in enumerate(articles)
    ])
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [{
                "role": "user",
                "content": f"""아래 AI 뉴스 기사들을 한국어로 번역하고 각각 2~3문장으로 요약해줘.
출력 형식: 번호. [한국어 제목] - 요약 내용
다른 말 없이 번호와 내용만 출력해.

{text}"""
            }]
        }
    )
    return response.json()["content"][0]["text"]

def send_to_teams(articles, summaries):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    lines = summaries.strip().split("\n")
    
    facts = []
    for i, article in enumerate(articles):
        summary_line = lines[i] if i < len(lines) else ""
        summary_line = re.sub(r'^\d+\.\s*', '', summary_line)
        facts.append({
            "title": f"{i+1}. {article['title']}",
            "value": f"[{article['source']}]({article['link']})\n{summary_line}"
        })
    
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
                    }
                ] + [
                    {
                        "type": "TextBlock",
                        "text": f"**{i+1}. [{a['title']}]({a['link']})**\n{lines[i] if i < len(lines) else ''}",
                        "wrap": True,
                        "separator": True
                    }
                    for i, a in enumerate(articles)
                ]
            }
        }]
    }
    requests.post(TEAMS_WEBHOOK, json=payload)

articles = get_news(10)
summaries = translate_and_summarize(articles)
send_to_teams(articles, summaries)
