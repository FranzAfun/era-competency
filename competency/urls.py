from django.urls import path
from .views import (
    dashboard,
    login_view,
    logout_view,
    resend_otp_view,
    result,
    start_assessment,
    verify_otp_view,
)

urlpatterns = [
    path('', login_view, name='login'),
    path('login/', login_view, name='login_post'),
    path('verify-otp/', verify_otp_view, name='verify_otp'),
    path('resend-otp/', resend_otp_view, name='resend_otp'),
    path('dashboard/', dashboard, name='dashboard'),
    path('assessment/', start_assessment, name='start_assessment'),
    path('result/', result, name='result'),
]

urlpatterns += [
    path('logout/', logout_view, name='logout'),
]
