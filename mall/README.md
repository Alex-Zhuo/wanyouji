# About
用户管理模块
# Director  
 ├── images // 静态资源分享背景图片和字体  
 ├── __init__.py // django 应用注册  
 ├── migrations // django model模型数据库迁移   
 ├── admin.py // django 后台admin配置    
 ├── apps.py // app应用名字配置   
 ├── express_api.py // 快递查询接口    
 ├── mall_conf.py // 配置文件    
 ├── models.py // django model文件，数据库表格和model层相关方法    
 ├── pay_service.py // 微信支付方法封装  
 ├── serializers.py // django序列化，相当于controller 控制器层   
 ├── signals.py // Django signals（信号）处理   
 ├── tasks.py // celery任务    
 ├── url.py // api路由  
 ├── user_cache.py // 用户缓存封装    
 ├── utils.py // 模块公共方法        
 ├── view.py // django view 视图层   
 
 UserViewSet 用户接口   
 ReceiptViewset 收款记录接口  
 UserAddressViewSet 用户地址接口    
 HotSearchViewSet 热搜词接口    
 ExpressCompanyViewSet 快递公司接口    
 ResourceViewSet 多媒体资源接口    
 ShareQrcodeBackgroundViewSet 二维码背景图片接口  
 ServiceAuthRecordViewSet  用户服务协议记录接口  
 MembershipCardViewSet   年度会员卡设置接口   
 MemberCardRecordViewSet   年度会员卡订单接口  
 AgreementRecordViewSet  用户协议隐私记录接口  
  
 

