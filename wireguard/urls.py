from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

app_name = 'wireguard'
urlpatterns = [
    path('home/', views.HomeView.as_view(), name='home'),
    path('peer-new', views.PeerNewView.as_view(), name='peer-new'),
    path('peer/<int:pk>/detail', views.PeerDetailView.as_view(), name='peer-detail'),
    path('peers/', views.PeerListView.as_view(), name='peer-list'),
    path('peer/<int:pk>/delete', views.PeerDeleteView.as_view(), name='peer-delete'),

    path('server-new/', views.ServerNewView.as_view(), name='server-new'),
    path('servers/', views.ServerListView.as_view(), name='server-list'),
    path('server/<slug:interface>/', views.ServerSubsetView.as_view(), name='server-subset'),
    path('server/<int:pk>/delete', views.ServerDeleteView.as_view(), name='server-delete'),
]
