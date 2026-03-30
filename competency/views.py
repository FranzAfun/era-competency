import random
from datetime import timedelta
from html import escape as _esc

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Assessment, AssessmentCycle, Executive, LoginOTP, Option, Question, Response, Stage


OTP_EXPIRY_MINUTES = 10
QUESTIONS_PER_STAGE = 25
PASSING_SCORE_PERCENT = 70


def _get_active_stage_orders():
    return list(
        Stage.objects.filter(is_active=True)
        .order_by('order')
        .values_list('order', flat=True)
    )


def _is_cycle_locked(cycle):
    return bool(cycle and cycle.is_locked)


def _get_stage_by_order(stage_number):
    if stage_number is None:
        return None
    return Stage.objects.filter(order=stage_number).first()


def _get_current_cycle():
    current_cycle = AssessmentCycle.objects.filter(is_current=True).order_by('-sequence').first()
    if current_cycle:
        return current_cycle

    latest_cycle = AssessmentCycle.objects.order_by('-sequence').first()
    next_sequence = latest_cycle.sequence + 1 if latest_cycle else 1
    current_cycle = AssessmentCycle.objects.create(
        name=f'Assessment {next_sequence}',
        sequence=next_sequence,
        is_current=True,
        is_locked=False,
    )
    return current_cycle


def _generate_otp_code():
    return f"{random.randint(100000, 999999)}"


def _build_email_html(title, body_html):
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f6f2ea;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f6f2ea;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#fcf8f1;border-radius:10px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,0.06);">
  <tr><td style="background-color:#454285;padding:24px 32px;text-align:center;">
    <h1 style="margin:0;color:#ffffff;font-size:18px;font-weight:700;letter-spacing:3px;">ERA AXIS</h1>
  </td></tr>
  <tr><td style="padding:32px;">
    <h2 style="margin:0 0 20px;color:#182134;font-size:20px;font-weight:600;">{title}</h2>
    {body_html}
  </td></tr>
  <tr><td style="border-top:1px solid #ece7dd;padding:20px 32px;text-align:center;">
    <p style="margin:0;color:#5c6b84;font-size:12px;">ERA AXIS Competency &copy; 2026 &middot; ERA Technologies</p>
  </td></tr>
</table>
</td></tr></table>
</body>
</html>"""


def _email_detail_row(label, value, is_last=False):
    border = '' if is_last else 'border-bottom:1px solid #ece7dd;'
    return (
        f'<tr>'
        f'<td style="padding:10px 14px;color:#5c6b84;font-size:13px;{border}">{_esc(str(label))}</td>'
        f'<td style="padding:10px 14px;color:#182134;font-size:13px;font-weight:500;{border}">{_esc(str(value))}</td>'
        f'</tr>'
    )


def _email_detail_table(rows):
    """rows: list of (label, value) tuples."""
    html_rows = ''.join(
        _email_detail_row(label, value, is_last=(i == len(rows) - 1))
        for i, (label, value) in enumerate(rows)
    )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border:1px solid #ece7dd;border-radius:8px;overflow:hidden;margin:16px 0 0;">'
        f'{html_rows}</table>'
    )


def _send_login_otp(executive):
    code = _generate_otp_code()
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    LoginOTP.objects.filter(executive=executive, is_used=False).update(is_used=True)
    LoginOTP.objects.create(
        executive=executive,
        code_hash=make_password(code),
        expires_at=expires_at,
    )

    plain = (
        f"Your ERA AXIS one-time password is {code}. "
        f"It expires in {OTP_EXPIRY_MINUTES} minutes."
    )

    body_html = (
        f'<p style="margin:0 0 16px;color:#5c6b84;font-size:14px;line-height:1.6;">'
        f'Use the code below to verify your login. This code expires in {OTP_EXPIRY_MINUTES} minutes.</p>'
        f'<div style="margin:24px 0;text-align:center;padding:20px;background-color:#ece7dd;border-radius:8px;">'
        f'<span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#454285;">{_esc(code)}</span>'
        f'</div>'
        f'<p style="margin:0;color:#5c6b84;font-size:13px;">'
        f'If you didn\'t request this code, you can safely ignore this email.</p>'
    )

    send_mail(
        subject='ERA AXIS Competency - Your Login OTP',
        message=plain,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=[executive.email],
        html_message=_build_email_html('Your Login Code', body_html),
        fail_silently=False,
    )


def _get_logged_in_executive(request):
    executive_id = request.session.get('executive_id')
    if not executive_id:
        return None
    return Executive.objects.filter(id=executive_id).first()


def _get_next_stage_for_executive(executive, active_stage_orders=None, cycle=None):
    if active_stage_orders is None:
        active_stage_orders = _get_active_stage_orders()
    if cycle is None:
        cycle = _get_current_cycle()

    passed_stages = set(
        Assessment.objects.filter(executive=executive, cycle=cycle, passed=True).values_list('stage', flat=True)
    )

    for stage_number in active_stage_orders:
        if stage_number not in passed_stages:
            return stage_number

    return None


def _get_stage_label(stage_number):
    stage_obj = _get_stage_by_order(stage_number)
    if stage_obj:
        return stage_obj.name
    return f"Stage {stage_number}"


def _get_saved_assessment_stage(request, current_cycle, next_stage):
    if request.session.get('assessment_cycle_id') != current_cycle.id:
        return None
    if request.session.get('assessment_stage') != next_stage:
        return None
    if not request.session.get('assessment_question_ids'):
        return None
    if request.session.get('assessment_completed'):
        return None
    return next_stage


def _start_assessment_session(request, stage_number, cycle):
    question_ids = list(
        Question.objects.filter(stage=stage_number)
        .order_by('order', 'id')
        .values_list('id', flat=True)[:QUESTIONS_PER_STAGE]
    )
    random.shuffle(question_ids)

    request.session['assessment_cycle_id'] = cycle.id
    request.session['assessment_stage'] = stage_number
    request.session['assessment_question_ids'] = question_ids
    request.session['assessment_answers'] = []
    request.session['assessment_q_index'] = 0
    request.session['assessment_feedback'] = None
    request.session['assessment_selected_option_id'] = None
    request.session['assessment_completed'] = False
    request.session.pop('assessment_record_id', None)


def _clear_assessment_session(request):
    for key in [
        'assessment_stage',
        'assessment_cycle_id',
        'assessment_question_ids',
        'assessment_answers',
        'assessment_q_index',
        'assessment_feedback',
        'assessment_selected_option_id',
        'assessment_completed',
    ]:
        request.session.pop(key, None)


def _render_assessment_unavailable(request, stage_number, error):
    return render(request, 'assessment/question.html', {
        'question': None,
        'error': error,
        'stage_number': stage_number,
        'stage_label': _get_stage_label(stage_number),
        'question_number': 0,
        'total_questions': 0,
        'feedback': None,
        'selected_option_id': None,
        'assessment_unavailable': True,
    })


def _has_active_assessment_post(request, current_cycle, stage_number):
    return (
        request.method == 'POST'
        and request.session.get('assessment_cycle_id') == current_cycle.id
        and request.session.get('assessment_stage') == stage_number
        and bool(request.session.get('assessment_question_ids'))
        and not request.session.get('assessment_completed')
    )


def _notify_admins_about_completion(assessment, total_questions):
    user_model = get_user_model()
    recipient_list = list(
        user_model.objects.filter(is_superuser=True)
        .exclude(email='')
        .values_list('email', flat=True)
    )

    if not recipient_list:
        return

    executive = assessment.executive
    stage_label = assessment.stage_name or (assessment.stage_ref.name if assessment.stage_ref else f"Stage {assessment.stage}")
    status_label = 'Passed' if assessment.passed else 'Not Passed'
    subject = "ERA AXIS Competency - Executive Completed All Available Stages"

    plain = (
        f"An executive has completed all competency stages.\n\n"
        f"Executive: {executive.name}\n"
        f"Email: {executive.email}\n"
        f"Role: {executive.role}\n"
        f"Final Stage: {stage_label}\n"
        f"Attempt: {assessment.attempt_number}\n"
        f"Score: {assessment.score}%\n"
        f"Correct Answers: {assessment.correct_answers}/{total_questions}\n"
        f"Status: {status_label}\n"
    )

    status_color = '#047857' if assessment.passed else '#dc2626'
    body_html = (
        '<p style="margin:0 0 16px;color:#5c6b84;font-size:14px;line-height:1.6;">'
        'An executive has completed all available competency stages.</p>'
        + _email_detail_table([
            ('Executive', executive.name),
            ('Email', executive.email or '—'),
            ('Role', executive.role),
            ('Final Stage', stage_label),
            ('Attempt', assessment.attempt_number),
            ('Score', f'{assessment.score}%'),
            ('Correct Answers', f'{assessment.correct_answers}/{total_questions}'),
        ])
        + f'<div style="margin:16px 0 0;padding:10px 14px;border-radius:8px;'
          f'background-color:{"#e6f5ef" if assessment.passed else "#fef2f2"};">'
          f'<span style="font-size:13px;font-weight:600;color:{status_color};">'
          f'{_esc(status_label)}</span></div>'
    )

    send_mail(
        subject=subject,
        message=plain,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=recipient_list,
        html_message=_build_email_html('Executive Completed All Stages', body_html),
        fail_silently=True,
    )


def _notify_admins_about_three_failed_attempts(assessment):
    user_model = get_user_model()
    recipient_list = list(
        user_model.objects.filter(is_superuser=True)
        .exclude(email='')
        .values_list('email', flat=True)
    )

    if not recipient_list:
        return

    executive = assessment.executive
    stage_label = assessment.stage_name or (assessment.stage_ref.name if assessment.stage_ref else f"Stage {assessment.stage}")
    subject = f"ERA AXIS Competency - 3 Failed Attempts ({stage_label})"

    plain = (
        f"An executive has reached 3 failed attempts on the same stage.\n\n"
        f"Executive: {executive.name}\n"
        f"Email: {executive.email}\n"
        f"Role: {executive.role}\n"
        f"Stage: {stage_label}\n"
        f"Latest Attempt Number: {assessment.attempt_number}\n"
        f"Latest Score: {assessment.score}%\n"
    )

    body_html = (
        '<div style="margin:0 0 16px;padding:12px 16px;border-radius:8px;'
        'background-color:#fef2f2;border:1px solid #fecaca;">'
        '<p style="margin:0;color:#dc2626;font-size:14px;font-weight:500;">'
        'An executive has reached 3 failed attempts on the same stage.</p></div>'
        + _email_detail_table([
            ('Executive', executive.name),
            ('Email', executive.email or '—'),
            ('Role', executive.role),
            ('Stage', stage_label),
            ('Latest Attempt', assessment.attempt_number),
            ('Latest Score', f'{assessment.score}%'),
        ])
    )

    send_mail(
        subject=subject,
        message=plain,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=recipient_list,
        html_message=_build_email_html(f'3 Failed Attempts — {_esc(stage_label)}', body_html),
        fail_silently=True,
    )


def _notify_executive_about_stage_pass(assessment, total_questions):
    executive = assessment.executive
    if not executive.email:
        return

    stage_label = assessment.stage_name or (assessment.stage_ref.name if assessment.stage_ref else f"Stage {assessment.stage}")
    subject = f"ERA AXIS Competency - You Passed {stage_label}"

    plain = (
        f"Congratulations {executive.name},\n\n"
        f"You passed {stage_label}.\n"
        f"Score: {assessment.score}%\n"
        f"Correct Answers: {assessment.correct_answers}/{total_questions}\n"
        f"Attempt: {assessment.attempt_number}\n\n"
        f"You can now continue with your competency journey."
    )

    body_html = (
        f'<p style="margin:0 0 16px;color:#182134;font-size:15px;line-height:1.6;">'
        f'Congratulations <strong>{_esc(executive.name)}</strong>,</p>'
        f'<div style="margin:0 0 20px;padding:16px;border-radius:8px;background-color:#e6f5ef;text-align:center;">'
        f'<p style="margin:0 0 4px;color:#047857;font-size:16px;font-weight:600;">'
        f'You passed {_esc(stage_label)}</p>'
        f'<p style="margin:0;color:#047857;font-size:28px;font-weight:700;">{assessment.score}%</p></div>'
        + _email_detail_table([
            ('Stage', stage_label),
            ('Correct Answers', f'{assessment.correct_answers}/{total_questions}'),
            ('Attempt', assessment.attempt_number),
        ])
        + '<p style="margin:20px 0 0;color:#5c6b84;font-size:14px;line-height:1.6;">'
          'You can now continue with your competency journey.</p>'
    )

    send_mail(
        subject=subject,
        message=plain,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=[executive.email],
        html_message=_build_email_html(f'You Passed {_esc(stage_label)}', body_html),
        fail_silently=True,
    )

def login_view(request):
    errors = {}

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        name = request.POST.get('name', '').strip()
        role = request.POST.get('role', '').strip()

        if not email:
            errors['email'] = "Email is required"

        executive = None
        if email:
            executive = Executive.objects.filter(email=email).first()

        is_new_registration = executive is None

        if is_new_registration:
            if not name:
                errors['name'] = "Full name is required for first-time registration"
            if not role:
                errors['role'] = "Role is required for first-time registration"

        if not errors:
            if is_new_registration:
                executive = Executive.objects.create(
                    name=name,
                    role=role,
                    email=email,
                    date=timezone.localdate(),
                )

            _send_login_otp(executive)
            request.session['pending_executive_id'] = executive.id

            return redirect('verify_otp')

    return render(request, 'auth/login.html', {'errors': errors})


def verify_otp_view(request):
    pending_executive_id = request.session.get('pending_executive_id')

    if not pending_executive_id:
        return redirect('login')

    executive = get_object_or_404(Executive, id=pending_executive_id)
    errors = {}

    if request.method == 'POST':
        otp_code = request.POST.get('otp', '').strip()

        if not otp_code:
            errors['otp'] = 'OTP is required'
        else:
            otp_entry = LoginOTP.objects.filter(executive=executive, is_used=False).first()

            if otp_entry is None:
                errors['otp'] = 'No active OTP found. Please request a new one.'
            elif otp_entry.is_expired():
                otp_entry.is_used = True
                otp_entry.save(update_fields=['is_used'])
                errors['otp'] = 'OTP has expired. Please request a new one.'
            elif otp_entry.attempts_left == 0:
                otp_entry.is_used = True
                otp_entry.save(update_fields=['is_used'])
                errors['otp'] = 'Too many attempts. Please request a new OTP.'
            elif not check_password(otp_code, otp_entry.code_hash):
                otp_entry.attempts_left -= 1
                if otp_entry.attempts_left == 0:
                    otp_entry.is_used = True
                otp_entry.save(update_fields=['attempts_left', 'is_used'])
                errors['otp'] = 'Invalid OTP. Please try again.'
            else:
                otp_entry.is_used = True
                otp_entry.save(update_fields=['is_used'])

                request.session['executive_id'] = executive.id
                request.session['user'] = {
                    'name': executive.name,
                    'role': executive.role,
                    'date': str(executive.date),
                    'email': executive.email,
                }
                request.session.pop('pending_executive_id', None)
                return redirect('dashboard')

    active_otp = LoginOTP.objects.filter(executive=executive, is_used=False).first()
    otp_expires_at = active_otp.expires_at.isoformat() if active_otp and not active_otp.is_expired() else None
    otp_created_at = active_otp.created_at.isoformat() if active_otp else None

    return render(request, 'verify_otp.html', {
        'errors': errors,
        'email': executive.email,
        'otp_expires_at': otp_expires_at,
        'otp_created_at': otp_created_at,
    })


def resend_otp_view(request):
    pending_executive_id = request.session.get('pending_executive_id')

    if not pending_executive_id:
        return redirect('login')

    executive = get_object_or_404(Executive, id=pending_executive_id)
    _send_login_otp(executive)

    active_otp = LoginOTP.objects.filter(executive=executive, is_used=False).first()
    otp_expires_at = active_otp.expires_at.isoformat() if active_otp and not active_otp.is_expired() else None
    otp_created_at = active_otp.created_at.isoformat() if active_otp else None

    return render(request, 'verify_otp.html', {
        'email': executive.email,
        'info_message': f'A new OTP has been sent to {executive.email}.',
        'otp_expires_at': otp_expires_at,
        'otp_created_at': otp_created_at,
    })

def dashboard(request):
    executive = _get_logged_in_executive(request)

    if not executive:
        return redirect('/')

    current_cycle = _get_current_cycle()
    assessments = Assessment.objects.filter(executive=executive).select_related('stage_ref', 'cycle').order_by('-created_at')
    current_cycle_assessments = assessments.filter(cycle=current_cycle)
    active_stage_orders = _get_active_stage_orders()
    next_stage = _get_next_stage_for_executive(executive, active_stage_orders, current_cycle)
    is_cycle_locked = _is_cycle_locked(current_cycle)
    latest_assessment = current_cycle_assessments.first() or assessments.first()

    total_attempts = current_cycle_assessments.count()
    pass_count = current_cycle_assessments.filter(passed=True).count()
    completed_stage_count = current_cycle_assessments.filter(passed=True).values_list('stage', flat=True).distinct().count()
    overall_average_score = current_cycle_assessments.aggregate(avg=Avg('score'))['avg'] or 0
    overall_pass_rate = (pass_count / total_attempts) * 100 if total_attempts else 0
    can_start_assessment = next_stage is not None and not is_cycle_locked
    is_completed = bool(active_stage_orders) and next_stage is None
    saved_stage = _get_saved_assessment_stage(request, current_cycle, next_stage)

    user = request.session.get('user', {})
    user['name'] = executive.name
    user['role'] = executive.role
    user['email'] = executive.email
    user['date'] = str(executive.date)

    # Group performance history by cycle for structured display
    perf_by_cycle = {}
    for a in assessments[:50]:
        if a.cycle_id not in perf_by_cycle:
            perf_by_cycle[a.cycle_id] = {'cycle': a.cycle, 'assessments': []}
        perf_by_cycle[a.cycle_id]['assessments'].append(a)

    return render(request, 'dashboard.html', {
        'user': user,
        'next_stage': next_stage,
        'next_stage_label': _get_stage_label(next_stage) if next_stage else None,
        'is_completed': is_completed,
        'can_start_assessment': can_start_assessment,
        'is_cycle_locked': is_cycle_locked,
        'has_saved_progress': saved_stage is not None,
        'has_active_stages': bool(active_stage_orders),
        'latest_assessment': latest_assessment,
        'overall_average_score': round(overall_average_score, 2),
        'overall_pass_rate': round(overall_pass_rate, 2),
        'total_attempts': total_attempts,
        'completed_stage_count': completed_stage_count,
        'stage_count': len(active_stage_orders),
        'current_cycle': current_cycle,
        'performance_by_cycle': list(perf_by_cycle.values()),
    })

def logout_view(request):
    request.session.flush()
    return redirect('/')


def start_assessment(request):
    executive = _get_logged_in_executive(request)

    if not executive:
        return redirect('login')

    current_cycle = _get_current_cycle()
    next_stage = _get_next_stage_for_executive(executive, cycle=current_cycle)
    if next_stage is None:
        return redirect('dashboard')
    if _is_cycle_locked(current_cycle) and not _has_active_assessment_post(request, current_cycle, next_stage):
        return _render_assessment_unavailable(
            request,
            next_stage,
            f'{current_cycle.name} is currently locked. New attempts and saved progress are paused until admin unlocks the cycle.',
        )

    error = None

    should_reset = (
        request.GET.get('restart') == '1'
        or request.session.get('assessment_cycle_id') != current_cycle.id
        or request.session.get('assessment_stage') != next_stage
        or not request.session.get('assessment_question_ids')
    )
    if should_reset:
        _start_assessment_session(request, next_stage, current_cycle)

    stage_number = request.session.get('assessment_stage', next_stage)
    question_ids = request.session.get('assessment_question_ids', [])
    total_questions = len(question_ids)
    index = request.session.get('assessment_q_index', 0)
    answers = request.session.get('assessment_answers', [])
    feedback = request.session.get('assessment_feedback')
    selected_option_id = request.session.get('assessment_selected_option_id')

    if total_questions and index >= total_questions and len(answers) != total_questions:
        _clear_assessment_session(request)
        return redirect('dashboard')

    if total_questions == 0:
        return _render_assessment_unavailable(
            request,
            stage_number,
            f"{_get_stage_label(stage_number)} does not have any questions available yet.",
        )

    if request.method == 'POST':
        action = request.POST.get('action', '')
        submitted_option_id = request.POST.get('option')

        if action == 'save_exit':
            request.session['assessment_feedback'] = None
            request.session['assessment_selected_option_id'] = None
            return redirect('dashboard')

        should_advance = action == 'next'
        # Some browsers/client scripts can submit without button name/value.
        # When feedback is present and no option is being submitted, treat it as Next.
        if not should_advance and feedback and not submitted_option_id:
            should_advance = True

        if should_advance:
            if not feedback:
                error = 'Please submit an answer first.'
            else:
                index += 1
                request.session['assessment_q_index'] = index
                request.session['assessment_feedback'] = None
                request.session['assessment_selected_option_id'] = None

                if index >= total_questions:
                    request.session['assessment_completed'] = True
                    return redirect('result')

                return redirect('start_assessment')
        else:
            if feedback:
                error = 'Click Next to continue.'
            else:
                if not submitted_option_id:
                    error = 'Please select an option before continuing.'
                else:
                    try:
                        selected_option = Option.objects.select_related('question').get(id=submitted_option_id)
                    except Option.DoesNotExist:
                        selected_option = None

                    if selected_option is None:
                        error = 'Selected option is invalid.'
                    else:
                        current_question_id = question_ids[index]
                        if selected_option.question_id != current_question_id:
                            error = 'Selected option does not match this question.'
                        else:
                            answers.append(selected_option.id)
                            request.session['assessment_answers'] = answers

                            selected_option_id = selected_option.id
                            request.session['assessment_selected_option_id'] = selected_option.id

                            request.session['assessment_feedback'] = {
                                'is_correct': selected_option.is_correct,
                                'message': 'Correct answer.' if selected_option.is_correct else 'Incorrect answer.',
                                'explanation': selected_option.question.explanation,
                            }

                            feedback = request.session['assessment_feedback']

    if index >= total_questions:
        request.session['assessment_completed'] = True
        return redirect('result')

    question = Question.objects.prefetch_related('options').get(id=question_ids[index])

    return render(request, 'assessment/question.html', {
        'question': question,
        'error': error,
        'stage_number': stage_number,
        'stage_label': _get_stage_label(stage_number),
        'question_number': index + 1,
        'total_questions': total_questions,
        'feedback': feedback,
        'selected_option_id': selected_option_id,
        'is_last_question': index + 1 == total_questions,
        'assessment_unavailable': False,
    })


def result(request):
    executive = _get_logged_in_executive(request)
    if not executive:
        return redirect('login')
    current_cycle = _get_current_cycle()

    if not request.session.get('assessment_completed') and not request.session.get('assessment_record_id'):
        return redirect('start_assessment')

    existing_assessment_id = request.session.get('assessment_record_id')
    if existing_assessment_id:
        assessment = Assessment.objects.filter(id=existing_assessment_id, executive=executive).first()
        if assessment:
            total_answered = assessment.total_questions or assessment.responses.count()
            return render(request, 'result.html', {
                'score': assessment.score,
                'correct': assessment.correct_answers,
                'total': total_answered,
                'passed': assessment.passed,
                'stage_number': assessment.stage,
                'stage_label': assessment.stage_name or _get_stage_label(assessment.stage),
                'next_stage': _get_next_stage_for_executive(executive, cycle=current_cycle),
            })

    stage_number = request.session.get('assessment_stage')
    question_ids = request.session.get('assessment_question_ids', [])
    answer_ids = request.session.get('assessment_answers', [])

    if not stage_number or not question_ids or len(answer_ids) != len(question_ids):
        _clear_assessment_session(request)
        request.session.pop('assessment_record_id', None)
        return redirect('dashboard')

    options_by_id = {
        option.id: option
        for option in Option.objects.filter(id__in=answer_ids).select_related('question')
    }

    correct_count = 0
    responses_to_create = []

    for idx, question_id in enumerate(question_ids):
        option = options_by_id.get(answer_ids[idx])
        if option is None or option.question_id != question_id:
            return redirect('start_assessment')

        if option.is_correct:
            correct_count += 1

        responses_to_create.append({
            'question_id': question_id,
            'selected_option_id': option.id,
            'is_correct': option.is_correct,
        })

    total = len(question_ids)
    score = round((correct_count / total) * 100, 2) if total else 0
    passed = score >= PASSING_SCORE_PERCENT

    stage_ref = _get_stage_by_order(stage_number)
    stage_label = stage_ref.name if stage_ref else _get_stage_label(stage_number)
    attempt_number = Assessment.objects.filter(executive=executive, cycle=current_cycle, stage=stage_number).count() + 1
    assessment = Assessment.objects.create(
        executive=executive,
        cycle=current_cycle,
        stage=stage_number,
        stage_name=stage_label,
        stage_ref=stage_ref,
        attempt_number=attempt_number,
        correct_answers=correct_count,
        total_questions=total,
        score=score,
        passed=passed,
    )

    Response.objects.bulk_create([
        Response(
            assessment=assessment,
            question_id=item['question_id'],
            selected_option_id=item['selected_option_id'],
            is_correct=item['is_correct'],
        )
        for item in responses_to_create
    ])

    active_stage_orders = _get_active_stage_orders()
    if active_stage_orders and assessment.stage == active_stage_orders[-1]:
        _notify_admins_about_completion(assessment, total)

    if assessment.passed:
        _notify_executive_about_stage_pass(assessment, total)
    else:
        failed_attempts = Assessment.objects.filter(
            executive=executive,
            stage=assessment.stage,
            passed=False,
        ).count()
        if failed_attempts == 3:
            _notify_admins_about_three_failed_attempts(assessment)

    request.session['assessment_record_id'] = assessment.id
    _clear_assessment_session(request)

    return render(request, 'result.html', {
        'score': assessment.score,
        'correct': assessment.correct_answers,
        'total': total,
        'passed': assessment.passed,
        'stage_number': assessment.stage,
        'stage_label': assessment.stage_name or _get_stage_label(assessment.stage),
        'next_stage': _get_next_stage_for_executive(executive, cycle=current_cycle),
    })
