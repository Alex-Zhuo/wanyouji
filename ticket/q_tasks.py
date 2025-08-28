from django_q.tasks import async_task


@async_task
def down_load_task():
    from ticket.models import DownLoadTask
    DownLoadTask.do_task()