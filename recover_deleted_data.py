#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 binlog 文件中恢复指定时间范围内被删除和更新的数据
- 将 DELETE 操作转换为 INSERT 操作并执行（恢复被删除的数据）
- 将 UPDATE 操作转换为撤销语句并执行（将数据恢复到更新前的状态）
"""

import os
import sys
import subprocess
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pymysql

def get_db_config():
    """
    从 Django 配置中获取数据库配置
    如果无法从 Django 获取,则尝试从 env.yml 读取
    """
    # 方法1: 尝试从 Django 配置读取
    try:
        # 设置 Django 环境
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dj.settings')
        import django
        django.setup()
        
        from django.conf import settings
        db_config = settings.DATABASES['default']
        
        return {
            'HOST': db_config['HOST'],
            'PORT': db_config.get('PORT', 3306),
            'USER': db_config['USER'],
            'PASSWORD': db_config['PASSWORD'],
            'NAME': db_config['NAME'],
        }
    except Exception:
        pass
    
    # 方法2: 尝试从 env.yml 读取
    try:
        import yaml
        base_dir = os.path.dirname(os.path.abspath(__file__))
        env_file = os.path.join(base_dir, 'env.yml')
        
        if os.path.exists(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            db_configs = config.get('DATABASES', {})
            use_db = db_configs.get('use', 'dj')
            db_config = db_configs.get(use_db, {}).get('default', {})
            
            if db_config:
                return {
                    'HOST': db_config.get('HOST', 'localhost'),
                    'PORT': db_config.get('PORT', 3306),
                    'USER': db_config.get('USER', 'root'),
                    'PASSWORD': db_config.get('PASSWORD', ''),
                    'NAME': db_config.get('NAME', ''),
                }
    except Exception:
        pass
    
    # 方法3: 从环境变量读取
    return {
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': int(os.environ.get('DB_PORT', 3306)),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'NAME': os.environ.get('DB_NAME', ''),
    }

def parse_binlog_time(binlog_file: str, start_time: str, end_time: str, output_file: Optional[str] = None) -> str:
    """
    使用 mysqlbinlog 解析 binlog 文件，提取指定时间范围内的内容
    返回解析后的 SQL 文本
    """
    print(f"正在解析 binlog 文件: {binlog_file}")
    print(f"时间范围: {start_time} 到 {end_time}")
    
    # 使用 mysqlbinlog 解析 binlog，使用 ROW 格式以便提取详细数据
    cmd = [
        'mysqlbinlog',
        '--no-defaults',
        '--base64-output=DECODE-ROWS',
        '-v',  # verbose 模式，显示详细的 SQL 语句
        f'--start-datetime={start_time}',
        f'--stop-datetime={end_time}',
        binlog_file
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode != 0:
            print(f"警告: mysqlbinlog 返回错误码 {result.returncode}")
            print(f"错误信息: {result.stderr}")
            if not result.stdout:
                raise Exception(f"无法解析 binlog 文件: {result.stderr}")
        
        output = result.stdout
        
        # 如果指定了输出文件，保存到文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"已保存解析结果到: {output_file}")
        
        return output
    except FileNotFoundError:
        raise Exception("未找到 mysqlbinlog 命令，请确保 MySQL 客户端工具已安装并在 PATH 中")
    except Exception as e:
        raise Exception(f"解析 binlog 文件时出错: {str(e)}")


def extract_delete_operations(binlog_content: str) -> List[Dict]:
    """
    从 binlog 解析内容中提取 DELETE 操作
    返回包含表名和数据的列表
    """
    delete_operations = []
    lines = binlog_content.split('\n')
    
    current_delete = None
    in_delete_block = False
    table_name = None
    database_name = None
    table_id = None
    timestamp = None
    row_data = []
    current_row = {}
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 提取时间戳
        time_match = re.search(r'#(\d{6}\s+\d{2}:\d{2}:\d{2})', line)
        if time_match:
            timestamp = time_match.group(1)
        
        # 检测 Table_map 事件（DELETE 操作前会有表映射）
        table_map_match = re.search(r'Table_map:\s+`?([\w]+)`?\.`?([\w]+)`?\s+mapped to number\s+(\d+)', line)
        if table_map_match:
            # 如果当前正在处理 DELETE 块，先保存它
            if in_delete_block and current_delete:
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
                if current_delete:
                    if current_delete['rows']:
                        delete_operations.append(current_delete)
                    else:
                        print(f"警告: DELETE 操作没有数据行 - {current_delete.get('database')}.{current_delete.get('table')}")
                current_delete = None
                in_delete_block = False
            
            database_name = table_map_match.group(1)
            table_name = table_map_match.group(2)
            table_id = table_map_match.group(3)
        
        # 检测 Delete_rows 事件（可能有多种格式）
        if 'Delete_rows:' in line or 'Delete_rows' in line:
            # 确保有表信息（Table_map 应该在 Delete_rows 之前）
            if table_name and database_name:
                in_delete_block = True
                current_delete = {
                    'database': database_name,
                    'table': table_name,
                    'table_id': table_id,
                    'timestamp': timestamp,
                    'rows': []
                }
                current_row = {}
                i += 1
                continue
            else:
                # 如果没有表信息，可能是格式问题，跳过这个 DELETE 块
                print(f"警告: 检测到 Delete_rows 但没有表信息 (table_name={table_name}, database_name={database_name})")
        
        # 在 DELETE 块中提取数据
        if in_delete_block and current_delete:
            # 匹配 WHERE 条件中的值 (@1=value, @2=value 等)
            # 格式: ###   @1=value1
            value_match = re.search(r'###\s+@(\d+)=(.*)', line)
            if value_match:
                col_index = int(value_match.group(1))
                value_str = value_match.group(2).strip()
                
                # 处理值
                if value_str == 'NULL':
                    value = None
                elif value_str.startswith("'") and value_str.endswith("'"):
                    # 字符串值，移除引号并处理转义
                    value = value_str[1:-1].replace("\\'", "'").replace("\\\\", "\\")
                elif value_str.startswith("'") and not value_str.endswith("'"):
                    # 多行字符串值 - 需要继续读取直到找到结束引号
                    value = value_str[1:]  # 去掉开始的引号
                    i += 1
                    quote_closed = False
                    while i < len(lines):
                        next_line = lines[i]
                        # 检查是否包含结束引号
                        if "'" in next_line:
                            # 找到结束引号的位置
                            end_quote_idx = next_line.find("'")
                            value += next_line[:end_quote_idx]
                            quote_closed = True
                            break
                        else:
                            # 继续读取，添加换行符
                            value += '\n' + next_line
                        i += 1
                    
                    if not quote_closed:
                        # 如果没有找到结束引号，可能格式有问题，但继续处理
                        pass
                    
                    value = value.replace("\\'", "'").replace("\\\\", "\\")
                else:
                    # 数字或其他值
                    value_str_clean = value_str.strip()
                    if value_str_clean == 'NULL':
                        value = None
                    else:
                        try:
                            # 尝试解析为数字
                            if '.' in value_str_clean:
                                value = float(value_str_clean)
                            else:
                                value = int(value_str_clean)
                        except ValueError:
                            value = value_str_clean
                
                current_row[col_index] = value
            elif line.strip().startswith('### DELETE FROM'):
                # DELETE 语句开始，保存上一行数据（如果有）
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
                # 开始新的一行，等待 WHERE 子句的数据
                # 注意：这里不清空 current_row，因为数据会在 WHERE 之后
            elif line.strip() == '### WHERE':
                # WHERE 子句开始，准备读取数据
                # 如果之前有数据（不应该有），先保存
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
                # WHERE 之后会跟着 @N=value 格式的数据
            elif line.strip() == '':
                # 空行：可能是行之间的分隔
                # 如果当前行有数据，可能是行的结束，保存它
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
            elif line.strip().startswith('###') and not line.strip().startswith('### DELETE') and not line.strip().startswith('### WHERE') and not re.search(r'###\s+@', line):
                # 其他 ### 开头的行（但不是 DELETE、WHERE 或 @ 值）
                # 可能是新的一行数据开始，保存当前行
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
            
            # 检测 DELETE 块结束
            # 注意：需要检查是否是新的 Table_map 或其他事件
            # 检查是否是新的 Table_map（但不在 DELETE 块内）
            if 'Table_map:' in line and not in_delete_block:
                # 这是新的表映射，但不在 DELETE 块中，忽略
                pass
            elif (line.strip().startswith('# at ') and 
                'Delete_rows' not in line and 
                'Table_map' not in line and
                '###' not in line and
                'BINLOG' not in line):
                # 新的位置标记，可能是下一个事件，结束当前 DELETE 块
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
                if current_delete and current_delete['rows']:
                    delete_operations.append(current_delete)
                current_delete = None
                in_delete_block = False
                current_row = {}
                # 不清空 table_name 等，因为可能被下一个 Table_map 使用
            elif 'Write_rows' in line or 'Update_rows' in line:
                # 遇到其他类型的行操作，结束当前 DELETE 块
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
                if current_delete and current_delete['rows']:
                    delete_operations.append(current_delete)
                current_delete = None
                in_delete_block = False
                current_row = {}
                # 不清空 table_name 等
            elif 'COMMIT' in line or line.strip().startswith('COMMIT'):
                # 事务提交，结束当前 DELETE 块
                if current_row:
                    current_delete['rows'].append(current_row)
                    current_row = {}
                if current_delete and current_delete['rows']:
                    delete_operations.append(current_delete)
                current_delete = None
                in_delete_block = False
                current_row = {}
                # 不清空 table_name 等
            elif line.strip().startswith('BINLOG'):
                # BINLOG 块开始，这通常意味着 DELETE 块的数据部分结束
                # 但可能还有更多行，所以不立即结束
                # 只在遇到明确的结束标记时才结束
                pass
        
        i += 1
    
    # 处理最后一个 DELETE 操作
    if in_delete_block and current_delete:
        if current_row:
            current_delete['rows'].append(current_row)
        if current_delete:
            if current_delete['rows']:
                delete_operations.append(current_delete)
            else:
                print(f"警告: 最后一个 DELETE 操作没有数据行 - {current_delete.get('database')}.{current_delete.get('table')}")
    
    return delete_operations


def extract_update_operations(binlog_content: str) -> List[Dict]:
    """
    从 binlog 解析内容中提取 UPDATE 操作
    返回包含表名和更新前后数据的列表
    """
    update_operations = []
    lines = binlog_content.split('\n')
    
    current_update = None
    in_update_block = False
    table_name = None
    database_name = None
    table_id = None
    timestamp = None
    current_row = {}
    in_where_clause = False
    in_set_clause = False
    where_values = {}  # 更新前的值（用于 WHERE 条件）
    set_values = {}    # 更新后的值（用于 SET）
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 提取时间戳
        time_match = re.search(r'#(\d{6}\s+\d{2}:\d{2}:\d{2})', line)
        if time_match:
            timestamp = time_match.group(1)
        
        # 检测 Table_map 事件
        table_map_match = re.search(r'Table_map:\s+`?([\w]+)`?\.`?([\w]+)`?\s+mapped to number\s+(\d+)', line)
        if table_map_match:
            # 如果当前正在处理 UPDATE 块，先保存它
            if in_update_block and current_update:
                if where_values and set_values:
                    current_update['rows'].append({
                        'where': where_values.copy(),
                        'set': set_values.copy()
                    })
                if current_update and current_update['rows']:
                    update_operations.append(current_update)
                current_update = None
                in_update_block = False
                where_values = {}
                set_values = {}
            
            database_name = table_map_match.group(1)
            table_name = table_map_match.group(2)
            table_id = table_map_match.group(3)
        
        # 检测 Update_rows 事件
        if 'Update_rows:' in line or 'Update_rows' in line:
            if table_name and database_name:
                in_update_block = True
                in_where_clause = False
                in_set_clause = False
                current_update = {
                    'database': database_name,
                    'table': table_name,
                    'table_id': table_id,
                    'timestamp': timestamp,
                    'rows': []
                }
                where_values = {}
                set_values = {}
                i += 1
                continue
        
        # 在 UPDATE 块中提取数据
        if in_update_block and current_update:
            # 检测 UPDATE 语句开始
            if line.strip().startswith('### UPDATE'):
                in_where_clause = False
                in_set_clause = False
                # 如果之前有数据，先保存
                if where_values and set_values:
                    current_update['rows'].append({
                        'where': where_values.copy(),
                        'set': set_values.copy()
                    })
                    where_values = {}
                    set_values = {}
            
            # 检测 WHERE 子句
            elif line.strip() == '### WHERE':
                in_where_clause = True
                in_set_clause = False
            
            # 检测 SET 子句
            elif line.strip() == '### SET':
                in_where_clause = False
                in_set_clause = True
            
            # 提取值（@N=value 格式）
            value_match = re.search(r'###\s+@(\d+)=(.*)', line)
            if value_match:
                col_index = int(value_match.group(1))
                value_str = value_match.group(2).strip()
                
                # 处理值
                if value_str == 'NULL':
                    value = None
                elif value_str.startswith("'") and value_str.endswith("'"):
                    value = value_str[1:-1].replace("\\'", "'").replace("\\\\", "\\")
                elif value_str.startswith("'") and not value_str.endswith("'"):
                    value = value_str[1:]
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if "'" in next_line:
                            end_quote_idx = next_line.find("'")
                            value += next_line[:end_quote_idx]
                            break
                        value += '\n' + next_line
                        i += 1
                    value = value.replace("\\'", "'").replace("\\\\", "\\")
                else:
                    value_str_clean = value_str.strip()
                    if value_str_clean == 'NULL':
                        value = None
                    else:
                        try:
                            if '.' in value_str_clean:
                                value = float(value_str_clean)
                            else:
                                value = int(value_str_clean)
                        except ValueError:
                            value = value_str_clean
                
                # 根据是在 WHERE 还是 SET 子句中，存储到不同的字典
                if in_where_clause:
                    where_values[col_index] = value
                elif in_set_clause:
                    set_values[col_index] = value
            
            # 检测 UPDATE 块结束
            elif (line.strip().startswith('# at ') and 
                'Update_rows' not in line and 
                'Table_map' not in line and
                '###' not in line and
                'BINLOG' not in line):
                # 保存当前 UPDATE 操作
                if where_values and set_values:
                    current_update['rows'].append({
                        'where': where_values.copy(),
                        'set': set_values.copy()
                    })
                if current_update and current_update['rows']:
                    update_operations.append(current_update)
                current_update = None
                in_update_block = False
                where_values = {}
                set_values = {}
            elif 'Delete_rows' in line or 'Write_rows' in line:
                # 遇到其他类型的行操作，结束当前 UPDATE 块
                if where_values and set_values:
                    current_update['rows'].append({
                        'where': where_values.copy(),
                        'set': set_values.copy()
                    })
                if current_update and current_update['rows']:
                    update_operations.append(current_update)
                current_update = None
                in_update_block = False
                where_values = {}
                set_values = {}
            elif 'COMMIT' in line or line.strip().startswith('COMMIT'):
                # 事务提交，结束当前 UPDATE 块
                if where_values and set_values:
                    current_update['rows'].append({
                        'where': where_values.copy(),
                        'set': set_values.copy()
                    })
                if current_update and current_update['rows']:
                    update_operations.append(current_update)
                current_update = None
                in_update_block = False
                where_values = {}
                set_values = {}
        
        i += 1
    
    # 处理最后一个 UPDATE 操作
    if in_update_block and current_update:
        if where_values and set_values:
            current_update['rows'].append({
                'where': where_values.copy(),
                'set': set_values.copy()
            })
        if current_update and current_update['rows']:
            update_operations.append(current_update)
    
    return update_operations


def get_table_columns(db_config: Dict, database: str, table: str) -> Tuple[List[str], Dict[str, str]]:
    """
    获取表的列名列表（按顺序）和列类型信息
    返回: (列名列表, 列类型字典)
    """
    try:
        conn = pymysql.connect(
            host=db_config['HOST'],
            port=db_config.get('PORT', 3306),
            user=db_config['USER'],
            password=db_config['PASSWORD'],
            database=database,
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        columns_info = cursor.fetchall()
        
        columns = [row[0] for row in columns_info]
        column_types = {}
        for row in columns_info:
            col_name = row[0]
            col_type = row[1].upper()
            # 提取基础类型（去除长度等信息）
            if 'INT' in col_type:
                column_types[col_name] = 'INT'
            elif 'DECIMAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
                column_types[col_name] = 'NUMERIC'
            elif 'DATE' in col_type:
                column_types[col_name] = 'DATE'
            elif 'TIME' in col_type:
                column_types[col_name] = 'TIME'
            elif 'DATETIME' in col_type or 'TIMESTAMP' in col_type:
                column_types[col_name] = 'DATETIME'
            elif 'TEXT' in col_type or 'BLOB' in col_type:
                column_types[col_name] = 'TEXT'
            else:
                column_types[col_name] = 'STRING'
        
        cursor.close()
        conn.close()
        
        return columns, column_types
    except Exception as e:
        print(f"警告: 无法获取表 {database}.{table} 的列信息: {str(e)}")
        return [], {}


def format_value_for_sql(value, col_type: str = 'STRING', col_name: str = '') -> str:
    """
    根据列类型格式化值用于 SQL 语句
    """
    if value is None:
        return 'NULL'
    
    # 处理日期格式错误（如 2025:09:29 -> 2025-09-29）
    if isinstance(value, str):
        # 修复日期格式错误
        if ':' in value and len(value) == 10 and value.count(':') == 2:
            # 可能是日期格式错误，尝试修复
            try:
                # 检查是否是 YYYY:MM:DD 格式
                parts = value.split(':')
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    if len(parts[0]) == 4:  # 年份
                        value = f"{parts[0]}-{parts[1]}-{parts[2]}"
            except:
                pass
    
    # 根据列类型格式化
    if col_type == 'INT':
        if isinstance(value, (int, float)):
            return str(int(value))
        elif isinstance(value, str) and value.isdigit():
            return value
        else:
            return 'NULL'
    elif col_type == 'NUMERIC':
        if isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            try:
                return str(float(value))
            except:
                return 'NULL'
        else:
            return 'NULL'
    elif col_type in ('DATE', 'DATETIME', 'TIME'):
        if isinstance(value, str):
            # 确保日期格式正确
            value = value.replace(':', '-', 2) if value.count(':') >= 2 and '-' not in value else value
            # 转义字符串
            escaped_value = value.replace('\\', '\\\\').replace("'", "\\'")
            return f"'{escaped_value}'"
        else:
            return 'NULL'
    else:
        # 字符串类型
        if isinstance(value, str):
            # 使用 pymysql 的转义函数更安全
            try:
                import pymysql
                escaped_value = pymysql.escape_string(value)
                return f"'{escaped_value}'"
            except:
                # 手动转义
                escaped_value = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r').replace('\x00', '\\0')
                return f"'{escaped_value}'"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            # 其他类型转换为字符串
            escaped_value = str(value).replace('\\', '\\\\').replace("'", "\\'")
            return f"'{escaped_value}'"


def convert_delete_to_insert(delete_ops: List[Dict], db_config: Dict, target_database: Optional[str] = None) -> List[str]:
    """
    将 DELETE 操作转换为 INSERT 语句
    """
    insert_statements = []
    table_columns_cache = {}  # 缓存表的列信息
    
    for delete_op in delete_ops:
        database = delete_op.get('database')
        table = delete_op.get('table')
        rows = delete_op.get('rows', [])
        
        if not table or not rows:
            continue
        
        # 如果指定了目标数据库，使用目标数据库；否则使用原始数据库
        target_db = target_database or database
        
        # 获取表的列信息（从目标数据库获取）
        cache_key = f"{target_db}.{table}" if target_db else table
        if cache_key not in table_columns_cache:
            columns, column_types = get_table_columns(db_config, target_db or db_config.get('NAME', ''), table)
            table_columns_cache[cache_key] = (columns, column_types)
        else:
            columns, column_types = table_columns_cache[cache_key]
        
        if not columns:
            print(f"警告: 无法获取表 {cache_key} 的列信息，跳过该 DELETE 操作")
            continue
        
        # 构建表引用（使用目标数据库）
        table_ref = f"`{target_db}`.`{table}`" if target_db else f"`{table}`"
        
        # 为每一行生成 INSERT 语句
        for row_values in rows:
            if not row_values:
                continue
            
            # 构建 VALUES 列表（按列顺序）
            values_list = []
            max_col_index = max(row_values.keys()) if row_values else 0
            
            # 根据列索引填充值
            for col_index in range(1, max_col_index + 1):
                if col_index <= len(columns):
                    col_name = columns[col_index - 1]
                    col_type = column_types.get(col_name, 'STRING')
                    
                    if col_index in row_values:
                        value = row_values[col_index]
                        formatted_value = format_value_for_sql(value, col_type, col_name)
                        values_list.append(formatted_value)
                    else:
                        # 如果某个列索引缺失，使用 NULL
                        values_list.append('NULL')
                else:
                    # 列索引超出范围，跳过
                    pass
            
            # 如果列数不匹配，补充缺失的值
            if len(values_list) < len(columns):
                # 补充缺失的值（可能是自增列或其他列）
                while len(values_list) < len(columns):
                    values_list.append('NULL')
            elif len(values_list) > len(columns):
                # 截断多余的值
                print(f"警告: 表 {cache_key} 的值数量 ({len(values_list)}) 多于列数 ({len(columns)})，将截断")
                values_list = values_list[:len(columns)]
            
            if not values_list:
                continue
            
            values_str = ', '.join(values_list)
            
            # 使用 INSERT IGNORE 避免主键冲突
            insert_sql = f"INSERT IGNORE INTO {table_ref} VALUES ({values_str});"
            insert_statements.append(insert_sql)
    
    return insert_statements


def get_primary_keys(db_config: Dict, database: str, table: str) -> List[str]:
    """
    获取表的主键列名列表
    """
    try:
        conn = pymysql.connect(
            host=db_config['HOST'],
            port=db_config.get('PORT', 3306),
            user=db_config['USER'],
            password=db_config['PASSWORD'],
            database=database,
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        cursor.execute(f"SHOW KEYS FROM `{table}` WHERE Key_name = 'PRIMARY'")
        primary_keys = cursor.fetchall()
        
        # SHOW KEYS 返回的列顺序：
        # 0: Table, 1: Non_unique, 2: Key_name, 3: Seq_in_index, 4: Column_name, ...
        pk_columns = []
        if primary_keys:
            # 按 Seq_in_index 排序（索引3）
            sorted_keys = sorted(primary_keys, key=lambda x: x[3])  # Seq_in_index 在第4列（索引3）
            pk_columns = [row[4] for row in sorted_keys]  # Column_name 在第5列（索引4）
        
        cursor.close()
        conn.close()
        
        return pk_columns
    except Exception as e:
        print(f"警告: 无法获取表 {database}.{table} 的主键信息: {str(e)}")
        return []


def convert_update_to_revert(update_ops: List[Dict], db_config: Dict, target_database: Optional[str] = None) -> List[str]:
    """
    将 UPDATE 操作转换为撤销 UPDATE 的语句
    撤销 UPDATE 意味着将更新后的值改回更新前的值
    """
    revert_statements = []
    table_columns_cache = {}  # 缓存表的列信息
    table_pk_cache = {}  # 缓存表的主键信息
    
    for update_op in update_ops:
        database = update_op.get('database')
        table = update_op.get('table')
        rows = update_op.get('rows', [])
        
        if not table or not rows:
            continue
        
        # 如果指定了目标数据库，使用目标数据库；否则使用原始数据库
        target_db = target_database or database
        
        # 获取表的列信息
        cache_key = f"{target_db}.{table}" if target_db else table
        if cache_key not in table_columns_cache:
            columns, column_types = get_table_columns(db_config, target_db or db_config.get('NAME', ''), table)
            table_columns_cache[cache_key] = (columns, column_types)
        else:
            columns, column_types = table_columns_cache[cache_key]
        
        if not columns:
            print(f"警告: 无法获取表 {cache_key} 的列信息，跳过该 UPDATE 操作")
            continue
        
        # 获取主键信息
        if cache_key not in table_pk_cache:
            pk_columns = get_primary_keys(db_config, target_db or db_config.get('NAME', ''), table)
            table_pk_cache[cache_key] = pk_columns
        else:
            pk_columns = table_pk_cache[cache_key]
        
        # 构建表引用
        table_ref = f"`{target_db}`.`{table}`" if target_db else f"`{table}`"
        
        # 为每一行生成撤销 UPDATE 语句
        for row_data in rows:
            where_values = row_data.get('where', {})  # 更新前的值（用于恢复）
            set_values = row_data.get('set', {})       # 更新后的值
            
            if not where_values or not set_values:
                continue
            
            # 优先使用主键构建 WHERE 条件
            where_conditions = []
            if pk_columns:
                # 使用主键定位记录（更准确）
                for pk_col in pk_columns:
                    # 找到主键列在 columns 中的索引
                    try:
                        pk_col_index = columns.index(pk_col) + 1  # 列索引从1开始
                        # 优先使用更新后的值（set_values），如果没有则使用更新前的值（where_values）
                        if pk_col_index in set_values:
                            value = set_values[pk_col_index]
                        elif pk_col_index in where_values:
                            value = where_values[pk_col_index]
                        else:
                            continue
                        
                        col_type = column_types.get(pk_col, 'STRING')
                        formatted_value = format_value_for_sql(value, col_type, pk_col)
                        where_conditions.append(f"`{pk_col}` = {formatted_value}")
                    except ValueError:
                        # 主键列不在列列表中，跳过
                        continue
            
            # 如果没有主键或主键条件不足，使用所有更新后的值作为 WHERE 条件
            if not where_conditions:
                for col_index in sorted(set_values.keys()):
                    if col_index <= len(columns):
                        col_name = columns[col_index - 1]
                        col_type = column_types.get(col_name, 'STRING')
                        value = set_values[col_index]
                        formatted_value = format_value_for_sql(value, col_type, col_name)
                        where_conditions.append(f"`{col_name}` = {formatted_value}")
            
            if not where_conditions:
                print(f"警告: 无法为表 {cache_key} 构建 WHERE 条件，跳过该 UPDATE 撤销")
                continue
            
            # 构建 SET 子句（使用更新前的值来恢复数据）
            set_clauses = []
            for col_index in sorted(where_values.keys()):
                if col_index <= len(columns):
                    col_name = columns[col_index - 1]
                    col_type = column_types.get(col_name, 'STRING')
                    value = where_values[col_index]
                    formatted_value = format_value_for_sql(value, col_type, col_name)
                    set_clauses.append(f"`{col_name}` = {formatted_value}")
            
            if not set_clauses:
                continue
            
            where_clause = ' AND '.join(where_conditions)
            set_clause = ', '.join(set_clauses)
            
            # 生成撤销 UPDATE 语句
            revert_sql = f"UPDATE {table_ref} SET {set_clause} WHERE {where_clause};"
            revert_statements.append(revert_sql)
    
    return revert_statements


def execute_insert_statements(db_config: Dict, insert_statements: List[str], revert_statements: List[str] = None, dry_run: bool = False, use_replace: bool = False, reverse: bool = False, target_database: Optional[str] = None) -> None:
    """
    执行 INSERT 和 UPDATE 撤销语句
    """
    if revert_statements is None:
        revert_statements = []
    
    if not insert_statements and not revert_statements:
        print("没有需要恢复的数据")
        return
    
    # 确保执行顺序：先执行所有 INSERT（恢复删除的数据），再执行所有 UPDATE 撤销
    # 如果使用 --reverse，只在各自类型内部倒序，但整体顺序仍然是：先所有 INSERT，后所有 UPDATE
    if reverse:
        # 倒序模式：各自内部倒序，但保持 INSERT 在前，UPDATE 在后
        insert_list = list(reversed(insert_statements)) if insert_statements else []
        revert_list = list(reversed(revert_statements)) if revert_statements else []
    else:
        # 正常模式：保持原始顺序
        insert_list = insert_statements if insert_statements else []
        revert_list = revert_statements if revert_statements else []
    
    # 合并：先所有 INSERT，后所有 UPDATE
    all_statements = []
    if insert_list:
        all_statements.extend(insert_list)
    if revert_list:
        all_statements.extend(revert_list)
    
    if not all_statements:
        print("没有需要恢复的数据")
        return
    
    # 如果指定了目标数据库，更新配置
    if target_database:
        db_config = db_config.copy()
        db_config['NAME'] = target_database
        print(f"\n目标数据库: {target_database}")
    
    # 显示执行顺序信息
    print(f"\n执行顺序: 先恢复删除的数据（INSERT），再撤销更新操作（UPDATE）")
    if reverse:
        print(f"（使用倒序模式：各自内部倒序）")
    print(f"\n找到 {len(all_statements)} 条需要恢复的记录")
    if insert_list:
        print(f"  - INSERT 语句（恢复删除）: {len(insert_list)} 条")
    if revert_list:
        print(f"  - UPDATE 撤销语句（撤销更新）: {len(revert_list)} 条")
    
    if dry_run:
        print("\n=== 预览模式，不会实际执行 ===")
        print(f"\n数据库连接信息:")
        print(f"  主机: {db_config['HOST']}:{db_config.get('PORT', 3306)}")
        print(f"  数据库: {db_config['NAME']}")
        print(f"  用户: {db_config['USER']}")
        
        # 统计涉及的数据库和表
        db_tables = {}
        for sql in all_statements:
            # 匹配 INSERT 语句: INSERT INTO `db`.`table`
            table_match = re.search(r'INTO\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
            if not table_match:
                # 匹配 UPDATE 语句: UPDATE `db`.`table`
                table_match = re.search(r'UPDATE\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
            if table_match:
                if len(table_match.groups()) == 2:
                    db_name, table_name = table_match.groups()
                    if db_name not in db_tables:
                        db_tables[db_name] = set()
                    db_tables[db_name].add(table_name)
                else:
                    table_name = table_match.group(1)
                    db_name = db_config['NAME']
                    if db_name not in db_tables:
                        db_tables[db_name] = set()
                    db_tables[db_name].add(table_name)
        
        if db_tables:
            print(f"\n涉及的数据库和表:")
            for db_name in sorted(db_tables.keys()):
                print(f"  {db_name}:")
                for table_name in sorted(db_tables[db_name]):
                    print(f"    - {table_name}")
        
        if reverse:
            print("\n（显示的是倒序后的前10条）")
        print("\n执行顺序说明:")
        print("  1. 先执行所有 INSERT 语句（恢复被删除的数据）")
        print("  2. 再执行所有 UPDATE 撤销语句（撤销更新操作）")
        print("\n前10条恢复语句预览:")
        for i, sql in enumerate(all_statements[:10], 1):  # 只显示前10条
            sql_type = "INSERT" if sql.strip().upper().startswith('INSERT') else "UPDATE"
            print(f"{i}. [{sql_type}] {sql}")
        if len(all_statements) > 10:
            print(f"... 还有 {len(all_statements) - 10} 条记录")
        return
    
    # 询问确认
    insert_type = "REPLACE INTO" if use_replace else "INSERT IGNORE INTO"
    print(f"\n将使用 {insert_type} 执行恢复")
    print(f"\n数据库连接信息:")
    print(f"  主机: {db_config['HOST']}:{db_config.get('PORT', 3306)}")
    print(f"  数据库: {db_config['NAME']}")
    print(f"  用户: {db_config['USER']}")
    
    if not use_replace:
        print("\n注意: INSERT IGNORE 会跳过已存在的记录（主键冲突时不会插入）")
        print("如果数据已存在，将不会插入。如需替换已存在的记录，请使用 --replace 参数")
    
    response = input(f"\n确定要恢复 {len(all_statements)} 条记录到数据库 {db_config['NAME']} 吗？(yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("已取消恢复操作")
        return
    
    try:
        conn = pymysql.connect(
            host=db_config['HOST'],
            port=db_config.get('PORT', 3306),
            user=db_config['USER'],
            password=db_config['PASSWORD'],
            database=db_config['NAME'],
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        
        # 显示当前连接的数据库
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()[0]
        print(f"\n✓ 已连接到数据库: {current_db}")
        
        # 禁用外键约束和唯一性检查，提高插入速度并避免约束问题
        print("\n正在禁用外键约束和唯一性检查...")
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute("SET UNIQUE_CHECKS = 0")
            cursor.execute("SET AUTOCOMMIT = 0")  # 使用事务，提高性能
            print("✓ 外键约束和唯一性检查已禁用")
        except Exception as e:
            print(f"警告: 禁用约束时出错: {str(e)}")
            print("将继续执行，但可能会遇到约束错误")
        
        success_count = 0
        error_count = 0
        inserted_count = 0  # 实际插入的行数
        skipped_count = 0    # 跳过的行数（INSERT IGNORE 时主键冲突）
        
        # 统计每个数据库和表的插入情况
        table_stats = {}  # {database.table: {'inserted': 0, 'skipped': 0, 'errors': 0}}
        
        print("\n开始执行恢复...")
        print(f"目标数据库: {db_config['NAME']}")
        print("=" * 60)
        
        # 显示执行阶段
        if insert_list and revert_list:
            print(f"\n阶段 1: 恢复删除的数据（{len(insert_list)} 条 INSERT 语句）")
            print("-" * 60)
        elif insert_list:
            print(f"\n阶段 1: 恢复删除的数据（{len(insert_list)} 条 INSERT 语句）")
            print("-" * 60)
        
        statement_index = 0
        for i, sql in enumerate(all_statements, 1):
            statement_index += 1
            
            # 检测是否从 INSERT 阶段切换到 UPDATE 阶段
            if i == len(insert_list) + 1 and revert_list:
                print(f"\n阶段 2: 撤销更新操作（{len(revert_list)} 条 UPDATE 语句）")
                print("-" * 60)
                statement_index = 1  # 重置计数器
            try:
                # 如果使用 REPLACE，替换 INSERT IGNORE
                if use_replace:
                    sql = sql.replace('INSERT IGNORE INTO', 'REPLACE INTO')
                
                cursor.execute(sql)
                affected_rows = cursor.rowcount
                
                # 判断是 INSERT 还是 UPDATE 语句
                is_update = sql.strip().upper().startswith('UPDATE')
                
                # 提取表名用于统计
                table_match = re.search(r'INTO\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
                if not table_match:
                    table_match = re.search(r'UPDATE\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
                if table_match:
                    if len(table_match.groups()) == 2:
                        db_name, table_name = table_match.groups()
                        table_key = f"{db_name}.{table_name}"
                    else:
                        table_name = table_match.group(1)
                        table_key = f"{db_config['NAME']}.{table_name}"
                else:
                    table_key = "unknown"
                
                if table_key not in table_stats:
                    table_stats[table_key] = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
                
                if affected_rows > 0:
                    if is_update:
                        # UPDATE 语句
                        success_count += 1
                        table_stats[table_key]['updated'] += affected_rows
                        # 每10条 UPDATE 显示一次进度
                        if statement_index % 10 == 0 and i > len(insert_list):
                            print(f"  [UPDATE] 已更新 {statement_index}/{len(revert_list)} 条，影响 {affected_rows} 行")
                    else:
                        # INSERT 语句
                        inserted_count += affected_rows
                        success_count += 1
                        table_stats[table_key]['inserted'] += affected_rows
                else:
                    # INSERT IGNORE 时，如果主键冲突，affected_rows 为 0
                    # UPDATE 时，如果没有匹配的行，affected_rows 也为 0
                    skipped_count += 1
                    success_count += 1  # 执行成功，只是没有影响行
                    table_stats[table_key]['skipped'] += 1
                    if is_update:
                        # UPDATE 没有影响任何行，可能是 WHERE 条件不匹配
                        if statement_index <= 5 or statement_index % 50 == 0:  # 只显示前5条或每50条
                            print(f"  警告 [UPDATE #{statement_index}]: 没有匹配的行，WHERE 条件可能不正确")
                            print(f"    SQL: {sql[:200]}...")
                
                # 显示进度（每100条或每个阶段结束时）
                if i % 100 == 0:
                    current_phase = "INSERT" if i <= len(insert_list) else "UPDATE"
                    print(f"[{current_phase}] 已处理 {i}/{len(all_statements)} 条记录... (实际插入: {inserted_count}, 跳过: {skipped_count})")
                elif i == len(insert_list) and revert_list:
                    # INSERT 阶段完成
                    print(f"[INSERT] 阶段完成: 已处理 {len(insert_list)} 条 INSERT 语句 (实际插入: {inserted_count}, 跳过: {skipped_count})")
            except pymysql.Error as e:
                error_count += 1
                # 提取表名用于统计
                table_match = re.search(r'INTO\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
                if not table_match:
                    table_match = re.search(r'UPDATE\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
                if table_match:
                    if len(table_match.groups()) == 2:
                        db_name, table_name = table_match.groups()
                        table_key = f"{db_name}.{table_name}"
                    else:
                        table_name = table_match.group(1)
                        table_key = f"{db_config['NAME']}.{table_name}"
                else:
                    table_key = "unknown"
                
                if table_key not in table_stats:
                    table_stats[table_key] = {'inserted': 0, 'skipped': 0, 'errors': 0}
                table_stats[table_key]['errors'] += 1
                
                if e.args and len(e.args) >= 2:
                    error_code, error_msg = e.args[0], e.args[1]
                    print(f"MySQL 错误 (第 {i} 条) [{table_key}]: [{error_code}] {error_msg}")
                else:
                    print(f"MySQL 错误 (第 {i} 条) [{table_key}]: {str(e)}")
                print(f"SQL: {sql[:300]}...")
                # 继续执行，不中断
            except Exception as e:
                error_count += 1
                # 提取表名用于统计
                table_match = re.search(r'INTO\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
                if not table_match:
                    table_match = re.search(r'UPDATE\s+`?([\w]+)`?\.?`?([\w]+)`?', sql, re.IGNORECASE)
                if table_match:
                    if len(table_match.groups()) == 2:
                        db_name, table_name = table_match.groups()
                        table_key = f"{db_name}.{table_name}"
                    else:
                        table_name = table_match.group(1)
                        table_key = f"{db_config['NAME']}.{table_name}"
                else:
                    table_key = "unknown"
                
                if table_key not in table_stats:
                    table_stats[table_key] = {'inserted': 0, 'skipped': 0, 'errors': 0}
                table_stats[table_key]['errors'] += 1
                
                print(f"错误 (第 {i} 条) [{table_key}]: {type(e).__name__}: {str(e)}")
                print(f"SQL: {sql[:300]}...")
                # 继续执行，不中断
        
        # 提交事务
        try:
            conn.commit()
            print("\n✓ 事务已提交")
        except Exception as e:
            print(f"\n警告: 提交事务时出错: {str(e)}")
            try:
                conn.rollback()
                print("已回滚事务")
            except:
                pass
        
        # 重新启用外键约束和唯一性检查
        print("\n正在重新启用外键约束和唯一性检查...")
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            cursor.execute("SET UNIQUE_CHECKS = 1")
            cursor.execute("SET AUTOCOMMIT = 1")
            print("✓ 外键约束和唯一性检查已重新启用")
        except Exception as e:
            print(f"警告: 重新启用约束时出错: {str(e)}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print(f"恢复完成!")
        print("=" * 60)
        print(f"\n数据库: {db_config['NAME']}")
        print(f"主机: {db_config['HOST']}:{db_config.get('PORT', 3306)}")
        print(f"\n总体统计:")
        print(f"  执行成功: {success_count} 条")
        if insert_statements:
            print(f"  实际插入: {inserted_count} 条")
        if revert_statements:
            updated_count = sum(stats.get('updated', 0) for stats in table_stats.values())
            print(f"  实际更新: {updated_count} 条")
        if not use_replace:
            print(f"  跳过(已存在/无匹配): {skipped_count} 条")
        print(f"  执行失败: {error_count} 条")
        
        # 显示每个表的详细统计
        if table_stats:
            print(f"\n各表统计:")
            print("-" * 60)
            for table_key in sorted(table_stats.keys()):
                stats = table_stats[table_key]
                total = stats.get('inserted', 0) + stats.get('updated', 0) + stats.get('skipped', 0) + stats.get('errors', 0)
                print(f"  {table_key}:")
                if stats.get('inserted', 0) > 0:
                    print(f"    插入: {stats['inserted']} 条")
                if stats.get('updated', 0) > 0:
                    print(f"    更新: {stats['updated']} 条")
                if not use_replace and stats.get('skipped', 0) > 0:
                    print(f"    跳过: {stats['skipped']} 条")
                if stats.get('errors', 0) > 0:
                    print(f"    错误: {stats['errors']} 条")
                print(f"    总计: {total} 条")
        
        if inserted_count == 0 and skipped_count > 0:
            print("\n警告: 所有记录都被跳过了（可能因为主键已存在）")
            print("建议: 使用 --replace 参数来替换已存在的记录")
        
    except Exception as e:
        print(f"执行恢复时出错: {str(e)}")
        raise


def main():
    """
    主函数
    """
    if len(sys.argv) < 4:
        print("用法: python recover_deleted_data.py <binlog_file> <start_time> <end_time> [选项]")
        print("\n功能:")
        print("  - 恢复被删除的数据（将 DELETE 操作转换为 INSERT 语句）")
        print("  - 撤销 UPDATE 操作（将数据恢复到更新前的状态）")
        print("\n选项:")
        print("  --dry-run        预览模式，不实际执行")
        print("  --replace        使用 REPLACE INTO 替换已存在的记录（默认使用 INSERT IGNORE）")
        print("  --reverse        倒序执行（从下往上，最后删除的先恢复）")
        print("  --target-db DB   指定目标数据库名称（默认使用配置中的数据库）")
        print("\n示例:")
        print("  python recover_deleted_data.py cdb524080_binlog_mysqlbin.000018 '2025-10-24 11:15:30' '2025-10-24 11:15:35'")
        print("  python recover_deleted_data.py cdb524080_binlog_mysqlbin.000018 '2025-10-24 11:15:30' '2025-10-24 11:15:35' --dry-run")
        print("  python recover_deleted_data.py cdb524080_binlog_mysqlbin.000018 '2025-10-24 11:15:30' '2025-10-24 11:15:35' --replace")
        print("  python recover_deleted_data.py cdb524080_binlog_mysqlbin.000018 '2025-10-24 11:15:30' '2025-10-24 11:15:35' --target-db db_szpw_test")
        sys.exit(1)
    
    binlog_file = sys.argv[1]
    start_time = sys.argv[2]
    end_time = sys.argv[3]
    dry_run = '--dry-run' in sys.argv
    use_replace = '--replace' in sys.argv
    reverse = '--reverse' in sys.argv
    
    # 解析 --target-db 参数
    target_database = None
    if '--target-db' in sys.argv:
        try:
            target_db_index = sys.argv.index('--target-db')
            if target_db_index + 1 < len(sys.argv):
                target_database = sys.argv[target_db_index + 1]
            else:
                print("错误: --target-db 参数后必须指定数据库名称")
                sys.exit(1)
        except ValueError:
            pass
    
    # 检查 binlog 文件是否存在
    if not os.path.exists(binlog_file):
        print(f"错误: binlog 文件不存在: {binlog_file}")
        sys.exit(1)
    
    # 获取数据库配置
    db_config = get_db_config()
    if not db_config:
        print("错误: 无法获取数据库配置")
        sys.exit(1)
    
    try:
        # 1. 解析 binlog 文件
        print("=" * 60)
        print("步骤 1: 解析 binlog 文件")
        print("=" * 60)
        binlog_content = parse_binlog_time(binlog_file, start_time, end_time)
        
        if not binlog_content or len(binlog_content.strip()) == 0:
            print("警告: 在指定时间范围内未找到任何数据")
            sys.exit(0)
        
        # 2. 提取 DELETE 和 UPDATE 操作
        print("\n" + "=" * 60)
        print("步骤 2: 提取 DELETE 和 UPDATE 操作")
        print("=" * 60)
        delete_operations = extract_delete_operations(binlog_content)
        update_operations = extract_update_operations(binlog_content)
        
        if not delete_operations and not update_operations:
            print("在指定时间范围内未找到 DELETE 或 UPDATE 操作")
            sys.exit(0)
        
        if delete_operations:
            print(f"找到 {len(delete_operations)} 个 DELETE 操作")
        if update_operations:
            print(f"找到 {len(update_operations)} 个 UPDATE 操作")
        
        # 3. 转换为恢复语句
        print("\n" + "=" * 60)
        print("步骤 3: 转换为恢复语句")
        print("=" * 60)
        if target_database:
            print(f"目标数据库: {target_database}")
        
        insert_statements = []
        revert_statements = []
        
        if delete_operations:
            print("\n正在转换 DELETE 操作为 INSERT 语句...")
            insert_statements = convert_delete_to_insert(delete_operations, db_config, target_database=target_database)
            print(f"生成了 {len(insert_statements)} 条 INSERT 语句")
        
        if update_operations:
            print("\n正在转换 UPDATE 操作为撤销语句...")
            revert_statements = convert_update_to_revert(update_operations, db_config, target_database=target_database)
            print(f"生成了 {len(revert_statements)} 条撤销 UPDATE 语句")
        
        if not insert_statements and not revert_statements:
            print("无法生成恢复语句（可能是列信息不匹配）")
            sys.exit(0)
        
        # 4. 执行恢复
        print("\n" + "=" * 60)
        print("步骤 4: 执行恢复")
        print("=" * 60)
        execute_insert_statements(db_config, insert_statements, revert_statements=revert_statements, dry_run=dry_run, use_replace=use_replace, reverse=reverse, target_database=target_database)
        
        print("\n" + "=" * 60)
        print("完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

