from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Address
from apps.user_activities.models import UserActivity

class AddressInline(admin.TabularInline):
    model = Address
    extra = 0

class UserActivityInline(admin.TabularInline):
    model = UserActivity
    extra = 0
    readonly_fields = ('product', 'view_time', 'view_count', 'last_viewed')
    max_num = 10

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone_number', 'role', 'is_online', 'is_staff')
    list_filter = ('role', 'is_online', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'email', 'phone_number')}),
        ('Разрешения', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Важные даты', {'fields': ('last_login', 'date_joined', 'last_activity')}),
        ('Статус', {'fields': ('is_online',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone_number', 'password1', 'password2', 'role'),
        }),
    )
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('username',)
    inlines = [AddressInline, UserActivityInline]

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Address)