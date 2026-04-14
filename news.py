import os
import re
import requests
import feedparser
from datetime import datetime

# ─────────────────────────────────────────
# 뉴스를 가져올 RSS 피드 목록
# RSS란 웹사이트가 새 글을 자동으로 제공하는 구독 형식이에요.
# 주소를 추가하면 더 많은 매체에서 뉴스를 가져올 수 있어요.
# ─────────────────────────────────────────
RSS_FEEDS = [
    "https://feeds.feedburner.com/venturebeat/SZYF",           # VentureBeat AI
    "https://techcrunch.com/category/artificial-intelligence/feed/",  # TechCrunch AI
    "https://www.technologyreview.com/feed/",                   # MIT Technology Review
]

# ─────────────────────────────────────────
# 환경변수에서 비밀 키 불러오기
# 코드에 직접 쓰면 GitHub에 노출되니까 Secret으로 관리해요.
# ─────────────────────────────────────────
TEAMS_WEBHOOK = os.environ.get("TEAMS_WEBHOOK")         # Teams 채널 Webhook URL
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") # Claude API 키


def clean_html(text):
    """
    HTML 태그 제거 함수
    RSS 피드에는 <p>, <b> 같은 HTML 태그가 섞여 있어요.
    정규식으로 꺽쇠 괄호 안의 내용을 전부 제거해요.
    """
    return re.sub(r'<[^>]+>', '', text or '').strip()


def get_news(limit=10):
    """
    RSS 피드에서 뉴스 가져오기
    각 피드를 순회하면서 기사 제목, 링크, 요약, 출처를 수집해요.
    limit 개수만큼만 잘라서 반환해요.
    """
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)  # RSS 피드 파싱
        for entry in feed.entries:
            articles.append({
                "title": clean_html(entry.title),                        # 기사 제목
                "link": entry.link,                                       # 기사 링크
                "summary": clean_html(entry.get("summary", ""))[:300],   # 요약 (300자 제한)
                "source": feed.feed.title                                 # 출처 매체명
            })
    return articles[:limit]  # 상위 N개만 반환


def translate_and_summarize(articles):
    """
    Claude API로 기사 번역 및 요약
    수집한 기사들을 Claude에게 보내서 한국어로 번역 + 요약해달라고 요청해요.
    """
    # 기사 목록을 텍스트로 변환해서 Claude에게 전달할 프롬프트 만들기
    text = "\n".join([
        f"{i+1}. 제목: {a['title']}\n내용: {a['summary']}"
        for i, a in enumerate(articles)
    ])

    # Claude API 호출
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

    # 응답에서 텍스트만 추출해서 반환
    return response.json()["content"][0]["text"]


def send_to_teams(summaries):
    """
    Teams 채널로 메시지 전송
    Webhook URL로 Adaptive Card 형식의 메시지를 POST 요청으로 보내요.
    Adaptive Card는 Teams에서 예쁘게 렌더링되는 카드 형식이에요.
    """
    today = datetime.now().strftime("%Y년 %m월 %d일")  # 오늘 날짜 포맷팅

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
                        # 상단 제목 텍스트
                        "type": "TextBlock",
                        "text": f"🤖 AI 뉴스 브리핑 — {today}",
                        "size": "Medium",
                        "weight": "Bolder"
                    },
                    {
                        # Claude가 요약한 내용을 그대로 표시
                        "type": "TextBlock",
                        "text": summaries,
                        "wrap": True,      # 긴 텍스트 자동 줄바꿈
                        "separator": True  # 제목과 구분선 추가
                    }
                ]
            }
        }]
    }

    # Teams Webhook으로 POST 요청 전송
    requests.post(TEAMS_WEBHOOK, json=payload)


# ─────────────────────────────────────────
# 메인 실행 흐름
# ─────────────────────────────────────────
articles = get_news(10)                        # 1. 뉴스 10건 수집
summaries = translate_and_summarize(articles)  # 2. Claude로 번역 및 요약
send_to_teams(summaries)                       # 3. Teams로 전송
