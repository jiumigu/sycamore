"""AI 问答库测试 — 主题/回答 CRUD · 全文检索 · 标签与 AI 过滤 · nested answers · 采纳标记"""
from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.toolkit.models import AskAnswer, AskTopic

TOPICS_URL = '/api/toolkit/ask-topics/'
ANSWERS_URL = '/api/toolkit/ask-answers/'


def _create_topic(question: str = '这份工作还值得继续吗', tags: list | None = None) -> dict:
    payload = {
        'title': '',
        'question': question,
        'background': '考虑年中是否离职',
        'tags': tags or ['工作', '决策'],
    }
    resp = APIClient().post(TOPICS_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


def _add_answer(topic_id: int, ai: str = 'WorkBuddy', session: str = '', verdict: str = '',
                days_ago: int = 0, answer: str = '结合你近三个月的打卡数据来看…') -> dict:
    from django.utils import timezone
    payload = {
        'topic': topic_id,
        'ai': ai,
        'session': session,
        'answer': answer,
        'asked_at': (timezone.now() - timedelta(days=days_ago)).isoformat(),
        'verdict': verdict,
    }
    resp = APIClient().post(ANSWERS_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


@pytest.mark.django_db
def test_topic_create_with_answers_nested() -> None:
    """新建主题（标题空自动回退）+ 挂两条回答 → detail 内嵌 answers"""
    t = _create_topic()
    _add_answer(t['id'], ai='Claude Code', session='6月职业规划深聊', days_ago=1)
    _add_answer(t['id'], ai='DeepSeek', session='断舍离那晚', verdict='采纳', days_ago=3)
    resp = APIClient().get(f"{TOPICS_URL}{t['id']}/")
    assert resp.status_code == 200
    assert len(resp.data['answers']) == 2
    assert resp.data['answer_count'] == 2
    assert resp.data['accepted_count'] == 1
    # 标题为空 → 回退展示问题（前端用 question 截断，后端存空串即可）
    assert resp.data['title'] == ''
    assert AskTopic.objects.get(id=t['id']).question.startswith('这份工作')


@pytest.mark.django_db
def test_search_across_question_answer_session_ai() -> None:
    """全文检索命中 回答正文/会话背景/AI 对象 三处"""
    t = _create_topic(question='如何降低通勤成本')
    _add_answer(t['id'], ai='Kimi', session='早上上班路上问的', answer='建议地铁加共享单车组合')
    c = APIClient()
    # 命中回答正文关键词
    assert c.get(TOPICS_URL, {'search': '共享单车'}).data['count'] == 1
    # 命中会话背景
    assert c.get(TOPICS_URL, {'search': '上班路上'}).data['count'] == 1
    # 命中 AI 对象
    assert c.get(TOPICS_URL, {'search': 'Kimi'}).data['count'] == 1
    # 无命中
    assert c.get(TOPICS_URL, {'search': '不存在的词xyz'}).data['count'] == 0


@pytest.mark.django_db
def test_filter_by_tag_and_ai() -> None:
    """?tag= 命中主题标签数组；?ai= 命中该 AI 回答过的主题"""
    t1 = _create_topic(question='问题A', tags=['学习'])
    t2 = _create_topic(question='问题B', tags=['健康'])
    _add_answer(t1['id'], ai='ChatGPT')
    _add_answer(t2['id'], ai='豆包')
    c = APIClient()
    assert c.get(TOPICS_URL, {'tag': '学习'}).data['count'] == 1
    assert c.get(TOPICS_URL, {'tag': '健康'}).data['count'] == 1
    assert c.get(TOPICS_URL, {'tag': '决策'}).data['count'] == 0
    assert c.get(TOPICS_URL, {'ai': 'ChatGPT'}).data['count'] == 1
    assert c.get(TOPICS_URL, {'ai': '豆包'}).data['count'] == 1


@pytest.mark.django_db
def test_same_ai_different_session_two_answers() -> None:
    """同 AI 不同对话会话 = 两条独立回答（区分上下文）"""
    t = _create_topic()
    a1 = _add_answer(t['id'], ai='DeepSeek', session='对话一')
    a2 = _add_answer(t['id'], ai='DeepSeek', session='对话二')
    assert a1['id'] != a2['id']
    resp = APIClient().get(f"{TOPICS_URL}{t['id']}/")
    assert len(resp.data['answers']) == 2
    assert {x['session'] for x in resp.data['answers']} == {'对话一', '对话二'}


@pytest.mark.django_db
def test_answer_verdict_update_and_filter_by_topic() -> None:
    """回答 verdict 可改；answers 列表支持 ?topic= 过滤"""
    t = _create_topic()
    a = _add_answer(t['id'], ai='WorkBuddy')
    # 行内改为采纳
    resp = APIClient().patch(f"{ANSWERS_URL}{a['id']}/", {'verdict': '采纳'}, format='json')
    assert resp.status_code == 200 and resp.data['verdict'] == '采纳'
    listed = APIClient().get(ANSWERS_URL, {'topic': t['id']}).data
    assert listed['count'] == 1 and listed['results'][0]['verdict'] == '采纳'
    AskAnswer.objects.get(id=a['id']).delete()
    assert AskAnswer.objects.filter(topic_id=t['id']).count() == 0
