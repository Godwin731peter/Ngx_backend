from . import views
from django.urls import path

urlpatterns = [
    path('login/', views.loginView.as_view()),
    path('refresh/', views.refreshView.as_view()),
    path('logout/', views.BrowserLogoutView.as_view()),
    path('auth/pkce/', views.GooglePKCEInitView.as_view()),
    path('auth/google/', views.GoogleBrowserAuthView.as_view(), name='google_auth'),
    path('auth/google/callback/', views.CallbackView.as_view(), name='google_auth_callback'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('list/user/', views.UserListView.as_view())
]