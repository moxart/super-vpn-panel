from django.urls import path

from . import views

app_name = 'wireguard'
urlpatterns = [
    path('home/', views.HomeView.as_view(), name='home'),

    path('peer-new', views.PeerNewView.as_view(), name='peer-new'),
    path('peers/', views.PeerListView.as_view(), name='peer-list'),
    path('peer/<int:pk>/detail', views.PeerDetailView.as_view(), name='peer-detail'),
    path('peer/<int:pk>/edit', views.PeerEditView.as_view(), name='peer-edit'),
    path('peer/<int:pk>/toggle', views.PeerToggleView.as_view(), name='peer-toggle'),
    path('peer/<int:pk>/delete', views.PeerDeleteView.as_view(), name='peer-delete'),
    path('peer/<int:pk>/download/<str:kind>', views.PeerDownloadView.as_view(), name='peer-download'),

    path('server-new/', views.ServerNewView.as_view(), name='server-new'),
    path('servers/', views.ServerListView.as_view(), name='server-list'),
    path('server/<int:pk>/edit', views.ServerEditView.as_view(), name='server-edit'),
    path('server/<int:pk>/delete', views.ServerDeleteView.as_view(), name='server-delete'),
    path('server/<int:pk>/config', views.ServerConfigDownloadView.as_view(), name='server-config'),
    path('server/<str:interface>/', views.ServerSubsetView.as_view(), name='server-subset'),

    path('backup/', views.BackupView.as_view(), name='backup'),
    path('backup/export', views.BackupExportView.as_view(), name='backup-export'),
]
