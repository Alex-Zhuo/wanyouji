from django_q.tasks import async_task


def down_load_task():
    from ticket.models import DownLoadTask
    async_task(DownLoadTask.do_task)


def update_ticket_file_stock_from_redis():
    from ticket.models import TicketFile
    TicketFile.update_stock_from_redis()
