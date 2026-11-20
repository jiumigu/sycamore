from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('relation', '0008_db_comments'),
    ]

    operations = [
        migrations.AddField(
            model_name='readermonthlysummary',
            name='published_count',
            field=models.IntegerField(
                blank=True, db_comment='本月发文篇数', null=True, verbose_name='本月发文篇数',
            ),
        ),
        migrations.AddField(
            model_name='readermonthlysummary',
            name='top_article_views',
            field=models.IntegerField(
                blank=True, db_comment='最佳文章阅读数', null=True, verbose_name='最佳文章阅读数',
            ),
        ),
    ]
