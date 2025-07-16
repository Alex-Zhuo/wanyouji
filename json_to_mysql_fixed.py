# coding=utf-8
import MySQLdb
import json
import base64
from typing import List, Dict, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 数据库连接配置 ---
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'asdlb1289asd',
    'database': 'db_pw_ai',
    'charset': 'utf8mb4',
    'port': 8306,
    # 增加连接超时和读取超时设置
    'connect_timeout': 60,
    'read_timeout': 60,
    'write_timeout': 60,
    # 设置更大的max_allowed_packet
    'init_command': 'SET SESSION max_allowed_packet=67108864'  # 64MB
}

def process_image_data(image_hex: str, max_size: int = 1024 * 1024) -> str:
    """
    处理图片数据，如果太大则截断或压缩
    
    Args:
        image_hex: 16进制图片数据
        max_size: 最大允许大小（字节）
    
    Returns:
        处理后的图片数据
    """
    if not image_hex:
        return ""
    
    try:
        # 将16进制转换为字节
        image_bytes = bytes.fromhex(image_hex)
        
        # 如果图片太大，截断或返回空
        if len(image_bytes) > max_size:
            logger.warning(f"图片数据过大 ({len(image_bytes)} bytes)，已截断")
            return ""
        
        return image_hex
    except Exception as e:
        logger.error(f"处理图片数据失败: {e}")
        return ""

def batch_insert_data(cursor, data: List[Dict[str, Any]], batch_size: int = 100):
    """
    分批插入数据，避免一次性插入过多数据
    
    Args:
        cursor: 数据库游标
        data: 要插入的数据列表
        batch_size: 每批插入的数据量
    """
    sql = "INSERT INTO shows (slug, name, show_at, place, price, logo, rate) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    
    total_inserted = 0
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        batch_values = []
        
        for item in batch:
            # 处理图片数据
            logo_data = process_image_data(item.get('logo', ''))
            
            values = (
                item.get('slug', ''),
                item.get('name', ''),
                item.get('show_at', ''),
                item.get('place', ''),
                item.get('price', ''),
                logo_data,
                item.get('rate', '')
            )
            batch_values.append(values)
        
        try:
            cursor.executemany(sql, batch_values)
            total_inserted += len(batch_values)
            logger.info(f"已插入 {len(batch_values)} 条数据，总计 {total_inserted} 条")
            
        except MySQLdb.Error as err:
            logger.error(f"插入批次数据失败: {err}")
            raise

def main():
    """主函数"""
    cnx = None
    cursor = None
    
    try:
        # 建立数据库连接
        logger.info("正在连接数据库...")
        cnx = MySQLdb.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        
        # 设置会话变量
        cursor.execute("SET SESSION max_allowed_packet=67108864")  # 64MB
        cursor.execute("SET SESSION wait_timeout=28800")  # 8小时
        cursor.execute("SET SESSION interactive_timeout=28800")  # 8小时
        
        # 读取JSON文件
        logger.info("正在读取JSON文件...")
        with open('/root/show_ai.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"JSON文件包含 {len(data)} 条记录")
        
        # 分批插入数据
        batch_insert_data(cursor, data, batch_size=50)
        
        # 提交事务
        cnx.commit()
        logger.info(f"成功插入所有数据到 shows 表")
        
    except MySQLdb.Error as err:
        logger.error(f"数据库操作失败: {err}")
        if cnx and hasattr(cnx, 'rollback'):
            cnx.rollback()
    except FileNotFoundError:
        logger.error("JSON文件不存在: /root/show_ai.json")
    except json.JSONDecodeError as e:
        logger.error(f"JSON文件格式错误: {e}")
    except Exception as e:
        logger.error(f"发生未知错误: {e}")
        if cnx and hasattr(cnx, 'rollback'):
            cnx.rollback()
    finally:
        # 关闭游标和连接
        if cursor:
            cursor.close()
        if cnx and hasattr(cnx, 'close'):
            cnx.close()
            logger.info("MySQL 连接已关闭")

def alternative_approach():
    """
    替代方案：如果图片数据太大，可以考虑以下方案
    1. 将图片数据存储到文件系统，数据库中只存储路径
    2. 使用BLOB字段存储图片
    3. 压缩图片数据
    """
    cnx = None
    cursor = None
    
    try:
        cnx = MySQLdb.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        
        # 设置更大的数据包大小
        cursor.execute("SET SESSION max_allowed_packet=134217728")  # 128MB
        
        with open('/root/show_ai.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 方案1：只存储图片路径，不存储图片数据
        sql = "INSERT INTO shows (slug, name, show_at, place, price, logo_path, rate) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        
        for item in data:
            # 如果有图片数据，保存到文件并存储路径
            logo_path = ""
            if item.get('logo'):
                try:
                    # 生成文件名
                    import hashlib
                    file_hash = hashlib.md5(item['logo'].encode()).hexdigest()
                    file_path = f"/var/www/images/{file_hash}.jpg"
                    
                    # 保存图片文件
                    with open(file_path, 'wb') as img_file:
                        img_file.write(bytes.fromhex(item['logo']))
                    
                    logo_path = file_path
                except Exception as e:
                    logger.warning(f"保存图片失败: {e}")
            
            values = (
                item.get('slug', ''),
                item.get('name', ''),
                item.get('show_at', ''),
                item.get('place', ''),
                item.get('price', ''),
                logo_path,
                item.get('rate', '')
            )
            
            cursor.execute(sql, values)
        
        cnx.commit()
        logger.info("使用文件路径方案插入完成")
        
    except Exception as e:
        logger.error(f"替代方案执行失败: {e}")
        if cnx and hasattr(cnx, 'rollback'):
            cnx.rollback()
    finally:
        if cursor:
            cursor.close()
        if cnx and hasattr(cnx, 'close'):
            cnx.close()

if __name__ == "__main__":
    # 首先尝试主方案
    try:
        main()
    except Exception as e:
        logger.error(f"主方案失败: {e}")
        logger.info("尝试替代方案...")
        alternative_approach() 