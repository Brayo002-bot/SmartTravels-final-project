from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',          views.system_admin_dashboard, name='system_admin_dashboard'),
    path('users/',              views.manage_users,           name='manage_users'),
    path('users/<int:user_id>/toggle/', views.toggle_user_status, name='toggle_user_status'),
    path('admins/',             views.manage_admins,          name='manage_admins'),
    path('analytics/',          views.analytics,              name='system_analytics'),
    path('reports/',             views.analytics,              name='system_reports'),
    path('audit/',              views.audit_logs,             name='audit_logs'),
    path('settings/',           views.system_settings,        name='system_settings'),
    path('subscribers/',        views.subscribers,            name='subscribers'),
    path('subscribe/',          views.subscribe,              name='subscribe'),
]
