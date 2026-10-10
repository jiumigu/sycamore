"""AI 问答库测试 — 主题/回答 CRUD · 全文检索 · 标签与 AI 过滤 · nested answers · 采纳标记 · 场景容器 · 追问链"""
from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.toolkit.models import AskAnswer, AskScene, AskTopic
from apps.toolkit.views import CONCLUSION_EXCERPT_LEN as VIEW_EXCERPT_LEN

TOPICS_URL = '/api/toolkit/ask-topics/'
ANSWERS_URL = '/api/toolkit/ask-answers/'
SCENES_URL = '/api/toolkit/ask-scenes/'


def _create_scene(name: str = '备考·网络', description: str = '') -> dict:
    resp = APIClient().post(SCENES_URL, {'name': name, 'description': description}, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


def _create_topic(question: str = '这份工作还值得继续吗', tags: list | None = None, scene: int | None = None) -> dict:
    payload = {
        'title': '',
        'question': question,
        'background': '考虑年中是否离职',
        'tags': tags or ['工作', '决策'],
    }
    if scene is not None:
        payload['scene'] = scene
    resp = APIClient().post(TOPICS_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


def _add_answer(topic_id: int, ai: str = 'WorkBuddy', session: str = '', verdict: str = '',
                days_ago: int = 0, answer: str = '结合你近三个月的打卡数据来看…',
                question: str = '', parent: int | None = None) -> dict:
    from django.utils import timezone
    payload = {
        'topic': topic_id,
        'ai': ai,
        'session': session,
        'answer': answer,
        'asked_at': (timezone.now() - timedelta(days=days_ago)).isoformat(),
        'verdict': verdict,
    }
    if question:
        payload['question'] = question
    if parent is not None:
        payload['parent'] = parent
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


# ─────────── 业务场景容器 ───────────

@pytest.mark.django_db
def test_scene_crud_and_topic_scene_filter() -> None:
    """场景 CRUD；主题挂场景；?scene= 按场景过滤、?scene=none 筛未分类"""
    scene = _create_scene(name='备考·网络')
    other = _create_scene(name='工作')
    t1 = _create_topic(question='CIDR 怎么划', scene=scene['id'])
    _create_topic(question='无场景主题')
    c = APIClient()
    # 场景列表 topic_count 注解
    listed = c.get(SCENES_URL).data['results']
    by_name = {s['name']: s['topic_count'] for s in listed}
    assert by_name == {'备考·网络': 1, '工作': 0}
    # 主题带 scene / scene_name 回显
    detail = c.get(f"{TOPICS_URL}{t1['id']}/").data
    assert detail['scene'] == scene['id'] and detail['scene_name'] == '备考·网络'
    # 过滤
    assert c.get(TOPICS_URL, {'scene': scene['id']}).data['count'] == 1
    assert c.get(TOPICS_URL, {'scene': other['id']}).data['count'] == 0
    assert c.get(TOPICS_URL, {'scene': 'none'}).data['count'] == 1
    # 删除场景 → 主题 scene 置空（SET_NULL）
    c.delete(f"{SCENES_URL}{scene['id']}/")
    assert AskTopic.objects.get(id=t1['id']).scene_id is None
    assert c.get(TOPICS_URL, {'scene': 'none'}).data['count'] == 2


# ─────────── 多轮追问链 ───────────

@pytest.mark.django_db
def test_followup_chain_create_nested_and_delete_cascade() -> None:
    """首轮回答 → 带 question/parent 的追问；detail 返回 parent/question；删除父回答级联删追问"""
    t = _create_topic(question='如何准备面试')
    root = _add_answer(t['id'], ai='WorkBuddy', answer='先看岗位 JD 拆能力点')
    followup = _add_answer(t['id'], ai='WorkBuddy', parent=root['id'],
                           question='追问：如果时间只有三天呢？', answer='那就主攻高频题 + 模拟面')
    deep = _add_answer(t['id'], ai='WorkBuddy', parent=followup['id'],
                       question='再追问：模拟面找谁？', answer='找朋友扮演面试官')
    detail = APIClient().get(f"{TOPICS_URL}{t['id']}/").data
    by_id = {a['id']: a for a in detail['answers']}
    assert by_id[root['id']]['parent'] is None and by_id[root['id']]['question'] == ''
    assert by_id[followup['id']]['parent'] == root['id']
    assert by_id[followup['id']]['question'].startswith('追问')
    assert by_id[deep['id']]['parent'] == followup['id']
    # 检索命中追问文本
    c = APIClient()
    assert c.get(TOPICS_URL, {'search': '三天'}).data['count'] == 1
    assert c.get(TOPICS_URL, {'search': '模拟面'}).data['count'] == 1
    # 删除中间父回答 → 其下追问级联删除，兄弟链不受影响
    AskAnswer.objects.get(id=followup['id']).delete()
    assert AskAnswer.objects.filter(id=deep['id']).count() == 0
    assert AskAnswer.objects.filter(id=root['id']).count() == 1


@pytest.mark.django_db
def test_scene_delete_leaves_topic_but_followups_deleted_with_topic() -> None:
    """删场景主题仍在（场景 SET_NULL）；删主题整链级联（含追问）"""
    scene = _create_scene(name='生活')
    t = _create_topic(question='旅行带什么', scene=scene['id'])
    root = _add_answer(t['id'], ai='DeepSeek')
    child = _add_answer(t['id'], ai='DeepSeek', parent=root['id'], question='充电宝多大')
    assert AskAnswer.objects.filter(topic_id=t['id']).count() == 2
    APIClient().delete(f"{TOPICS_URL}{t['id']}/")
    assert AskTopic.objects.filter(id=t['id']).count() == 0
    assert AskAnswer.objects.filter(id=child['id']).count() == 0
    assert AskScene.objects.filter(id=scene['id']).count() == 1  # 场景本身保留


# ─────────── 采纳回顾（只看采纳 + 结论汇总）───────────

@pytest.mark.django_db
def test_has_accepted_filter() -> None:
    """?has_accepted=1 只返回含 ✅采纳 回答的主题，可与场景过滤叠加"""
    sc = _create_scene(name='备考·网络')
    t1 = _create_topic(question='CIDR 是什么', scene=sc['id'])
    t2 = _create_topic(question='无采纳的问题', scene=sc['id'])
    _add_answer(t1['id'], ai='WorkBuddy', answer='采纳版', verdict='采纳')
    _add_answer(t1['id'], ai='DeepSeek', answer='备用版', verdict='备用')
    _add_answer(t2['id'], ai='WorkBuddy', answer='未标记版')
    c = APIClient()
    assert c.get(TOPICS_URL, {'has_accepted': '1'}).data['count'] == 1
    assert c.get(TOPICS_URL, {'has_accepted': '1', 'scene': sc['id']}).data['count'] == 1
    assert c.get(TOPICS_URL, {'has_accepted': '0'}).data['count'] == 2  # 非 1 值不生效
    assert c.get(TOPICS_URL).data['count'] == 2


@pytest.mark.django_db
def test_accepted_summary_aggregation() -> None:
    """summary 汇总某场景全部 ✅采纳 回答（含追问采纳），不含备用/未标记；场景过滤生效"""
    sc = _create_scene(name='备考·网络')
    other = _create_scene(name='写作')
    t1 = _create_topic(question='CIDR 怎么划', scene=sc['id'])
    root = _add_answer(t1['id'], ai='WorkBuddy', answer='用前缀长度表达', verdict='采纳')
    _add_answer(t1['id'], ai='DeepSeek', answer='另一家说法', verdict='备用')
    # 追问节点被采纳 → question 带入上下文
    _add_answer(t1['id'], ai='WorkBuddy', parent=root['id'], question='/26 几台主机？',
                answer='62 台', verdict='采纳')
    t_other = _create_topic(question='写作开题', scene=other['id'])
    _add_answer(t_other['id'], ai='ChatGPT', answer='先列提纲', verdict='采纳')
    c = APIClient()
    s1 = c.get(f"{TOPICS_URL}summary/?scene={sc['id']}").data['topics']
    assert len(s1) == 1
    assert s1[0]['scene_name'] == '备考·网络'
    assert [a['answer'] for a in s1[0]['accepted']] == ['用前缀长度表达', '62 台']  # 按时间升序且不含备用
    assert s1[0]['accepted'][1]['question'] == '/26 几台主机？'
    assert s1[0]['accepted'][0]['question'] == ''  # 首轮无 question
    all_t = c.get(f"{TOPICS_URL}summary/").data['topics']
    assert len(all_t) == 2
    none_t = c.get(f"{TOPICS_URL}summary/?scene=none").data['topics']
    assert none_t == []


# ─── v3.60.11：「回顾」视图与「一条旧结论」────────────────────────────


@pytest.mark.django_db
def test_review_groups_by_scene_and_marks_uncategorized() -> None:
    """review：按场景分组；无场景的主题归入「未分类」组，不会被静默丢掉"""
    sc = _create_scene(name='人生规划')
    t1 = _create_topic(question='我的人生规划', scene=sc['id'])
    _add_answer(t1['id'], verdict='采纳', days_ago=7)
    t2 = _create_topic(question='没有场景的问题')
    _add_answer(t2['id'], days_ago=3)
    data = APIClient().get(f'{TOPICS_URL}review/').data
    names = [g['scene_name'] for g in data['groups']]
    assert '人生规划' in names and '未分类' in names
    grp = next(g for g in data['groups'] if g['scene_name'] == '未分类')
    assert grp['scene_id'] is None
    assert [t['id'] for t in grp['topics']] == [t2['id']]
    assert grp['topics'][0]['answer_count'] == 1


@pytest.mark.django_db
def test_review_keeps_topics_without_answers() -> None:
    """一条结论都还没标的主题**照样出现**

    回顾页的作用是「点进去就有东西可标」；静默过滤掉无结论的主题，
    会让人以为数据丢了 —— 而「还没标」恰恰是回顾页最该处理的一批。
    """
    t = _create_topic(question='还没标过的主题')
    flat = [x for g in APIClient().get(f'{TOPICS_URL}review/').data['groups'] for x in g['topics']]
    assert [x['id'] for x in flat] == [t['id']]
    assert flat[0]['concluded_count'] == 0
    assert flat[0]['answer_count'] == 0


@pytest.mark.django_db
def test_review_orders_stale_topic_first() -> None:
    """冷落优先：最久没动的主题排最前（`updated_at` 是「最该回顾」的可算代理）"""
    from django.utils import timezone
    stale = _create_topic(question='很久没碰的')
    _create_topic(question='刚创建的')
    AskTopic.objects.filter(id=stale['id']).update(updated_at=timezone.now() - timedelta(days=30))
    flat = [x for g in APIClient().get(f'{TOPICS_URL}review/').data['groups'] for x in g['topics']]
    assert flat[0]['id'] == stale['id']
    assert flat[0]['days_idle'] >= 29


@pytest.mark.django_db
def test_review_stats_splits_marked_and_unmarked() -> None:
    """stats：marked = 采纳 或 写了备注；marked + unmarked 必须等于回答总数"""
    t = _create_topic()
    _add_answer(t['id'], verdict='采纳')
    _add_answer(t['id'], ai='DeepSeek')
    _add_answer(t['id'], ai='ChatGPT')
    noted = _add_answer(t['id'], ai='Gemini')
    APIClient().patch(f"{ANSWERS_URL}{noted['id']}/", {'note': '不够清晰'}, format='json')
    s = APIClient().get(f'{TOPICS_URL}review/').data['stats']
    assert s['topics'] == 1
    assert s['answers'] == 4
    assert s['marked'] == 2  # 1 条采纳 + 1 条有备注
    assert s['unmarked'] == 2
    assert s['marked'] + s['unmarked'] == s['answers']


@pytest.mark.django_db
def test_next_conclusion_returns_null_when_no_conclusion() -> None:
    """只有「原料」（全是未标记回答）时返回 200 + null，而不是 204

    前端要能区分「确实还没有结论」与「请求失败」：前者给引导文案，后者才报错。
    """
    t = _create_topic()
    _add_answer(t['id'], ai='DeepSeek')
    resp = APIClient().get(f'{TOPICS_URL}next-conclusion/')
    assert resp.status_code == 200
    assert resp.data is None


@pytest.mark.django_db
def test_next_conclusion_prefers_note_and_marks_source() -> None:
    """有备注 → conclusion 用备注、来源标 'note'（卡片要能说清这句是你写的还是 AI 的）

    ⚠️ 本接口内部是 `random.choice(候选)` ⇒ **用例必须让候选唯一**（此处只建 1 条有结论的回答），
    否则断言会间歇性失败 —— 这类 flaky 比报错更难查。
    """
    t = _create_topic()
    a = _add_answer(t['id'], ai='WorkBuddy', answer='AI 的一大段回答……')
    APIClient().patch(f"{ANSWERS_URL}{a['id']}/", {'note': '这条才是我的结论'}, format='json')
    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['id'] == a['id']
    assert got['conclusion'] == '这条才是我的结论'
    assert got['conclusion_source'] == 'note'
    assert got['days_ago'] == 0


@pytest.mark.django_db
def test_next_conclusion_falls_back_to_answer_snippet() -> None:
    """只有采纳、没写备注 → 退回用回答片段，来源标 'answer'（不能给出空结论）"""
    t = _create_topic()
    a = _add_answer(t['id'], ai='DeepSeek', verdict='采纳', answer='先离职，再重建结构')
    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['id'] == a['id']
    assert got['conclusion'] == '先离职，再重建结构'
    assert got['conclusion_source'] == 'answer'
    assert got['verdict'] == '采纳'


# ─── v3.60.13：卡片的信息密度与出口（「信息不够多，也点不开」）───────────
#
# 起因：卡片原先只渲染「问题 + 结论」两个字段，而 `note` 型的结论可能只有几个字
# （库里那条 4 个字：「不够清晰」）⇒ **判断的依据**一个字都不在卡上，
# 「15 天前」读起来像一句没头没尾的批注。


@pytest.mark.django_db
def test_next_conclusion_carries_context_and_excerpt() -> None:
    """出处（场景 / 主题）、AI 回答摘要、池子条数都要下发

    `scene_name` / `topic_title` 其实**早就在返回体里**，只是卡片从未渲染 ——
    实测 11/11 主题都有标题与场景，等于白扔（同硬坑⑬：能存不能看，先查渲染端）。
    """
    sc = _create_scene(name='人生规划')
    t = _create_topic(question='如果我想以自己的方式过一生，你觉得会是哪种方式', scene=sc['id'])
    a = _add_answer(t['id'], ai='DeepSeek', answer='A' * 300)
    APIClient().patch(f"{ANSWERS_URL}{a['id']}/", {'note': '不够清晰'}, format='json')

    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['conclusion'] == '不够清晰'
    assert got['conclusion_source'] == 'note'
    # 出处（此前前端根本没读这两个键）
    assert got['scene_name'] == '人生规划'
    assert got['topic_title'] == '如果我想以自己的方式过一生，你觉得会是哪种方式'
    # 判断依据：note 型下结论只有 4 个字，没有这段就读不出当时在判断什么
    assert got['ai_excerpt'] == 'A' * VIEW_EXCERPT_LEN
    assert got['answer_len'] == 300
    assert got['ai_excerpt_truncated'] is True
    assert got['pool_size'] == 1


@pytest.mark.django_db
def test_next_conclusion_truncation_flag_is_decided_by_backend() -> None:
    """截断与否由**后端**判（前端不按长度推算），两侧 + 边界都要钉

    实测库里池中回答原文 1045 ~ 2696 字，而卡上只放得下 120 字。
    界面上不标出来，1871 字的回答会被读成「AI 就说了这么一点」。
    """
    t = _create_topic()
    a = _add_answer(t['id'], ai='Claude', verdict='采纳', answer='短回答')

    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['ai_excerpt'] == '短回答'
    assert got['ai_excerpt_truncated'] is False
    assert got['answer_len'] == 3

    # 边界：**恰好等于**上限不算截断（多一个字才算）
    AskAnswer.objects.filter(id=a['id']).update(answer='B' * VIEW_EXCERPT_LEN)
    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['ai_excerpt_truncated'] is False
    assert got['answer_len'] == VIEW_EXCERPT_LEN

    AskAnswer.objects.filter(id=a['id']).update(answer='B' * (VIEW_EXCERPT_LEN + 1))
    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['ai_excerpt_truncated'] is True
    assert len(got['ai_excerpt']) == VIEW_EXCERPT_LEN


@pytest.mark.django_db
def test_next_conclusion_pool_size_counts_only_conclusions() -> None:
    """`pool_size` 只数「有结论」的 —— 未标记的是原料、标了「备用」的也只是标记

    「🔄 换一条」转两下就回原处时，界面上要能说出为什么。
    """
    t = _create_topic()
    _add_answer(t['id'], ai='A')                                     # 原料：不算
    _add_answer(t['id'], ai='B', verdict='备用')                      # 有标记无备注：不算「结论」
    _add_answer(t['id'], ai='C', verdict='采纳')                      # 算
    noted = _add_answer(t['id'], ai='D', answer='D 的一段回答')
    APIClient().patch(f"{ANSWERS_URL}{noted['id']}/", {'note': '我的结论'}, format='json')  # 算

    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['pool_size'] == 2


@pytest.mark.django_db
def test_next_conclusion_answer_type_excerpt_equals_conclusion() -> None:
    """`answer` 型下 `ai_excerpt` 与 `conclusion` **是同一段文字**

    钉住这个事实：前端只该渲染一块，否则同一段话会被画两遍、读成「AI 说了两个版本」。
    将来若想让「依据」与「结论」真正分开，要改的是设计 —— 这条用例会先红着提醒。
    """
    t = _create_topic()
    _add_answer(t['id'], ai='DeepSeek', verdict='采纳', answer='X' * 400)

    got = APIClient().get(f'{TOPICS_URL}next-conclusion/').data
    assert got['conclusion_source'] == 'answer'
    assert got['conclusion'] == got['ai_excerpt'] == 'X' * VIEW_EXCERPT_LEN
