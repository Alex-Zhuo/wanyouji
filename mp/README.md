# About
基本配置模块
# Director  
 ├── __init__.py // django 应用注册  
 ├── migrations // django model模型数据库迁移   
 ├── admin.py // django 后台admin配置    
 ├── apps.py // app应用名字配置   
 ├── event_key_handle.py // 公众号事件event通用处理  
 ├── models.py // django model文件，数据库表格和model层相关方法   
 ├── mp_config.py //   公众号部分配置  
 ├── msg_handle.py // 公众号推送消息处理     
 ├── parsers.py // 公众号xml消息解析   
 ├── renders.py // 公众号xml消息回复   
 ├── url.py // api路由       
 ├── view.py // django view 视图层   
 ├── wechat_client.py // 微信小程序公众号通用模型接入  
 
 WxAuthViewSet 微信小程序登录   
 LpViewSet 微信小程序手机号绑定  
 BasicConfigViewSet 基础配置接口      
 MpClientView 公众号接口封装    
 MpWebView 公众号登录  
 MpApi 公众号回调配置方法   
  
 

