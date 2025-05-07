import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

app = Celery('marketplace')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Определение периодических задач
app.conf.beat_schedule = {
    # Генерация рекомендаций каждый день в 8:00
    'generate-recommendations-daily': {
        'task': 'apps.ai_assistant.tasks.generate_daily_recommendations',
        'schedule': crontab(hour=8, minute=0),
    },
    # Отчет о продажах для продавцов каждый понедельник в 7:00
    'send-sales-report-weekly': {
        'task': 'apps.orders.tasks.send_weekly_sales_report',
        'schedule': crontab(hour=7, minute=0, day_of_week=1),
    },
    # Уведомления о товарах, которых мало в наличии, каждый день в 9:00
    'low-stock-notification-daily': {
        'task': 'apps.products.tasks.notify_low_stock_products',
        'schedule': crontab(hour=9, minute=0),
    },
    # Обновление статуса "в сети" каждые 10 минут
    'update-online-status': {
        'task': 'apps.accounts.tasks.update_online_status',
        'schedule': crontab(minute='*/10'),
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
