# -*- coding: utf-8 -*-
import logging
# from fastapi import FastAPI
# from fastapi import Query
# from fastapi import Body
import os

# app = FastAPI()
import json
import time
from selenium import webdriver
# from selenium.webdriver.support.wait import WebDriverWait
# import pyautogui
from selenium.webdriver.common.action_chains import ActionChains


def vcg_get_cookies(name: str, password: str):
    # print('当前鼠标位置： {}'.format(mouse.position))
    url = 'https://maizuo.maitix.com/login'
    
    try:
        # 导入Firefox配置工具
        from maizuo.firefox_config import create_firefox_driver, find_firefox_binary, find_gecko_driver
        
        # 查找Firefox和GeckoDriver路径
        firefox_path = find_firefox_binary()
        gecko_path = find_gecko_driver()
        
        print(f"Firefox路径: {firefox_path}")
        print(f"GeckoDriver路径: {gecko_path}")
        
        # 创建WebDriver
        driver = create_firefox_driver(
            headless=True,
            gecko_driver_path=gecko_path,
            firefox_binary_path=firefox_path
        )
        
        try:
            # 访问目标URL
            driver.get(url)
            time.sleep(4)
            
            # 定位到需要进行滑块验证的元素
            slider = driver.find_element_by_class_name("btn_slide")  # 假设是根据id定位

            # 对滑块进行拖动
            ActionChains(driver).click_and_hold(slider).perform()
            # 假设滑动50像素
            is_auth = False
            for i in range(1, 20):
                time.sleep(0.2)
                ActionChains(driver).move_by_offset(xoffset=i * 50, yoffset=0).perform()
                if driver.find_element_by_class_name('nc-lang-cnt').text == '验证通过':
                    is_auth = True
                    break
                    
            if not is_auth:
                driver.quit()
                return False, None, None, '滑动失败'
                
            # cookies = driver.get_cookies()
            # print(cookies)
            time.sleep(1)
            driver.find_element_by_id('userName').send_keys(name)
            time.sleep(1)
            driver.find_element_by_id('password').send_keys(password)
            time.sleep(1)
            driver.find_element_by_class_name("loginBtn___xKEwQ").click()
            # 等登录后响应
            time.sleep(5)
            # user_name = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'userInfo')))
            # print(user_name)
            cookies = driver.get_cookies()  # Selenium为我们提供了get_cookies来获取登录cookies
            
            # 获取请求头信息
            # agent = driver.execute_script("return navigator.userAgent")
            headers = dict()
            headers['accept'] = "application/json"
            headers['content-type'] = "application/json;charset=UTF-8"
            
            # 处理cookies
            cookie = dict()
            for item in cookies:
                cookie[item['name']] = item['value']
                
            # 设置XSRF token
            if 'XSRF-TOKEN' in cookie:
                headers['x-xsrf-token'] = cookie['XSRF-TOKEN']
            
            # headers['sec-ch-ua-platform'] = "Windows"
            headers['accept-language'] = "zh-CN,zh;q=0.9"
            headers['referer'] = "https://maizuo.maitix.com/"
            headers['origin'] = "https://maizuo.maitix.com/"
            # headers['user-agent'] = agent
            # print(headers)
            
            return True, headers, cookie, None
            
        except Exception as e:
            print(f"执行过程中发生错误: {e}")
            return False, None, None, f'执行错误: {e}'
        finally:
            # 确保WebDriver被正确关闭
            try:
                if 'driver' in locals():
                    driver.quit()
            except Exception as close_error:
                print(f"关闭WebDriver时发生错误: {close_error}")
                
    except Exception as e:
        print(f"初始化过程中发生错误: {e}")
        return False, None, None, f'初始化错误: {e}'

# @app.get('/mz')
# def mz_login():
#     st, headers, cookies = vcg_get_cookies()
#     if st:
#         return dict(code=200, headers=headers, cookies=cookies)
#     else:
#         return dict(code=400, headers=headers, cookies=cookies)

# if __name__ == '__main__':
#      import uvicorn
#      uvicorn.run(app, host='0.0.0.0', port=8090, reload=True)
