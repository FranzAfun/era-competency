from django.urls import path
from .views import login_view, dashboard, start_assessment, result
from .views import logout_view

urlpatterns = [
    path('', login_view, name='login'),
    path('login/', login_view, name='login_post'),
    path('dashboard/', dashboard, name='dashboard'),
    path('assessment/', start_assessment, name='start_assessment'),
    path('result/', result, name='result'),
]

urlpatterns += [
    path('logout/', logout_view, name='logout'),
]
