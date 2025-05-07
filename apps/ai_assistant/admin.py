from django.contrib import admin
from .models import AISearchQuery, AIRecommendation

class AISearchQueryAdmin(admin.ModelAdmin):
    list_display = ('user', 'query', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'query')
    readonly_fields = ('created_at',)

class AIRecommendationAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason', 'created_at', 'is_viewed')
    list_filter = ('created_at', 'is_viewed')
    search_fields = ('user__username', 'reason')
    readonly_fields = ('created_at',)
    filter_horizontal = ('products',)

admin.site.register(AISearchQuery, AISearchQueryAdmin)
admin.site.register(AIRecommendation, AIRecommendationAdmin)
