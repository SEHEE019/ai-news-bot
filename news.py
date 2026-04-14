import os
import re
import requests
import feedparser
from datetime import datetime

# ─────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────

# Hacker News에서 AI 관련 상위 기사만 가져오는 RSS
# points=50 이상인 것만 → 커뮤니티에서 어느 정도 검증된 글만 가져와요
RSS_FEEDS = [
    "https://hnrss.org/newest?q=AI+OR+LLM+OR+ChatGPT+OR+Claude+OR+Gemini+OR+OpenAI+OR+Anthropic&points=50",
]

TEAMS_WEBHOOK = os.environ.get("TEAMS_WEBHOOK")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

TOP_N = 5  # 최종적으로 Teams에 보낼 기사 수


def clean_html(text):
    """HTML 태그 제거"""
    return re.sub(r'<[^>]+>', '', text or '').strip()


def get_news(fetch_count=20):
    """
    RSS 피드에서 뉴스 가져오기
    Claude가 Top 5를 고를 수 있도록 넉넉하게 20개 수집해요.
    Hacker News는 포인트(추천수) 기반이라 이미 커뮤니티 필터가 된 상태예요.
    """
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            articles.append({
                "title": clean_html(entry.title),
                "link": entry.link,
                "summary": clean_html(entry.get("summary", ""))[:300],
            })
    return articles[:fetch_count]


def pick_and_summarize(articles, top_n=TOP_N):
    """
    Claude API로 Top N 선정 + 한국어 번역 및 요약
    단순히 번역만 하는 게 아니라 중요도 기준으로 추려달라고 요청해요.
    """
    text = "\n".join([
        f"{i+1}. 제목: {a['title']}\n링크: {a['link']}\n내용: {a['summary']}"
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
                "content": f"""아래는 오늘의 AI 관련 뉴스 목록이야.
이 중에서 AI 업계 종사자에게 가장 중요하고 임팩트 있는 기사 {top_n}개를 골라서
한국어로 번역하고 각각 2~3문장으로 요약해줘.

출력 형식 (반드시 지켜줘):
1. [한국어 제목](링크) - 요약 내용
2. [한국어 제목](링크) - 요약 내용
...

다른 말 없이 번호와 내용만 출력해.

{text}"""
            }]
        }
    )

    return response.json()["content"][0]["text"]


def send_to_teams(summaries):
    """
    Teams 채널로 메시지 전송
    Adaptive Card 형식으로 보내요.
    """
    today = datetime.now().strftime("%Y년 %m월 %d일")

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
                        "text": f"🤖 AI 뉴스 Top {TOP_N} — {today}",
                        "size": "Medium",
                        "weight": "Bolder"
                    },
                    {
                        "type": "TextBlock",
                        "text": summaries,
                        "wrap": True,
                        "separator": True
                    }
                ]
            }
        }]
    }

    requests.post(TEAMS_WEBHOOK, json=payload)


# ─────────────────────────────────────────
# 메인 실행 흐름
# ─────────────────────────────────────────
articles = get_news(fetch_count=20)        # 1. 후보 20개 수집
summaries = pick_and_summarize(articles)   # 2. Claude가 Top 5 선정 + 번역 요약
send_to_teams(summaries)                   # 3. Teams로 전송
