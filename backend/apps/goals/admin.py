from django.contrib import admin

from .models import Action, Goal, GoalReview, Milestone


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'category', 'priority', 'status', 'progress_percentage', 'deadline', 'year']
    list_filter = ['category', 'priority', 'status', 'year']
    search_fields = ['title', 'description']
    ordering = ['-created_at']


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'goal', 'status', 'order_num', 'target_date']
    list_filter = ['status']
    search_fields = ['title']


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'goal', 'milestone', 'created_at']
    list_filter = ['goal']
    search_fields = ['name']


@admin.register(GoalReview)
class GoalReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'goal', 'review_type', 'review_date', 'score']
    list_filter = ['review_type', 'review_date']
