from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Ticket, Comment

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role',)}),
    )
    search_fields = ('username', 'email', 'role')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('title', 'create_by', 'assigned_to', 'priority', 'status', 'created_at', 'updated_at', 'response_due_at', 'resolution_due_at')
    list_filter = ('priority', 'status', 'assigned_to', 'created_at')
    search_fields = ('title', 'description', 'create_by__username', 'assigned_to__username')
    raw_id_fields = ('create_by', 'assigned_to')
    date_hierarchy = 'created_at'

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'ticket', 'text', 'created_at')
    list_filter = ('user', 'ticket__title', 'created_at')
    search_fields = ('text', 'user__username', 'ticket__title')
    raw_id_fields = ('user', 'ticket')