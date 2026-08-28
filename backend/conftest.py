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
