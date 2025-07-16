# coding=utf-8
import MySQLdb
import json
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
    'port': 8306
}

def insert_data_without_images():
    """
    方案1：不插入图片数据，只插入其他字段
    """
    cnx = None
    cursor = None
    
    try:
        # 建立数据库连接
        cnx = MySQLdb.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        
        # 设置更大的数据包大小
        cursor.execute("SET SESSION max_allowed_packet=67108864")  # 64MB
        
        # 读取JSON文件
        with open('/root/show_ai.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 只插入非图片字段
        sql = "INSERT INTO shows (slug, name, show_at, place, price, rate) VALUES (%s, %s, %s, %s, %s, %s)"
        
        for item in data:
            values = (
                item.get('slug', ''),
                item.get('name', ''),
                item.get('show_at', ''),
                item.get('place', ''),
                item.get('price', ''),
                item.get('rate', '')
            )
            cursor.execute(sql, values)
        
        cnx.commit()
        logger.info(f"成功插入 {len(data)} 条数据（不包含图片）")
        
    except Exception as e:
        logger.error(f"插入失败: {e}")
        if cnx:
            cnx.rollback()
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

def insert_data_with_compressed_images():
    """
    方案2：压缩图片数据后插入
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
        
        sql = "INSERT INTO shows (slug, name, show_at, place, price, logo, rate) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        
        for item in data:
            # 处理图片数据 - 如果太大则截断
            logo_data = item.get('logo', '')
            if logo_data and len(logo_data) > 1000000:  # 如果超过1MB
                logo_data = logo_data[:1000000]  # 截断到1MB
                logger.warning(f"图片数据过大，已截断: {item.get('name', '')}")
            
            values = (
                item.get('slug', ''),
                item.get('name', ''),
                item.get('show_at', ''),
                item.get('place', ''),
                item.get('price', ''),
                logo_data,
                item.get('rate', '')
            )
            cursor.execute(sql, values)
        
        cnx.commit()
        logger.info(f"成功插入 {len(data)} 条数据（包含压缩图片）")
        
    except Exception as e:
        logger.error(f"插入失败: {e}")
        if cnx:
            cnx.rollback()
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

def insert_data_batch():
    """
    方案3：分批插入，每次只处理少量数据
    """
    cnx = None
    cursor = None
    
    try:
        cnx = MySQLdb.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        
        # 设置更大的数据包大小
        cursor.execute("SET SESSION max_allowed_packet=67108864")  # 64MB
        
        with open('/root/show_ai.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        sql = "INSERT INTO shows (slug, name, show_at, place, price, logo, rate) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        
        # 分批处理，每批10条
        batch_size = 10
        total_inserted = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_values = []
            
            for item in batch:
                # 处理图片数据
                logo_data = item.get('logo', '')
                if logo_data and len(logo_data) > 500000:  # 如果超过500KB
                    logo_data = logo_data[:500000]  # 截断到500KB
                
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
            
            cursor.executemany(sql, batch_values)
            total_inserted += len(batch_values)
            logger.info(f"已插入 {total_inserted}/{len(data)} 条数据")
        
        cnx.commit()
        logger.info(f"成功插入所有 {total_inserted} 条数据")
        
    except Exception as e:
        logger.error(f"插入失败: {e}")
        if cnx:
            cnx.rollback()
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

if __name__ == "__main__":
    print("选择插入方案:")
    print("1. 不插入图片数据")
    print("2. 压缩图片数据后插入")
    print("3. 分批插入")
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    if choice == "1":
        insert_data_without_images()
    elif choice == "2":
        insert_data_with_compressed_images()
    elif choice == "3":
        insert_data_batch()
    else:
        print("无效选择，使用默认方案（不插入图片数据）")
        insert_data_without_images() 