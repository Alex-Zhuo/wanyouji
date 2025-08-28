from django_q.tasks import async_task


def down_load_task():
    from ticket.models import DownLoadTask
    async_task(DownLoadTask.do_task)