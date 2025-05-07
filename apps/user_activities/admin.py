from django.contrib import admin
from .models import UserActivity

class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'view_count', 'view_time', 'last_viewed')
    list_filter = ('last_viewed',)
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('last_viewed',)

admin.site.register(UserActivity, UserActivityAdmin)