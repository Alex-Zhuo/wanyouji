# About
立云科技：  
总功能模块注释讲解，具体app注释请阅读每个模块的readme
# Director
应用app功能模块具体请看app里面的readme   
通用配置功能模块如下：  
├── admins   
│   ├── app.py // 用于控制后台菜单排序   

├── caches // redis（pika）缓存应用  

├── common // 通用方法封装  
│   ├── config.py // 读取配置文件   
│   ├── dateutils.py // 日期时间处理方法  
│   ├── qrutils.py // 图片合成通用方法  
│   ├── utils.py // 业务通用方法  

├── concu  
│   ├── api_limit.py //  控制api并发qps方法  
│   ├── stock_cache.py // 并发库存计数处理方法  

├── dj // django程序入口  
│   ├── asgi.py // asgi协议    
│   ├── wsgi.py // wsgi协议  
│   ├── celery.py // celery配置   
│   ├── settings.py // django基本配置     
│   ├── url.py // django api路由  
  
├── dj_ext // django方法重载  
│   ├── AdminMixins.py // admin方法重载     
│   ├── exceptions.py // 错误处理重载  
│   ├── filters.py // admin业务过滤重载   
│   ├── middlewares.py // 中间件重载  
│   ├── permissions.py // 权限控制重载 

├── douyin // 抖音平台接入（无效）  
│   ├── __init__.py // 抖音接入  
│   ├── exceptions.py // 错误处理  
│   ├── platform_public_key.py // 抖音平台公钥(没用已作废)   
│   ├── private_key.py // 抖音私钥  
│   ├── public_key.py // 抖音公钥  

├── home // 后台首页数据展示   
 
├── maizuo // 麦座模块（无效）  
│   ├── __init__.py // 麦座同步座位功能  
│   ├── login.py // 麦座自动登录  
│   ├── install_guide.txt // 安装指引    

├── push // 公众号模板消息接入

├── qcloud // 短信接入功能  
│   ├── __init__.py // 腾讯业务接口接入
│   ├── consts.py // 短信验证码    
│   ├── requests.py // 短信相关通用方法  
│   ├── sms.py // 腾讯和阿里短信调用方法  
│   ├── serializers.py // 短信api通用验证方法  

├── production // django方法重载  
│   ├── celery_szpw.service // celery 异步任务shell服务          
│   ├── celery_szpw_beat.service // celery 定时任务shell服务      
│   ├── ly_szpw.service // 主服务shell  
│   ├── qcluster_szpw.service // django_q 异步服务用于处理文件  

├── restframework_ext // django方法重载  
│   ├── exceptions.py // 通用异常处理方法        
│   ├── filterbackends.py // 通用后台过滤方法    
│   ├── mixins.py // 接口序列化重载   
│   ├── models.py // 通用模型   
│   ├── pagination.py // 通用分页方法  
│   ├── permissions.py // 通用接口权限方法    
│   ├── serializers.py // 通用序列化方法  
│   ├── views.py // 通用接口方法 

├── simpleui // simpleui后台模板目录  
├── static // django静态文件目录  
├── streaming // 流式响应  
│   ├── utils.py //   通用方法        
│   ├── view.py // 调用用例         
├── templates // django模板文件目录   
├── deploy-requirements.txt // 环境依赖包   
├── requirements.txt // 环境依赖包  
├── env.yml.sample // 配置文件模板  
├── README.md // 模块注释  
├── manage.py // django 内置启动文件  



App功能模块如下：  
 ├── ai_agent // AI模块  
 ├── caiyicloud // 彩艺模块  
 ├── coupon // 消费券模块  
 ├── express // 邮费模板模块   
 ├── group_activity // 找搭子模块   
 ├── kuaishou_wxa // 快手接入第三方平台模块 （无效）   
 ├── log // 后台操作日志模块   
 ├── mall // 用户管理模块   
 ├── mp // 基本配置模块   
 ├── renovation // 商城装修模块   
 ├── shopping_points // 代理模块  
 ├── statistical // 数据统计模块  
 ├── ticket // 票务模块  
 ├── xiaoghongshu // 小红书接入模块（无效）  
  
 

