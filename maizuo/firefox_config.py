#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firefox WebDriver 配置工具
解决 "Process unexpectedly closed with status 1" 错误
"""

import os
import platform
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


def get_firefox_options(headless=True, disable_images=True, disable_js=False):
    """
    获取优化的Firefox选项配置
    
    Args:
        headless: 是否使用无头模式
        disable_images: 是否禁用图片加载
        disable_js: 是否禁用JavaScript
    
    Returns:
        Options: 配置好的Firefox选项
    """
    options = Options()
    
    # 基本设置
    if headless:
        options.headless = True
    
    # 系统特定的启动参数
    if platform.system() == "Windows":
        # Windows特定配置
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        
    elif platform.system() == "Linux":
        # Linux特定配置
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
    elif platform.system() == "Darwin":  # macOS
        # macOS特定配置
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
    
    # 通用优化参数
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--ignore-certificate-errors-spki-list')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-features=TranslateUI')
    options.add_argument('--disable-ipc-flooding-protection')
    
    # 性能优化
    if disable_images:
        options.add_argument('--disable-images')
    
    if disable_js:
        options.add_argument('--disable-javascript')
    
    # 设置Firefox配置文件
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", os.getcwd())
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-gzip")
    
    # 禁用各种弹窗和通知
    options.set_preference("dom.webnotifications.enabled", False)
    options.set_preference("dom.push.enabled", False)
    options.set_preference("media.navigator.enabled", False)
    options.set_preference("media.peerconnection.enabled", False)
    
    # 设置页面加载策略
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.cache.memory.enable", False)
    options.set_preference("browser.cache.offline.enable", False)
    options.set_preference("browser.cache.check_doc_frequency", 3)
    
    # 禁用自动更新和检查
    options.set_preference("app.update.enabled", False)
    options.set_preference("app.update.auto", False)
    options.set_preference("app.update.checkInstallTime", False)
    options.set_preference("app.update.disabledForTesting", True)
    
    # 禁用遥测和崩溃报告
    options.set_preference("toolkit.telemetry.enabled", False)
    options.set_preference("toolkit.telemetry.unified", False)
    options.set_preference("breakpad.reportURL", "")
    options.set_preference("browser.tabs.crashReporting.sendReport", False)
    
    # 禁用默认浏览器检查
    options.set_preference("browser.shell.checkDefaultBrowser", False)
    
    # 设置用户代理
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
    options.set_preference("general.useragent.override", user_agent)
    
    return options


def get_firefox_service(gecko_driver_path=None):
    """
    获取Firefox服务配置
    
    Args:
        gecko_driver_path: GeckoDriver可执行文件路径
    
    Returns:
        Service: 配置好的Firefox服务
    """
    if gecko_driver_path and os.path.exists(gecko_driver_path):
        return Service(executable_path=gecko_driver_path)
    return None


def find_firefox_binary():
    """
    查找Firefox浏览器可执行文件路径
    
    Returns:
        str: Firefox可执行文件路径，如果找不到返回None
    """
    possible_paths = []
    
    if platform.system() == "Windows":
        possible_paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            os.path.expanduser(r"~\AppData\Local\Mozilla\Firefox\firefox.exe")
        ]
    elif platform.system() == "Linux":
        possible_paths = [
            "/usr/bin/firefox",
            "/usr/bin/firefox-esr",
            "/snap/bin/firefox"
        ]
    elif platform.system() == "Darwin":  # macOS
        possible_paths = [
            "/Applications/Firefox.app/Contents/MacOS/firefox"
        ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None


def find_gecko_driver():
    """
    查找GeckoDriver可执行文件
    
    Returns:
        str: GeckoDriver可执行文件路径，如果找不到返回None
    """
    # 检查环境变量
    gecko_path = os.environ.get('GECKODRIVER_PATH')
    if gecko_path and os.path.exists(gecko_path):
        return gecko_path
    
    # 检查当前目录
    current_dir = os.getcwd()
    if platform.system() == "Windows":
        gecko_name = "geckodriver.exe"
    else:
        gecko_name = "geckodriver"
    
    gecko_path = os.path.join(current_dir, gecko_name)
    if os.path.exists(gecko_path):
        return gecko_path
    
    # 检查PATH环境变量
    import shutil
    try:
        gecko_path = shutil.which("geckodriver")
        if gecko_path:
            return gecko_path
    except:
        pass
    
    return None


def create_firefox_driver(headless=True, gecko_driver_path=None, firefox_binary_path=None):
    """
    创建Firefox WebDriver实例
    
    Args:
        headless: 是否使用无头模式
        gecko_driver_path: GeckoDriver路径
        firefox_binary_path: Firefox二进制文件路径
    
    Returns:
        webdriver.Firefox: 配置好的Firefox WebDriver实例
    """
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException
    
    try:
        # 获取配置
        options = get_firefox_options(headless=headless)
        service = get_firefox_service(gecko_driver_path)
        
        # 设置Firefox二进制文件路径
        if firefox_binary_path and os.path.exists(firefox_binary_path):
            options.binary_location = firefox_binary_path
        
        # 创建WebDriver
        if service:
            driver = webdriver.Firefox(service=service, options=options)
        else:
            driver = webdriver.Firefox(options=options)
        
        # 设置超时
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        return driver
        
    except WebDriverException as e:
        print(f"Firefox WebDriver启动失败: {e}")
        raise
    except Exception as e:
        print(f"创建Firefox WebDriver时发生未知错误: {e}")
        raise


if __name__ == "__main__":
    # 测试配置
    print("Firefox配置测试")
    print(f"Firefox路径: {find_firefox_binary()}")
    print(f"GeckoDriver路径: {find_gecko_driver()}")
    
    # 测试选项配置
    options = get_firefox_options()
    print(f"Firefox选项数量: {len(options.arguments)}")
