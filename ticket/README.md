# About
演出管理模块
# Director  
 ├── images // 静态资源分享背景图片 
 ├── __init__.py // django 应用注册  
 ├── migrations // django model模型数据库迁移   
 ├── admin.py // django 后台admin配置    
 ├── apps.py // app应用名字配置        
 ├── models.py // django model文件，数据库表格和model层相关方法    
 ├── serializers.py // django序列化，相当于controller 控制器层   
 ├── signals.py // Django signals（信号）处理   
 ├── stock_updater.py // 库存计数处理封装方法  
 ├── tasks.py // celery任务    
 ├── url.py // api路由    
 ├── utils.py // 模块公共方法        
 ├── view.py // django view 视图层   
 
VenuesViewSet    演出场馆接口  
TicketColorViewSet 票档颜色接口   
ShowCollectRecordViewSet  用户演出收藏记录接口  
ShowProjectViewSet 演出项目接口  
SessionSeatViewSet 演出场次座位接口  
SessionInfoViewSet  演出场次接口  
TicketFileViewSet  演出场次票档接口  
TicketOrderViewSet  订单接口  
ShowPerformerViewSet 演员管理接口  
ShowUserViewSet  常用联系人接口  
PerformerFocusRecordViewSet  用户演员关注记录接口  
ShowCommentImageViewSet  演出评论图片接口  
ShowCommentViewSet  演出评论接口  
TicketBookingViewSet 抖音预约单接口  
TicketGiveRecordViewSet  门票赠送相关接口
  
 

