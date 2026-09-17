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


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """在 Django 迁移建库之后，补齐原生 SQL 表"""
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
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
            cursor.execute(_CREATE_ASK_SCENE_SQL)
            cursor.execute(_CREATE_ASK_TOPIC_SQL)
            cursor.execute(_CREATE_ASK_ANSWER_SQL)
            cursor.execute(_CREATE_WISH_TABLE_SQL)
            cursor.execute(_CREATE_REDEMPTION_PERIOD_SQL)
            cursor.execute(_CREATE_REDEMPTION_INJECT_SQL)
            cursor.execute(_CREATE_REDEMPTION_RULE_SQL)
            cursor.execute(_CREATE_REDEMPTION_SNAPSHOT_SQL)
            cursor.execute(_CREATE_ACTIVITY_GROUP_SQL)
            cursor.execute(_CREATE_TASK_META_SQL)
