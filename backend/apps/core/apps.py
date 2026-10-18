from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'apps.core'

    def ready(self):
        """把注释派生到各模型的 `field.db_comment` / `Meta.db_table_comment` 上。

        **必须挂在这里**，不能改成 import 时执行：`ready()` 是 Django 保证
        「所有 app 的模型都已注册」之后才跑的第一个钩子，这里做一次遍历就能
        覆盖全项目；挂早会漏模型，挂在 import 上则每次导入都可能跑一遍。

        只碰 Python 对象、不连数据库 ⇒ 迁移 / 测试 / WSGI 冷启动都安全；
        幂等 ⇒ 重复调用无副作用。

        ⚠️ 两个函数缺一不可：列注释与表注释走**不同的读取路径**
        （表注释要改 `_meta.original_attrs` 才被 autodetector 看到），
        少调一个就是「改了一半、另一半静默不生效」。

        真源与判据见 `apps/core/db_comments.py` 的模块 docstring。
        """
        from apps.core.db_comments import apply_column_comments, apply_table_comments

        apply_column_comments()
        apply_table_comments()
