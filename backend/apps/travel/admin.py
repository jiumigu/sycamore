from django.contrib import admin

from .models import TravelPlan, TravelPlanItem


class TravelPlanItemInline(admin.TabularInline):
    model = TravelPlanItem
    extra = 0
    fields = ['item_type', 'name', 'estimate_cost', 'is_completed', 'sort_order']


@admin.register(TravelPlan)
class TravelPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'destination', 'start_date', 'status', 'total_estimate']
    list_filter = ['status']
    search_fields = ['name', 'destination']
    ordering = ['-start_date']
    inlines = [TravelPlanItemInline]
