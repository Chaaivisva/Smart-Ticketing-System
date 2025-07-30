# tickets/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login_view'),
    path('register/', views.register_view, name='register_view'),
    path('logout/', views.logout_view, name='logout_view'),

    # Ticket Management URLs
    path('', views.dashboard, name='dashboard'), # Home page / Dashboard
    path('tickets/create/', views.create_ticket, name='create_ticket'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:pk>/update/', views.update_ticket, name='update_ticket'),
    path('tickets/<int:pk>/delete/', views.delete_ticket, name='delete_ticket'),

    # Analytics Dashboards
    path('analytics/agents/', views.agent_performance_dashboard, name='agent_performance_dashboard'),
    path('analytics/trends/', views.ticket_trend_dashboard, name='ticket_trend_dashboard'),
]
