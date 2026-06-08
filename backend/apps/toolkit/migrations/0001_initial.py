from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS `toolkit_definition` (
                  `id` int NOT NULL AUTO_INCREMENT,
                  `tool_key` varchar(100) NOT NULL COMMENT '工具标识',
                  `name` varchar(100) NOT NULL COMMENT '工具名称',
                  `description` text COMMENT '工具描述',
                  `icon` varchar(50) DEFAULT '🔧' COMMENT '图标',
                  `category` varchar(50) DEFAULT 'other' COMMENT '分类',
                  `input_schema` json NOT NULL COMMENT '输入参数定义',
                  `output_type` varchar(50) DEFAULT 'file' COMMENT '输出类型',
                  `is_async` tinyint DEFAULT 1 COMMENT '是否异步',
                  `timeout_seconds` int DEFAULT 300 COMMENT '超时时间',
                  `is_enabled` tinyint DEFAULT 1 COMMENT '是否启用',
                  `user_id` int NOT NULL COMMENT '用户ID',
                  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (`id`),
                  UNIQUE KEY `uk_tool_key` (`tool_key`),
                  KEY `idx_category` (`category`),
                  KEY `idx_is_enabled` (`is_enabled`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具定义表';

                CREATE TABLE IF NOT EXISTS `toolkit_execution` (
                  `id` bigint NOT NULL AUTO_INCREMENT,
                  `tool_id` int NOT NULL COMMENT '工具ID',
                  `task_id` varchar(100) DEFAULT NULL COMMENT '任务ID',
                  `input_params` json NOT NULL COMMENT '输入参数',
                  `output_result` text COMMENT '输出结果',
                  `output_file` varchar(500) DEFAULT NULL COMMENT '输出文件路径',
                  `status` varchar(20) DEFAULT 'pending' COMMENT '状态',
                  `progress` int DEFAULT 0 COMMENT '进度百分比',
                  `error_message` text COMMENT '错误信息',
                  `execution_time_ms` int DEFAULT NULL COMMENT '执行耗时',
                  `user_id` int NOT NULL COMMENT '用户ID',
                  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
                  `completed_at` datetime DEFAULT NULL,
                  PRIMARY KEY (`id`),
                  KEY `idx_tool_id` (`tool_id`),
                  KEY `idx_task_id` (`task_id`),
                  KEY `idx_status` (`status`),
                  KEY `idx_user_id` (`user_id`),
                  KEY `idx_created_at` (`created_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具执行记录表';
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS `toolkit_execution`;
                DROP TABLE IF EXISTS `toolkit_definition`;
            """,
            state_operations=[
                migrations.CreateModel(
                    name='ToolkitDefinition',
                    fields=[
                        ('id', models.AutoField(primary_key=True, serialize=False)),
                        ('tool_key', models.CharField(max_length=100, unique=True, verbose_name='工具标识')),
                        ('name', models.CharField(max_length=100, verbose_name='工具名称')),
                        ('description', models.TextField(blank=True, default='', verbose_name='工具描述')),
                        ('icon', models.CharField(default='🔧', max_length=50, verbose_name='图标')),
                        ('category', models.CharField(choices=[('image', '图片处理'), ('text', '文本处理'), ('file', '文件转换'), ('convert', '格式转换'), ('other', '其他')], default='other', max_length=50, verbose_name='分类')),
                        ('input_schema', models.JSONField(verbose_name='输入参数定义')),
                        ('output_type', models.CharField(choices=[('file', '文件'), ('text', '文本'), ('json', 'JSON')], default='file', max_length=50, verbose_name='输出类型')),
                        ('is_async', models.BooleanField(default=True, verbose_name='是否异步')),
                        ('timeout_seconds', models.IntegerField(default=300, verbose_name='超时时间')),
                        ('is_enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                        ('user_id', models.IntegerField(verbose_name='用户ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                    ],
                    options={
                        'db_table': 'toolkit_definition',
                        'ordering': ['category', 'id'],
                        'verbose_name': '工具定义',
                        'managed': False,
                    },
                ),
                migrations.CreateModel(
                    name='ToolkitExecution',
                    fields=[
                        ('id', models.BigAutoField(primary_key=True, serialize=False)),
                        ('tool', models.ForeignKey(db_column='tool_id', on_delete=models.deletion.CASCADE, to='toolkit.ToolkitDefinition', verbose_name='工具')),
                        ('task_id', models.CharField(blank=True, default='', max_length=100, verbose_name='任务ID')),
                        ('input_params', models.JSONField(verbose_name='输入参数')),
                        ('output_result', models.TextField(blank=True, default='', verbose_name='输出结果')),
                        ('output_file', models.CharField(blank=True, default='', max_length=500, verbose_name='输出文件路径')),
                        ('status', models.CharField(choices=[('pending', '等待中'), ('running', '执行中'), ('success', '成功'), ('failed', '失败'), ('cancelled', '已取消')], default='pending', max_length=20, verbose_name='状态')),
                        ('progress', models.IntegerField(default=0, verbose_name='进度百分比')),
                        ('error_message', models.TextField(blank=True, default='', verbose_name='错误信息')),
                        ('execution_time_ms', models.IntegerField(blank=True, null=True, verbose_name='执行耗时')),
                        ('user_id', models.IntegerField(verbose_name='用户ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                    ],
                    options={
                        'db_table': 'toolkit_execution',
                        'ordering': ['-created_at'],
                        'verbose_name': '工具执行记录',
                        'managed': False,
                    },
                ),
            ],
        ),
    ]
