"""跨 app 共用的序列化字段。

这里放的是**口径类**字段：同一个字段名，入参和出参要的不是同一种类型，
而 DRF 的现成字段只能满足一边。放公共位置是为了避免每个 app 抄一份
（抄第二份就是**第三处实现**，口径迟早分叉）。
"""

from rest_framework import serializers


class AmountNumberField(serializers.FloatField):
    """金额字段：**出参 number、入参 Decimal**。

    两个方向要的不是同一种类型，所以不能只挑一个现成字段：

    - 出参必须是 number —— 前端 `formatAmount` 第一句就是
      `typeof value !== 'number' → 返回空占位`，字符串会让**有值**渲染成 `¥—`；
      前端 TS 类型也写的是 `number`，字符串过得了类型检查（运行时才炸）。
    - 入参必须是 Decimal —— `RewardPool.balance` 是 DecimalField，
      `Decimal += float` 会抛 `TypeError`，而 `perform_create` 里
      `serializer.save()` 已提交、`add_reward()` 随后才炸 ⇒ 写一半（v3.63.15）。

    ⚠️ 不要用 `DecimalField(coerce_to_string=False)` 替代：它的 `response.data`
    里是 Decimal（虽经 JSONRenderer 仍是 number），而既有测试断言的是
    `isinstance(value, float)` —— 会红。只覆写反序列化方向、出参照旧走
    `FloatField`，两个方向各自正确。

    ⚠️ 也不要直接不声明让 `ModelSerializer` 自动生成：它给 DecimalField 生成的
    是 `coerce_to_string=True`，接口吐 `"800.00"`（v3.63.16 礼物价格全空白的原因）。
    """

    def __init__(self, **kwargs):
        # FloatField 不认这两个参数，先摘下来给内部的 DecimalField 用
        self.max_digits = kwargs.pop('max_digits', 12)
        self.decimal_places = kwargs.pop('decimal_places', 2)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        return serializers.DecimalField(
            max_digits=self.max_digits,
            decimal_places=self.decimal_places,
        ).to_internal_value(data)
