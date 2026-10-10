"""pytest 全局配置：测试库建表与共享 fixture"""
import pytest
from django.db import connection

# wealth_bill_list 无 Django 模型（纯原生 SQL 操作的外部表），
# Django migrate 不会在测试库创建它，这里手动镜像生产表结构。
_CREATE_BILL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_bill_list` (
  `id` int NOT NULL AUTO_INCREMENT,
  `transaction_type` varchar(10) NOT NULL,
  `date` datetime NOT NULL,
  `category` varchar(50) DEFAULT NULL,
  `subcategory` varchar(50) DEFAULT NULL,
  `necessity` varchar(10) DEFAULT NULL,
  `period_tag` varchar(10) DEFAULT NULL COMMENT '赎回归属(为自己/过渡/外部/不计入)',
  `project` varchar(100) DEFAULT NULL,
  `account` varchar(50) DEFAULT NULL,
  `account_currency` varchar(10) DEFAULT NULL,
  `amount` decimal(10,2) NOT NULL,
  `member` varchar(50) DEFAULT NULL,
  `merchant` varchar(100) DEFAULT NULL,
  `notes` text,
  `related_id` varchar(100) DEFAULT NULL,
  `year` int DEFAULT NULL,
  `month` int DEFAULT NULL,
  `day` int DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_date` (`date`),
  KEY `idx_type` (`transaction_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# temporal_time_atracker_tasks_list（TemporalTask managed=False 外部表镜像）
_CREATE_TASK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `temporal_time_atracker_tasks_list` (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_name` varchar(255) NOT NULL,
  `task_description` text,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `duration` time DEFAULT NULL,
  `duration_hours` double DEFAULT NULL,
  `notes` text,
  `tags` text,
  `task_type` varchar(100) DEFAULT '其他',
  `year` int DEFAULT NULL,
  `mon` varchar(10) DEFAULT NULL,
  `day` int DEFAULT NULL,
  `week` int DEFAULT NULL,
  `quarter` int DEFAULT NULL,
  `category_level1` varchar(50) DEFAULT NULL,
  `category_level2` varchar(50) DEFAULT NULL,
  `category_color` varchar(20) DEFAULT NULL,
  `import_batch` varchar(50) DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# temporal_oneday_page_list（OneDayPage managed=False 外部表镜像）
_CREATE_ONEDAY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `temporal_oneday_page_list` (
  `oid` int NOT NULL AUTO_INCREMENT,
  `years` varchar(25) DEFAULT NULL,
  `oneday` int DEFAULT NULL,
  `page` int DEFAULT NULL,
  `total` int DEFAULT NULL,
  `title` varchar(255) NOT NULL,
  `begin_date` date NOT NULL,
  `otype` varchar(50) DEFAULT 'ONEDAY',
  `update_date` date DEFAULT NULL,
  `flag` varchar(50) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `user_id` bigint DEFAULT NULL,
  PRIMARY KEY (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# health_step_info（HealthRecord managed=False 外部表镜像）
_CREATE_STEP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `health_step_info` (
  `hid` int NOT NULL AUTO_INCREMENT,
  `steps` int DEFAULT NULL,
  `htype` int DEFAULT 1,
  `cofficient` double DEFAULT NULL,
  `total` double DEFAULT NULL,
  `time` datetime DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `years` varchar(25) DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`hid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
# relationship_relationship（Relationship managed=False 镜像）
_CREATE_RELATIONSHIP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `relationship_relationship` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `alias` varchar(200) DEFAULT '',
  `met_date` date DEFAULT NULL,
  `met_place` varchar(200) DEFAULT '',
  `met_scene` text,
  `identity_then` varchar(200) DEFAULT '',
  `they_give_me` text,
  `i_give_them` text,
  `current_status` varchar(20) DEFAULT 'active',
  `current_quality` varchar(20) DEFAULT 'neutral',
  `notes` text,
  `tags` varchar(200) DEFAULT '',
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# relationship_interaction（Interaction managed=False 镜像）
_CREATE_INTERACTION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `relationship_interaction` (
  `id` int NOT NULL AUTO_INCREMENT,
  `relationship_id` int NOT NULL,
  `happened_at` datetime NOT NULL,
  `method` varchar(20) DEFAULT '',
  `energy_score` smallint NOT NULL,
  `summary` varchar(200) DEFAULT '',
  `quality_shift` varchar(20) DEFAULT '',
  `next_reminder` varchar(200) DEFAULT '',
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `my_action` longtext NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# wealth_balance_list（WealthBalanceList managed=False 镜像）
_CREATE_BALANCE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_balance_list` (
  `yearmon` varchar(10) NOT NULL,
  `wageincome` float DEFAULT NULL,
  `otherincome` float DEFAULT NULL,
  `outmoney` float DEFAULT NULL,
  `mbalance` float DEFAULT NULL,
  `btime` datetime DEFAULT NULL,
  `balance` float DEFAULT NULL,
  `accumulationfund` float DEFAULT NULL,
  `total` float DEFAULT NULL,
  `remarks` varchar(255) DEFAULT NULL,
  `distance` float DEFAULT NULL,
  `borrow` float DEFAULT NULL,
  `lend` float DEFAULT NULL,
  `realnum` float DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`yearmon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
# travel_list_info（TravelRecord managed=False 镜像，summary 聚合器依赖）
_CREATE_TRAVEL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `travel_list_info` (
  `tid` int NOT NULL AUTO_INCREMENT,
  `parentnode` varchar(50) DEFAULT NULL,
  `tname` varchar(255) DEFAULT NULL,
  `tyear` int DEFAULT NULL,
  `tcost` float DEFAULT NULL,
  `duration_days` int DEFAULT NULL,
  `rating` int DEFAULT NULL,
  `companions` varchar(200) DEFAULT NULL,
  `latitude` decimal(10,6) DEFAULT NULL,
  `longitude` decimal(10,6) DEFAULT NULL,
  `ttime` date DEFAULT NULL,
  `tremark` varchar(255) DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `district` varchar(100) DEFAULT '',
  PRIMARY KEY (`tid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
# toolkit_definition（ToolkitDefinition managed=False 镜像）
_CREATE_TOOLKIT_DEF_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_definition` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tool_key` varchar(100) NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` text,
  `icon` varchar(50) DEFAULT '?',
  `category` varchar(50) DEFAULT 'other',
  `input_schema` json NOT NULL,
  `output_type` varchar(50) DEFAULT 'file',
  `is_enabled` tinyint DEFAULT 1,
  `is_async` tinyint DEFAULT 1,
  `timeout_seconds` int DEFAULT 300,
  `user_id` int DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


# toolkit_decision_tracker / toolkit_decision_record（managed 新表，--no-migrations 下镜像）
_CREATE_TRACKER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_decision_tracker` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` integer NOT NULL,
  `topic` varchar(200) NOT NULL,
  `background` longtext NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `status` varchar(20) NOT NULL,
  `final_decision` varchar(50) NOT NULL,
  `decision_date` date NULL,
  `review_note` longtext NOT NULL,
  `lean_options` json NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_RECORD_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_decision_record` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `record_date` date NOT NULL,
  `tendency` varchar(50) NOT NULL,
  `reason` longtext NOT NULL,
  `intensity` smallint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `tracker_id` integer NOT NULL,
  KEY `tracker_record_idx` (`tracker_id`, `record_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# toolkit_electricity_record（managed 表，--no-migrations 下镜像）
# ⚠️ DDL 与 `manage.py sqlmigrate toolkit 0001_squashed_0018` 逐字对齐
_CREATE_ELECTRICITY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_electricity_record` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` integer NOT NULL,
  `record_date` date NOT NULL,
  `meter_reading` numeric(10, 1) NOT NULL,
  `interval_usage` numeric(10, 1) NULL,
  `interval_days` integer NULL,
  `daily_avg` numeric(10, 2) NULL,
  `month_usage` numeric(10, 1) NULL,
  `notes` longtext NOT NULL,
  `created_at` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# core_user_profile（用户配置，managed 表，--no-migrations 下镜像）
# ⚠️ 2026-09-30（v3.60.12）首次纳入：core app 长期**零测试**，所以这张表一直
#    靠 `--reuse-db` 复用旧测试库里的表在「蒙着」—— 测试库一旦重建就全挂。
#    DDL 与 `sqlmigrate core 0001`（建表）＋ `sqlmigrate core 0007`（补列）逐字对齐。
_CREATE_CORE_USER_PROFILE_SQL = """
CREATE TABLE IF NOT EXISTS `core_user_profile` (
  `id` bigint NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` integer NOT NULL UNIQUE,
  `privacy_mode` bool NOT NULL,
  `logseq_path` varchar(500) NOT NULL,
  `quote_pool_max_len` integer UNSIGNED NOT NULL DEFAULT 500
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# toolkit_quote（摘录馆，managed 表，--no-migrations 下镜像）
# ⚠️ 2026-09-30 补建：此前漏了这一张，靠 `--reuse-db` 在旧测试库上「蒙着」能跑 ——
#    一旦测试库重建（换机器 / 删库重跑），所有涉及摘录的用例会直接报「表不存在」。
#    DDL 与 `sqlmigrate toolkit 0001_squashed_0018` 的输出逐字对齐。
_CREATE_QUOTE_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_quote` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` integer NOT NULL,
  `content` longtext NOT NULL,
  `author` varchar(200) NOT NULL,
  `language` varchar(20) NOT NULL,
  `category` varchar(50) NOT NULL,
  `is_paragraph` bool NOT NULL,
  `short_title` varchar(100) NOT NULL,
  `source` varchar(200) NOT NULL,
  `tags` varchar(500) NOT NULL,
  `is_favorite` bool NOT NULL,
  `review_count` integer NOT NULL,
  `created_at` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# toolkit_ask_topic / toolkit_ask_answer / toolkit_ask_scene（managed 表，--no-migrations 下镜像）
_CREATE_ASK_SCENE_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_ask_scene` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` longtext NOT NULL,
  `sort` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_ASK_TOPIC_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_ask_topic` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` integer NOT NULL,
  `scene_id` integer NULL,
  `title` varchar(200) NOT NULL,
  `question` longtext NOT NULL,
  `background` longtext NOT NULL,
  `tags` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  KEY `ask_topic_scene_idx` (`scene_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_ASK_ANSWER_SQL = """
CREATE TABLE IF NOT EXISTS `toolkit_ask_answer` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `parent_id` integer NULL,
  `question` longtext NOT NULL,
  `ai` varchar(50) NOT NULL,
  `session` varchar(100) NOT NULL,
  `answer` longtext NOT NULL,
  `asked_at` datetime(6) NOT NULL,
  `verdict` varchar(10) NOT NULL,
  `note` longtext NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `topic_id` integer NOT NULL,
  KEY `ask_topic_asked_idx` (`topic_id`, `asked_at`),
  KEY `ask_answer_parent_idx` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# travel_wish（旅行心愿单，镜像迁移 0003 的建表，--reuse-db 下已手动补齐）
_CREATE_WISH_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `travel_wish` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(200) NOT NULL,
  `category` varchar(20) NOT NULL,
  `province` varchar(50) NOT NULL,
  `city` varchar(100) NOT NULL,
  `district` varchar(100) NOT NULL DEFAULT '',
  `lng` double NULL,
  `lat` double NULL,
  `status` varchar(20) NOT NULL,
  `visited_at` date NULL,
  `visit_rating` smallint unsigned NULL,
  `visit_notes` longtext NOT NULL,
  `worth_revisit` tinyint(1) NOT NULL,
  `visit_plan_id` int NULL,
  `visit_record_id` int NULL,
  `notes` longtext NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  KEY `travel_wish_name_c47f26_idx` (`name`),
  KEY `travel_wish_provinc_b3c39f_idx` (`province`),
  KEY `travel_wish_status_ce8a7b_idx` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 三年赎回期（redemption app，managed 表，--no-migrations 下镜像）
_CREATE_REDEMPTION_PERIOD_SQL = """
CREATE TABLE IF NOT EXISTS `redemption_period` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `pool_principal` numeric(14, 2) NOT NULL,
  `tracking_status` varchar(10) NOT NULL,
  `paused_since` date NULL,
  `resume_at` date NULL,
  `baseline_toward_ratio` numeric(5, 4) NULL,
  `baseline_set_week` integer NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_REDEMPTION_INJECT_SQL = """
CREATE TABLE IF NOT EXISTS `redemption_pool_inject` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `inject_date` date NOT NULL,
  `amount` numeric(14, 2) NOT NULL,
  `source` varchar(20) NOT NULL,
  `note` longtext NULL,
  `created_at` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_REDEMPTION_RULE_SQL = """
CREATE TABLE IF NOT EXISTS `redemption_attr_rule` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `match_field` varchar(20) NOT NULL,
  `match_value` varchar(100) NOT NULL,
  `attribution` varchar(10) NOT NULL,
  `priority` integer NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `note` longtext NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_REDEMPTION_SNAPSHOT_SQL = """
CREATE TABLE IF NOT EXISTS `redemption_week_snapshot` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `year` integer NOT NULL,
  `week` integer NOT NULL,
  `toward_hours` double NOT NULL,
  `maintain_hours` double NOT NULL,
  `external_hours` double NOT NULL,
  `drain_hours` double NOT NULL,
  `covered_hours` double NOT NULL,
  `theoretical_hours` double NOT NULL,
  `coverage_rate` double NOT NULL,
  `toward_ratio` double NOT NULL,
  `unit_cost` numeric(10, 2) NULL,
  `snapshot_at` datetime(6) NOT NULL,
  UNIQUE KEY `redemption_week_snapshot_year_week_1d0c3b_idx` (`year`, `week`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 时间重构 L1 分组 / L2 活动类型映射（managed 表，--no-migrations 下镜像）
_CREATE_ACTIVITY_GROUP_SQL = """
CREATE TABLE IF NOT EXISTS `temporal_activity_group` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name` varchar(50) NOT NULL,
  `color` varchar(7) NULL,
  `sort_order` integer NOT NULL,
  `is_system` tinyint(1) NOT NULL,
  `note` longtext NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  UNIQUE KEY `temporal_activity_group_name_4a5c8d_idx` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_TASK_META_SQL = """
CREATE TABLE IF NOT EXISTS `temporal_task_meta` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `task_name` varchar(255) NOT NULL,
  `activity_type` varchar(50) NOT NULL,
  `default_attribution` varchar(10) NULL,
  `is_system` tinyint(1) NOT NULL,
  `note` longtext NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `group_id` integer NULL,
  UNIQUE KEY `temporal_task_meta_task_name_6b7e1f_idx` (`task_name`),
  KEY `temporal_ta_activi_2d3a6f_idx` (`activity_type`),
  KEY `temporal_ta_group_3c4b7e_idx` (`group_id`),
  CONSTRAINT `temporal_task_meta_group_id_8c9d2a_fk` FOREIGN KEY (`group_id`)
    REFERENCES `temporal_activity_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


# 负债明细 / 应收借出（wealth app managed 新表，--no-migrations --reuse-db 下镜像）
# ⚠️ DDL 必须与 manage.py sqlmigrate wealth 0016 的输出逐字对齐，
#    否则测试库与开发库结构漂移，测试通过只说明「镜像自洽」。
_CREATE_LIABILITY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_liability_detail` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name` varchar(50) NOT NULL,
  `category` varchar(10) NOT NULL,
  `principal` double NOT NULL,
  `outstanding` double NOT NULL,
  `annual_rate` double NOT NULL,
  `start_date` date NULL,
  `due_date` date NULL,
  `repayment_method` varchar(10) NOT NULL,
  `monthly_payment` double NOT NULL,
  `status` varchar(10) NOT NULL,
  `remark` varchar(200) NULL,
  `user_id` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  KEY `wealth_liab_user_id_b0abef_idx` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_RECEIVABLE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_receivable_detail` (
  `id` integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `counterparty` varchar(50) NOT NULL,
  `principal` double NOT NULL,
  `received` double NOT NULL,
  `lend_date` date NULL,
  `due_date` date NULL,
  `annual_rate` double NOT NULL,
  `status` varchar(10) NOT NULL,
  `remark` varchar(200) NULL,
  `user_id` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  KEY `wealth_rece_user_id_95e4d6_idx` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


# wealth_cash_flow（WealthCashFlow managed=False 镜像）
# 这张是外部遗留表，Django migrate 不建；此前仅靠「复用已有测试库」碰巧存在，
# 一旦有人跑 --create-db 就会消失，整组资产口径测试集体报「表不存在」。
# 补上镜像后 --create-db 也能自洽（--reuse-db 仍照常走 IF NOT EXISTS 跳过）。
_CREATE_CASHFLOW_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_cash_flow` (
  `baid` int NOT NULL AUTO_INCREMENT COMMENT '编号',
  `yearmon` varchar(10) DEFAULT NULL COMMENT '年月',
  `zplay` float DEFAULT NULL COMMENT '支付宝',
  `wechat` float DEFAULT NULL COMMENT '微信',
  `cash` float DEFAULT NULL COMMENT '现金',
  `jianbank` float DEFAULT NULL COMMENT '建行',
  `gongbank` float DEFAULT NULL COMMENT '工行',
  `zhongbank` float DEFAULT NULL COMMENT '中国银行',
  `nongbank` float DEFAULT NULL COMMENT '农村信用社',
  `accumulationfund` float DEFAULT NULL COMMENT '公积金',
  `lend` float DEFAULT NULL COMMENT '借出',
  `borrow` float DEFAULT NULL COMMENT '负债',
  `flow_total` float DEFAULT NULL COMMENT '总现金流',
  `total` float DEFAULT NULL COMMENT '总额',
  `btime` date DEFAULT NULL COMMENT '复盘时间',
  `remarks` varchar(255) DEFAULT NULL COMMENT '备注',
  `realnum` float DEFAULT NULL COMMENT '真正在手里的',
  PRIMARY KEY (`baid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 资产科目 / 快照头 / 快照明细（wealth app managed 新表，--no-migrations --reuse-db 下镜像）
# ⚠️ DDL 必须与 manage.py sqlmigrate wealth 0017 的输出逐字对齐，
#    否则测试库与开发库结构漂移，测试通过只说明「镜像自洽」。
#    注意两条 FK 未写 ON DELETE：MySQL 默认 RESTRICT，与 Django 侧
#    `on_delete=PROTECT`（account）双保险一致 —— 被快照引用的科目删不掉。
_CREATE_ASSET_ACCOUNT_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_asset_account` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `code` varchar(20) NULL,
  `name` varchar(50) NOT NULL,
  `category` varchar(10) NOT NULL,
  `account_kind` varchar(20) NOT NULL,
  `institution` varchar(50) NULL,
  `is_liquid` bool NOT NULL,
  `include_in_balance_sheet` bool NOT NULL,
  `sort` integer NOT NULL,
  `is_active` bool NOT NULL,
  `note` varchar(200) NULL,
  `user_id` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  CONSTRAINT `wealth_asset_account_user_code_uniq` UNIQUE (`user_id`, `code`),
  KEY `wealth_acct_user_active_idx` (`user_id`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_ASSET_SNAPSHOT_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_asset_snapshot` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `yearmon` varchar(10) NOT NULL,
  `snapshot_date` date NULL,
  `borrow` double precision NOT NULL,
  `lend` double precision NOT NULL,
  `remarks` varchar(255) NULL,
  `user_id` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  CONSTRAINT `wealth_asset_snap_user_yearmon_uniq` UNIQUE (`user_id`, `yearmon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_ASSET_SNAPSHOT_ITEM_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_asset_snapshot_item` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `amount` double precision NOT NULL,
  `account_id` integer NOT NULL,
  `snapshot_id` integer NOT NULL,
  CONSTRAINT `wealth_asset_item_snap_acct_uniq` UNIQUE (`snapshot_id`, `account_id`),
  CONSTRAINT `wealth_asset_snapsho_account_id_75c9cd8f_fk_wealth_as` FOREIGN KEY (`account_id`) REFERENCES `wealth_asset_account` (`id`),
  CONSTRAINT `wealth_asset_snapsho_snapshot_id_a6f8d20b_fk_wealth_as` FOREIGN KEY (`snapshot_id`) REFERENCES `wealth_asset_snapshot` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


# ⚠️ DDL 必须与 manage.py sqlmigrate wealth 0018 的输出逐字对齐
_CREATE_CLASSIFY_RULE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_classify_rule` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `rule_field` varchar(20) NOT NULL,
  `match_value` varchar(100) NOT NULL,
  `income_type` varchar(10) NULL,
  `expense_nature` varchar(10) NULL,
  `cashflow_class` varchar(20) NULL,
  `priority` integer NOT NULL,
  `is_active` bool NOT NULL,
  `note` varchar(200) NULL,
  `user_id` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  CONSTRAINT `wealth_classify_user_field_value_uniq` UNIQUE (`user_id`, `rule_field`, `match_value`),
  KEY `wealth_cls_user_active_idx` (`user_id`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


# ⚠️ 以下 5 张 DDL 必须与 manage.py sqlmigrate wealth 0019 的输出逐字对齐
#    （--no-migrations --reuse-db 下新 managed 表不会自动进测试库）。
#    建表顺序不能改：item 的 unit_id 外键指向 unit，必须先建 category → unit。
_CREATE_SURVIVAL_CATEGORY_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_category` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(50) NOT NULL,
  `consume_mode` varchar(20) NOT NULL,
  `aggregate_mode` varchar(20) NOT NULL,
  `icon` varchar(20) NOT NULL,
  `description` varchar(200) NOT NULL,
  `sort_order` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  CONSTRAINT `wealth_surv_cat_user_name_uniq` UNIQUE (`user_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_UNIT_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_unit` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(20) NOT NULL,
  `base_unit` varchar(20) NOT NULL,
  `to_base_rate` numeric(14, 4) NOT NULL,
  `is_serving_unit` bool NOT NULL,
  `note` varchar(100) NOT NULL,
  `sort_order` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `category_id` integer NOT NULL,
  CONSTRAINT `wealth_surv_unit_user_cat_name_uniq` UNIQUE (`user_id`, `category_id`, `name`),
  CONSTRAINT `wealth_survival_unit_category_id_268df492_fk_wealth_su` FOREIGN KEY (`category_id`) REFERENCES `wealth_survival_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_ITEM_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_item` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(200) NOT NULL,
  `quantity` numeric(14, 2) NOT NULL,
  `satiety` varchar(20) NOT NULL,
  `grade` varchar(20) NOT NULL,
  `status` varchar(20) NOT NULL,
  `priority` varchar(20) NOT NULL,
  `days_per_unit` numeric(10, 1) NULL,
  `hours_per_unit` numeric(8, 1) NULL,
  `uses_per_unit` numeric(10, 2) NULL,
  `use_cycle_num` numeric(6, 2) NULL,
  `use_cycle_unit` varchar(10) NULL,
  `use_times` numeric(6, 2) NULL,
  `stocktake_cycle_days` integer NULL,
  `restock_threshold` numeric(14, 2) NULL,
  `expire_date` date NULL,
  `purchase_date` date NULL,
  `purchase_cost` numeric(12, 2) NULL,
  `notes` longtext NOT NULL,
  `tags` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `category_id` integer NOT NULL,
  `unit_id` integer NULL,
  CONSTRAINT `wealth_survival_item_unit_id_17ac547d_fk_wealth_survival_unit_id` FOREIGN KEY (`unit_id`) REFERENCES `wealth_survival_unit` (`id`),
  CONSTRAINT `wealth_survival_item_category_id_c605b88a_fk_wealth_su` FOREIGN KEY (`category_id`) REFERENCES `wealth_survival_category` (`id`),
  KEY `wealth_surv_item_cat_idx` (`user_id`, `category_id`),
  KEY `wealth_surv_item_expire_idx` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_RECIPE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_recipe` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(50) NOT NULL,
  `meals_per_day` numeric(4, 1) NOT NULL,
  `note` varchar(200) NOT NULL,
  `sort_order` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `category_id` integer NOT NULL,
  CONSTRAINT `wealth_surv_recipe_user_cat_name_uniq` UNIQUE (`user_id`, `category_id`, `name`),
  CONSTRAINT `wealth_survival_reci_category_id_37c39886_fk_wealth_su` FOREIGN KEY (`category_id`) REFERENCES `wealth_survival_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_RECIPE_LINE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_recipe_line` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `role` varchar(20) NOT NULL,
  `quantity_per_serving` numeric(14, 4) NOT NULL,
  `note` varchar(200) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `item_id` integer NOT NULL,
  `recipe_id` integer NOT NULL,
  `unit_id` integer NULL,
  CONSTRAINT `wealth_survival_reci_item_id_7b239286_fk_wealth_su` FOREIGN KEY (`item_id`) REFERENCES `wealth_survival_item` (`id`),
  CONSTRAINT `wealth_survival_reci_recipe_id_880447c2_fk_wealth_su` FOREIGN KEY (`recipe_id`) REFERENCES `wealth_survival_recipe` (`id`),
  CONSTRAINT `wealth_survival_reci_unit_id_2be21627_fk_wealth_su` FOREIGN KEY (`unit_id`) REFERENCES `wealth_survival_unit` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
# 盘点快照（v3.59.0 二期）—— 与 `sqlmigrate wealth 0020` 输出逐字对齐。
# ⚠️ 外键**不写 ON DELETE**：Django 的 CASCADE / SET_NULL 由应用层执行，
#    DB 层加了子句就与真实迁移不一致，测试会掩盖真实的删除行为。
_CREATE_SURVIVAL_SNAPSHOT_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_snapshot` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `snapshot_date` date NOT NULL,
  `source` varchar(20) NOT NULL,
  `note` varchar(200) NOT NULL,
  `days_optimistic` numeric(12, 2) NULL,
  `days_likely` numeric(12, 2) NULL,
  `days_pessimistic` numeric(12, 2) NULL,
  `days_expected` numeric(12, 2) NULL,
  `spread` numeric(12, 2) NULL,
  `shortest_category` varchar(50) NOT NULL,
  `bottleneck` varchar(20) NOT NULL,
  `cash_months` numeric(10, 2) NULL,
  `cash_days` numeric(12, 2) NULL,
  `coverage_pct` numeric(8, 2) NULL,
  `coverage_remaining_days` integer NULL,
  `category_count` integer NOT NULL,
  `item_count` integer NOT NULL,
  `snack_days` numeric(12, 2) NULL,
  `issue_count` integer NOT NULL,
  `trustworthy` bool NOT NULL,
  `created_at` datetime(6) NOT NULL,
  CONSTRAINT `wealth_surv_snap_user_date_uniq` UNIQUE (`user_id`, `snapshot_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_SNAPSHOT_CATEGORY_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_snapshot_category` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `category_name` varchar(50) NOT NULL,
  `consume_mode` varchar(20) NOT NULL,
  `aggregate_mode_effective` varchar(20) NOT NULL,
  `days_optimistic` numeric(12, 2) NULL,
  `days_likely` numeric(12, 2) NULL,
  `days_pessimistic` numeric(12, 2) NULL,
  `days_expected` numeric(12, 2) NULL,
  `usable_item_count` integer NOT NULL,
  `item_count` integer NOT NULL,
  `snack_days` numeric(12, 2) NULL,
  `hours_total` numeric(12, 1) NULL,
  `issue_count` integer NOT NULL,
  `trustworthy` bool NOT NULL,
  `category_id` integer NULL,
  `snapshot_id` integer NOT NULL,
  CONSTRAINT `wealth_surv_snapcat_name_uniq` UNIQUE (`snapshot_id`, `category_name`),
  CONSTRAINT `wealth_survival_snap_category_id_3d6defd1_fk_wealth_su` FOREIGN KEY (`category_id`) REFERENCES `wealth_survival_category` (`id`),
  CONSTRAINT `wealth_survival_snap_snapshot_id_5148c583_fk_wealth_su` FOREIGN KEY (`snapshot_id`) REFERENCES `wealth_survival_snapshot` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
# 实盘盘点（v3.59.3）—— 与 `sqlmigrate wealth 0021` 输出逐字对齐。
# ⚠️ 同样不写 ON DELETE：`item` 的 SET_NULL 与 `stocktake` 的 CASCADE 都由应用层执行。
_CREATE_SURVIVAL_STOCKTAKE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_stocktake` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `stocktake_date` date NOT NULL,
  `source` varchar(20) NOT NULL,
  `note` varchar(200) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  KEY `wealth_surv_take_date_idx` (`user_id`, `stocktake_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_STOCKTAKE_LINE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_stocktake_line` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `item_name` varchar(200) NOT NULL,
  `category_name` varchar(50) NOT NULL,
  `unit_name` varchar(20) NOT NULL,
  `book_quantity` numeric(14, 2) NOT NULL,
  `actual_quantity` numeric(14, 2) NOT NULL,
  `note` varchar(200) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `item_id` integer NULL,
  `stocktake_id` integer NOT NULL,
  CONSTRAINT `wealth_survival_stoc_item_id_696ab844_fk_wealth_su` FOREIGN KEY (`item_id`) REFERENCES `wealth_survival_item` (`id`),
  CONSTRAINT `wealth_survival_stoc_stocktake_id_411b0c30_fk_wealth_su` FOREIGN KEY (`stocktake_id`) REFERENCES `wealth_survival_stocktake` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 必需品基准清单（v3.59.7；v3.59.12 起关联改为多对多，本表不再有 `item_id`）
# —— 与 `sqlmigrate wealth 0024` 输出逐字对齐。
# ⚠️ 同样不写 ON DELETE：`category` 的 CASCADE 由应用层执行。
# ⚠️ 旧测试库（`--reuse-db` 复用的那份）里这张表**还留着 `item_id` 列** ——
#    `CREATE TABLE IF NOT EXISTS` 遇到已存在的表什么也不做。留着无害：
#    模型里已经没有这个字段，ORM 既不 SELECT 也不写它。不去 ALTER DROP
#    是为了守住「只加缺的列，不删列、不动数据」那条非破坏性约定。
_CREATE_SURVIVAL_ESSENTIAL_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_essential` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(100) NOT NULL,
  `scope` varchar(20) NOT NULL,
  `unit_name` varchar(20) NOT NULL,
  `hint` varchar(200) NOT NULL,
  `note` varchar(200) NOT NULL,
  `sort_order` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `category_id` integer NOT NULL,
  KEY `wealth_surv_ess_cat_idx` (`user_id`, `category_id`),
  CONSTRAINT `wealth_surv_ess_user_name_uniq` UNIQUE (`user_id`, `name`),
  CONSTRAINT `wealth_survival_esse_category_id_09628944_fk_wealth_su` FOREIGN KEY (`category_id`) REFERENCES `wealth_survival_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 必需品 ↔ 物品 的多对多中间表（v3.59.12）—— 与 `sqlmigrate wealth 0024` 逐字对齐。
# 🔴 这是本项目第一张 **Django 自动创建**的中间表（没有显式 through 模型），
#    表名与列名都是 Django 按规则拼的，不能凭印象写 ——
#    必须照抄 `sqlmigrate` 的输出。⚠️ 主键是 `bigint`（不是其它表的 `integer`）。
_CREATE_SURVIVAL_ESSENTIAL_ITEMS_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_essential_items` (
  `id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `survivalessential_id` integer NOT NULL,
  `survivalitem_id` integer NOT NULL,
  CONSTRAINT `wealth_survival_essentia_survivalessential_id_sur_79bcf1de_uniq` UNIQUE (`survivalessential_id`, `survivalitem_id`),
  CONSTRAINT `wealth_survival_esse_survivalessential_id_a3a66c92_fk_wealth_su` FOREIGN KEY (`survivalessential_id`) REFERENCES `wealth_survival_essential` (`id`),
  CONSTRAINT `wealth_survival_esse_survivalitem_id_0fc5ff14_fk_wealth_su` FOREIGN KEY (`survivalitem_id`) REFERENCES `wealth_survival_item` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 组合（v3.59.13）—— 与 `sqlmigrate wealth 0025` 输出逐字对齐。
# 三张表都是**新建**的：既有 `wealth_survival_recipe_line` 一个字节都没动
# （组合行刻意另起一张表，见模型注释），所以这里没有补列 / 改列定义的活儿。
_CREATE_SURVIVAL_COMBO_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_combo` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(50) NOT NULL,
  `note` varchar(200) NOT NULL,
  `sort_order` integer NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `category_id` integer NOT NULL,
  KEY `wealth_surv_combo_cat_idx` (`user_id`, `category_id`),
  CONSTRAINT `wealth_surv_combo_user_cat_name_uniq` UNIQUE (`user_id`, `category_id`, `name`),
  CONSTRAINT `wealth_survival_comb_category_id_8bbccc4c_fk_wealth_su` FOREIGN KEY (`category_id`) REFERENCES `wealth_survival_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_COMBO_ITEM_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_combo_item` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `quantity_per_serving` numeric(14, 4) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `combo_id` integer NOT NULL,
  `item_id` integer NOT NULL,
  `unit_id` integer NULL,
  CONSTRAINT `wealth_surv_combo_item_uniq` UNIQUE (`combo_id`, `item_id`),
  CONSTRAINT `wealth_survival_comb_combo_id_a268e7fe_fk_wealth_su` FOREIGN KEY (`combo_id`) REFERENCES `wealth_survival_combo` (`id`),
  CONSTRAINT `wealth_survival_comb_item_id_71420722_fk_wealth_su` FOREIGN KEY (`item_id`) REFERENCES `wealth_survival_item` (`id`),
  CONSTRAINT `wealth_survival_comb_unit_id_361aae7c_fk_wealth_su` FOREIGN KEY (`unit_id`) REFERENCES `wealth_survival_unit` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_SURVIVAL_RECIPE_COMBO_LINE_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_recipe_combo_line` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `role` varchar(20) NOT NULL,
  `note` varchar(200) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `combo_id` integer NOT NULL,
  `recipe_id` integer NOT NULL,
  CONSTRAINT `wealth_surv_recipe_combo_uniq` UNIQUE (`recipe_id`, `combo_id`),
  CONSTRAINT `wealth_survival_reci_combo_id_21018b0a_fk_wealth_su` FOREIGN KEY (`combo_id`) REFERENCES `wealth_survival_combo` (`id`),
  CONSTRAINT `wealth_survival_reci_recipe_id_e66af64e_fk_wealth_su` FOREIGN KEY (`recipe_id`) REFERENCES `wealth_survival_recipe` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_PROPERTY_CATEGORY_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_property_category` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(50) NOT NULL,
  `icon` varchar(20) NOT NULL,
  `default_lifespan_months` integer NULL,
  `sort_order` integer NOT NULL,
  `note` varchar(200) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  CONSTRAINT `wealth_prop_cat_user_name_uniq` UNIQUE (`user_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
_CREATE_PROPERTY_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_property` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `name` varchar(100) NOT NULL,
  `spec` varchar(100) NOT NULL,
  `location` varchar(50) NOT NULL,
  `purchase_amount` numeric(12, 2) NULL,
  `purchase_date` date NULL,
  `lifespan_months` integer NULL,
  `status` varchar(20) NOT NULL,
  `condition` varchar(20) NOT NULL,
  `scrapped_date` date NULL,
  `dispose_note` varchar(200) NOT NULL,
  `note` longtext NOT NULL,
  `tags` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `category_id` integer NOT NULL,
  CONSTRAINT `wealth_property_category_id_7d927051_fk_wealth_pr` FOREIGN KEY (`category_id`) REFERENCES `wealth_property_category` (`id`),
  KEY `wealth_prop_user_cat_idx` (`user_id`, `category_id`),
  KEY `wealth_prop_status_idx` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# ⚠️ DDL 与 `manage.py sqlmigrate wealth 0027` 的输出逐字对齐。
#    两条外键：`item_id` → 物品表；`reverses_id` → **本表**（自引用）。
#    MySQL 支持表内自引用外键，所以两条都写在 CREATE TABLE 里。
#    FK 一律**不带 ON DELETE** —— Django 在应用层管级联，真实迁移里也不带；
#    手写时顺手加 `SET_NULL` 会让「测试库过了、开发库行为不同」。
_CREATE_SURVIVAL_FLOW_SQL = """
CREATE TABLE IF NOT EXISTS `wealth_survival_flow` (
  `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `user_id` integer NOT NULL,
  `item_name` varchar(200) NOT NULL,
  `category_name` varchar(50) NOT NULL,
  `unit_name` varchar(20) NOT NULL,
  `delta` numeric(14, 2) NOT NULL,
  `channel` varchar(20) NOT NULL,
  `reason` varchar(20) NOT NULL,
  `occurred_at` datetime(6) NOT NULL,
  `note` varchar(200) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `item_id` integer NULL,
  `reverses_id` integer NULL,
  CONSTRAINT `wealth_survival_flow_item_id_df20f67f_fk_wealth_survival_item_id` FOREIGN KEY (`item_id`) REFERENCES `wealth_survival_item` (`id`),
  CONSTRAINT `wealth_survival_flow_reverses_id_7fe23a1b_fk_wealth_su` FOREIGN KEY (`reverses_id`) REFERENCES `wealth_survival_flow` (`id`),
  KEY `wealth_surv_flow_time_idx` (`user_id`, `occurred_at`),
  KEY `wealth_surv_flow_item_idx` (`user_id`, `item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# ⚠️ 0021 给**已存在**的 `wealth_survival_item` 加了 6 列，这是本项目第一次
#    「给 survival 组的既有表加列」。`--reuse-db` 复用的旧测试库里那张表还是
#    0019 的样子，而 `CREATE TABLE IF NOT EXISTS` 遇到已存在的表**什么也不做** ——
#    结果是列不存在，一片用例报 OperationalError，看着像代码错、其实是环境错。
#    MySQL 又没有 `ADD COLUMN IF NOT EXISTS`，所以先查 information_schema 再补：
#    **只加缺的列，不删列、不动数据**（幂等的非破坏性 DDL）。
#    列定义取自 `sqlmigrate wealth 0021` 的 ALTER 语句原文；
#    带 DEFAULT 只是为了给已存在的行一个值，Django 在应用层仍会自己填默认值。
_SURVIVAL_ITEM_COLUMNS_0021 = (
    ('uses_per_unit', 'numeric(10, 2) NULL'),
    ('use_cycle_num', 'numeric(6, 2) NOT NULL DEFAULT 1'),
    ('use_cycle_unit', "varchar(10) NOT NULL DEFAULT 'day'"),
    ('use_times', 'numeric(6, 2) NOT NULL DEFAULT 1'),
    ('stocktake_cycle_days', 'integer NULL'),
    ('restock_threshold', 'numeric(14, 2) NULL'),
)


_SURVIVAL_ITEM_NULLABLE_0022 = (
    ('use_cycle_num', 'numeric(6, 2) NULL'),
    ('use_cycle_unit', 'varchar(10) NULL'),
    ('use_times', 'numeric(6, 2) NULL'),
)


def _patch_survival_item_columns(cursor) -> None:
    """给已存在的 `wealth_survival_item` 对齐 0021 / 0022 的列定义（幂等、不删不动）

    `--reuse-db` 下这张表早就建好了，而 `CREATE TABLE IF NOT EXISTS` 既不会补列、
    更不会改列定义 —— 两条路径都得显式走一遍：
      0021 补列（缺的才补）；0022 把频次三列放宽成可空（还是 NOT NULL 才改）。
    """
    cursor.execute(
        """
        SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wealth_survival_item'
        """,
    )
    rows = {row[0]: row[1] for row in cursor.fetchall()}
    if not rows:
        return          # 表还没建：上面那条 CREATE 已经带着新列一起建了
    for name, definition in _SURVIVAL_ITEM_COLUMNS_0021:
        if name in rows:
            continue
        # 列名与定义都是本文件里的字面量，不来自外部输入
        cursor.execute(
            f'ALTER TABLE `wealth_survival_item` ADD COLUMN `{name}` {definition}',
        )
    for name, definition in _SURVIVAL_ITEM_NULLABLE_0022:
        if rows.get(name) != 'NO':
            continue
        cursor.execute(
            f'ALTER TABLE `wealth_survival_item` MODIFY COLUMN `{name}` {definition}',
        )


def _patch_core_user_profile_columns(cursor) -> None:
    """给**已存在**的 `core_user_profile` 补上 0007 的新列（幂等、不删不动）。

    `--reuse-db` 复用的旧测试库里这张表还是 0001 的样子，而
    `CREATE TABLE IF NOT EXISTS` 遇到已存在的表**什么也不做** ⇒ 新列不存在、
    凡读配置的用例一片 OperationalError（看着像代码错、其实是环境错）。
    MySQL 没有 `ADD COLUMN IF NOT EXISTS`，所以先查 information_schema 再补。

    列定义取自 `sqlmigrate core 0007` 的 ALTER 原文
    （`integer UNSIGNED DEFAULT 500 NOT NULL`；未带 CHECK，与 survival 补列的既有写法一致 ——
    该约束由 Django 侧 `validators` 保证，测试不依赖 DB CHECK）。
    """
    cursor.execute(
        """
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'core_user_profile'
        """,
    )
    existing = {row[0] for row in cursor.fetchall()}
    if not existing:
        return          # 表还没建：上面那条 CREATE 已经带着新列一起建了
    if 'quote_pool_max_len' not in existing:
        cursor.execute(
            'ALTER TABLE `core_user_profile` ADD COLUMN `quote_pool_max_len` '
            'integer UNSIGNED NOT NULL DEFAULT 500',
        )
@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """在 Django 迁移建库之后，补齐原生 SQL 表"""
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            # 用户配置（v3.60.12）：金句池长度上限存在这张表里，toolkit 侧要读它
            # ⇒ 排在所有 toolkit 相关的建表之前；旧库里缺列时由 patch 顺手补上
            cursor.execute(_CREATE_CORE_USER_PROFILE_SQL)
            _patch_core_user_profile_columns(cursor)
            cursor.execute(_CREATE_BILL_TABLE_SQL)
            cursor.execute(_CREATE_TASK_TABLE_SQL)
            cursor.execute(_CREATE_ONEDAY_TABLE_SQL)
            cursor.execute(_CREATE_STEP_TABLE_SQL)
            cursor.execute(_CREATE_RELATIONSHIP_TABLE_SQL)
            cursor.execute(_CREATE_INTERACTION_TABLE_SQL)
            cursor.execute(_CREATE_BALANCE_TABLE_SQL)
            cursor.execute(_CREATE_TRAVEL_TABLE_SQL)
            cursor.execute(_CREATE_TOOLKIT_DEF_TABLE_SQL)
            cursor.execute(_CREATE_TRACKER_TABLE_SQL)
            cursor.execute(_CREATE_RECORD_TABLE_SQL)
            cursor.execute(_CREATE_QUOTE_SQL)
            cursor.execute(_CREATE_ASK_SCENE_SQL)
            cursor.execute(_CREATE_ASK_TOPIC_SQL)
            cursor.execute(_CREATE_ASK_ANSWER_SQL)
            cursor.execute(_CREATE_ELECTRICITY_TABLE_SQL)
            cursor.execute(_CREATE_WISH_TABLE_SQL)
            cursor.execute(_CREATE_REDEMPTION_PERIOD_SQL)
            cursor.execute(_CREATE_REDEMPTION_INJECT_SQL)
            cursor.execute(_CREATE_REDEMPTION_RULE_SQL)
            cursor.execute(_CREATE_REDEMPTION_SNAPSHOT_SQL)
            cursor.execute(_CREATE_ACTIVITY_GROUP_SQL)
            cursor.execute(_CREATE_TASK_META_SQL)
            cursor.execute(_CREATE_LIABILITY_TABLE_SQL)
            cursor.execute(_CREATE_RECEIVABLE_TABLE_SQL)
            cursor.execute(_CREATE_CASHFLOW_TABLE_SQL)
            cursor.execute(_CREATE_ASSET_ACCOUNT_SQL)
            cursor.execute(_CREATE_ASSET_SNAPSHOT_SQL)
            cursor.execute(_CREATE_ASSET_SNAPSHOT_ITEM_SQL)
            cursor.execute(_CREATE_CLASSIFY_RULE_SQL)
            # 生存资源盘点（v3.59.0）：顺序不能改 —— item 的外键指向 unit
            cursor.execute(_CREATE_SURVIVAL_CATEGORY_SQL)
            cursor.execute(_CREATE_SURVIVAL_UNIT_SQL)
            cursor.execute(_CREATE_SURVIVAL_ITEM_SQL)
            cursor.execute(_CREATE_SURVIVAL_RECIPE_SQL)
            cursor.execute(_CREATE_SURVIVAL_RECIPE_LINE_SQL)
            # 快照两张表：明细有外键指向快照头与类别，顺序不能反
            cursor.execute(_CREATE_SURVIVAL_SNAPSHOT_SQL)
            cursor.execute(_CREATE_SURVIVAL_SNAPSHOT_CATEGORY_SQL)
            # 实盘盘点（v3.59.3）：先给 item 补上 0021 的新列，再建盘点两张表 ——
            # 明细表的 item_id 外键指向 item，先补列读起来顺序更清楚
            _patch_survival_item_columns(cursor)
            cursor.execute(_CREATE_SURVIVAL_STOCKTAKE_SQL)
            cursor.execute(_CREATE_SURVIVAL_STOCKTAKE_LINE_SQL)
            # 必需品基准清单（v3.59.7）：外键指向 category，故排在类别之后
            cursor.execute(_CREATE_SURVIVAL_ESSENTIAL_SQL)
            # 必需品 ↔ 物品 中间表（v3.59.12）：两个外键分别指向上面两张表，
            # 必须排在两者**都建好之后**，否则建表直接失败
            cursor.execute(_CREATE_SURVIVAL_ESSENTIAL_ITEMS_SQL)
            # 组合（v3.59.13）：外键分别指向 category / item / unit / recipe，
            # 故排在它们**全部建好之后**；组合行最后建（它的外键指向组合与配方）
            cursor.execute(_CREATE_SURVIVAL_COMBO_SQL)
            cursor.execute(_CREATE_SURVIVAL_COMBO_ITEM_SQL)
            cursor.execute(_CREATE_SURVIVAL_RECIPE_COMBO_LINE_SQL)
            # 物件资产（v3.60.0）：物件表的外键指向类别表，故类别必须先建
            cursor.execute(_CREATE_PROPERTY_CATEGORY_SQL)
            cursor.execute(_CREATE_PROPERTY_SQL)
            # 库存流水（v3.60.18 · P0）：外键指向 `wealth_survival_item`，
            # 故排在它之后（本文件最末尾，天然满足）
            cursor.execute(_CREATE_SURVIVAL_FLOW_SQL)
