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
    from selenium.webdriver.firefox.options import Options
    options = Options()
    options.headless = True
    # 不加载图片,加快访问速度
    # options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    # 此步骤很重要，设置为开发者模式，防止被各大网站识别出来使用了Selenium
    # options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    # options.add_argument('--headless')
    # options.add_argument('--disable-gpu')
    # 添加本地代理
    # options.add_argument("--proxy--server=127.0.0.1:8080")
    # 添加UA
    # ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
    # options.add_argument('user-agent=' + ua)
    # options.add_argument('verify=False')
    with webdriver.Firefox(options=options) as driver:
        # driver.maximize_window()
        # width, height = pyautogui.size()
        # print('width,{},{}'.format(width, height))
        # wait = WebDriverWait(driver, 10)
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
        # time.sleep(2)
        # # driver.refresh()
        # wd = 0.5875 * width
        # ht = 0.6 * height
        # pyautogui.dragTo(wd, ht, duration=0.8)
        # x, y = pyautogui.position()
        # print('xy1,{},{}'.format(x, y))
        # pyautogui.dragRel(500, 0, duration=1)
        # # tt = driver.find_element_by_class_name('nc-lang-cnt').text
        # i = 1
        # while i < 6:
        #     time.sleep(1)
        #     if driver.find_element_by_class_name('nc-lang-cnt').text == '验证通过':
        #         break
        #     else:
        #         # driver.refresh()
        #         pyautogui.dragTo(wd, ht, duration=0.8)
        #         pyautogui.dragRel(500, 0, duration=1)
        #         i += 1
        if not is_auth:
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
        # driver.close()  # 获取cookies便可以关闭浏览器
        # 然后的关键就是保存cookies，之后请求从文件中读取cookies就可以省去每次都要登录一次的
        # 当然可以把cookies返回回去，但是之后的每次请求都要先执行一次login没有发挥cookies的作用
        # jsonCookies = json.dumps(cookies)  # 通过json将cookies写入文件
        cookie = dict()
        for item in cookies:
            cookie[item['name']] = item['value']
        # print(cookie)
        # 获取请求头信息
        # agent = driver.execute_script("return navigator.userAgent")
        headers = dict()
        headers['accept'] = "application/json"
        headers['content-type'] = "application/json;charset=UTF-8"
        headers['x-xsrf-token'] = cookie['XSRF-TOKEN']
        # headers['sec-ch-ua-platform'] = "Windows"
        headers['accept-language'] = "zh-CN,zh;q=0.9"
        headers['referer'] = "https://maizuo.maitix.com/"
        headers['origin'] = "https://maizuo.maitix.com/"
        # headers['user-agent'] = agent
        # print(headers)
        return True, headers, cookie, None
        # with open('vcgCookies.json', 'w') as f:
        #     f.write(jsonCookies)
        # print(cookies)
        # cookie = [item["name"] + "=" + item["value"] for item in cookies]
        # cookiestr = ';'.join(item for item in cookie)
        # headers_cookie = {
        #     "Cookie": cookiestr  # 通过接口请求时需要cookies等信息
        # }

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
