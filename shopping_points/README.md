# About
代理管理模块
# Director  
 ├── __init__.py // django 应用注册  
 ├── migrations // django model模型数据库迁移   
 ├── admin.py // django 后台admin配置    
 ├── apps.py // app应用名字配置   
 ├── models.py // django model文件，数据库表格和model层相关方法    
 ├── serializers.py // django序列化，相当于controller 控制器层   
 ├── signals.py // Django signals（信号）处理   
 ├── url.py // api路由       
 ├── view.py // django view 视图层   
 
 UserAccountLevelViewSet 代理等级接口   
 CommissionWithdrawViewSet 佣金提现记录接口  
 UserAccountViewSet 用户账户接口    
 UserCommissionChangeRecordViewSet 佣金明细接口    
 UserCommissionMonthRecordViewSet 佣金月度记录接口    
 ReceiptAccountViewSet 用户收款账号接口    
  
 

