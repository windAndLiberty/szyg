from szyg.case_recommendations import knowledge_fallback_keyword, normalized_count, select_diverse_videos


def test_relevance_beats_unrelated_popularity():
    videos = [
        {
            "title": "明星婚礼现场大公开",
            "description": "娱乐资讯",
            "url": "https://example.com/hot",
            "platform": "douyin",
            "author": "娱乐号",
            "likes": 9_000_000,
        },
        {
            "title": "AI英语学习机如何训练孩子口语",
            "description": "英语启蒙、口语陪练与分级学习体验",
            "url": "https://example.com/relevant",
            "platform": "bilibili",
            "author": "教育观察",
            "likes": 120,
        },
    ]

    selected = select_diverse_videos(
        videos,
        keyword="AI英语学习机",
        context="儿童英语启蒙产品，提供AI口语陪练和分级学习",
        limit=1,
    )

    assert selected[0]["url"].endswith("relevant")


def test_selection_prefers_distinct_sources_and_authors_when_relevant():
    videos = [
        {
            "title": f"AI英语学习产品真实体验 {index}",
            "description": "儿童口语陪练与英语启蒙",
            "url": f"https://example.com/{index}",
            "platform": platform,
            "author": author,
            "likes": 100 - index,
        }
        for index, (platform, author) in enumerate(
            [("bilibili", "老师甲"), ("douyin", "家长乙"), ("kuaishou", "测评丙"), ("douyin", "老师甲")]
        )
    ]

    selected = select_diverse_videos(videos, "AI英语学习", "儿童英语口语陪练", limit=3)

    assert len(selected) == 3
    assert len({row["platform"] for row in selected}) == 3
    assert len({row["author"] for row in selected}) == 3


def test_normalized_count_understands_chinese_units():
    assert normalized_count("1.2万") == 12_000


def test_knowledge_filename_is_used_when_keyword_model_is_unavailable():
    assert knowledge_fallback_keyword("[产品资料] AI英语学习机说明书.pdf\n正文") == "AI英语学习机说明书"
