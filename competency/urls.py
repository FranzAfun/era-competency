from django.urls import path
from .admin_portal_views import (
    admin_clear_stage_questions_view,
    admin_delete_stage_view,
    admin_dashboard_view,
    admin_login_view,
    admin_logout_view,
    admin_questions_view,
    admin_delete_question_view,
    admin_questions_template_download_view,
    admin_reset_cycle_view,
    admin_stages_view,
    admin_toggle_cycle_lock_view,
)
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
    path('portal/login/', admin_login_view, name='admin_portal_login'),
    path('portal/logout/', admin_logout_view, name='admin_portal_logout'),
    path('portal/', admin_dashboard_view, name='admin_portal_dashboard'),
    path('portal/stages/', admin_stages_view, name='admin_portal_stages'),
    path('portal/stages/toggle-cycle-lock/', admin_toggle_cycle_lock_view, name='admin_portal_toggle_cycle_lock'),
    path('portal/stages/<int:stage_id>/clear-questions/', admin_clear_stage_questions_view, name='admin_portal_clear_stage_questions'),
    path('portal/stages/<int:stage_id>/delete/', admin_delete_stage_view, name='admin_portal_delete_stage'),
    path('portal/stages/reset-cycle/', admin_reset_cycle_view, name='admin_portal_reset_cycle'),
    path('portal/questions/', admin_questions_view, name='admin_portal_questions'),
    path('portal/questions/<int:question_id>/delete/', admin_delete_question_view, name='admin_delete_question'),
    path('portal/questions/template/', admin_questions_template_download_view, name='admin_portal_questions_template'),
]
