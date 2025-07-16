-- MySQL配置修复脚本
-- 解决 "MySQL server has gone away" 错误

-- 1. 设置更大的数据包大小（临时，重启后失效）
SET GLOBAL max_allowed_packet = 134217728;  -- 128MB
SET SESSION max_allowed_packet = 134217728; -- 128MB

-- 2. 设置连接超时时间
SET GLOBAL wait_timeout = 28800;           -- 8小时
SET GLOBAL interactive_timeout = 28800;    -- 8小时

-- 3. 设置网络超时
SET GLOBAL net_read_timeout = 600;         -- 10分钟
SET GLOBAL net_write_timeout = 600;        -- 10分钟

-- 4. 检查当前设置
SHOW VARIABLES LIKE 'max_allowed_packet';
SHOW VARIABLES LIKE 'wait_timeout';
SHOW VARIABLES LIKE 'interactive_timeout';
SHOW VARIABLES LIKE 'net_read_timeout';
SHOW VARIABLES LIKE 'net_write_timeout';

-- 5. 永久修改（需要在my.cnf或my.ini中添加）
-- [mysqld]
-- max_allowed_packet = 128M
-- wait_timeout = 28800
-- interactive_timeout = 28800
-- net_read_timeout = 600
-- net_write_timeout = 600 