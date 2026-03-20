import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Assessment, Executive, LoginOTP, Option, Question, Response, Stage


OTP_EXPIRY_MINUTES = 10
TOTAL_STAGES = 4
QUESTIONS_PER_STAGE = 25
PASSING_SCORE_PERCENT = 70


def _generate_otp_code():
    return f"{random.randint(100000, 999999)}"


def _send_login_otp(executive):
    code = _generate_otp_code()
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    LoginOTP.objects.filter(executive=executive, is_used=False).update(is_used=True)
    LoginOTP.objects.create(
        executive=executive,
        code_hash=make_password(code),
        expires_at=expires_at,
    )

    send_mail(
        subject='ERA AXIS Competency - Your Login OTP',
        message=(
            f"Your ERA AXIS one-time password is {code}. "
            f"It expires in {OTP_EXPIRY_MINUTES} minutes."
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=[executive.email],
        fail_silently=False,
    )


def _get_logged_in_executive(request):
    executive_id = request.session.get('executive_id')
    if not executive_id:
        return None
    return Executive.objects.filter(id=executive_id).first()


def _get_next_stage_for_executive(executive):
    passed_stages = set(
        Assessment.objects.filter(executive=executive, passed=True).values_list('stage', flat=True)
    )

    for stage_number in range(1, TOTAL_STAGES + 1):
        if stage_number not in passed_stages:
            return stage_number

    return None


def _get_stage_label(stage_number):
    stage_obj = Stage.objects.filter(order=stage_number, is_active=True).first()
    if stage_obj:
        return stage_obj.name
    return f"Stage {stage_number}"


def _start_assessment_session(request, stage_number):
    question_ids = list(
        Question.objects.filter(stage=stage_number)
        .order_by('order', 'id')
        .values_list('id', flat=True)[:QUESTIONS_PER_STAGE]
    )
    random.shuffle(question_ids)

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
        'assessment_question_ids',
        'assessment_answers',
        'assessment_q_index',
        'assessment_feedback',
        'assessment_selected_option_id',
        'assessment_completed',
    ]:
        request.session.pop(key, None)


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
    stage_label = assessment.stage_ref.name if assessment.stage_ref else f"Stage {assessment.stage}"
    subject = "ERA AXIS Competency - Executive Completed All 4 Stages"
    message = (
        f"An executive has completed all competency stages.\n\n"
        f"Executive: {executive.name}\n"
        f"Email: {executive.email}\n"
        f"Role: {executive.role}\n"
        f"Final Stage: {stage_label}\n"
        f"Attempt: {assessment.attempt_number}\n"
        f"Score: {assessment.score}%\n"
        f"Correct Answers: {assessment.correct_answers}/{total_questions}\n"
        f"Status: {'Passed' if assessment.passed else 'Not Passed'}\n"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=recipient_list,
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

    return render(request, 'verify_otp.html', {
        'errors': errors,
        'email': executive.email,
    })


def resend_otp_view(request):
    pending_executive_id = request.session.get('pending_executive_id')

    if not pending_executive_id:
        return redirect('login')

    executive = get_object_or_404(Executive, id=pending_executive_id)
    _send_login_otp(executive)

    return render(request, 'verify_otp.html', {
        'email': executive.email,
        'info_message': f'A new OTP has been sent to {executive.email}.',
    })

def dashboard(request):
    executive = _get_logged_in_executive(request)

    if not executive:
        return redirect('/')

    assessments = Assessment.objects.filter(executive=executive).select_related('stage_ref').order_by('-created_at')
    next_stage = _get_next_stage_for_executive(executive)
    latest_assessment = assessments.first()

    total_attempts = assessments.count()
    pass_count = assessments.filter(passed=True).count()
    completed_stage_count = assessments.filter(passed=True).values_list('stage', flat=True).distinct().count()
    overall_average_score = assessments.aggregate(avg=Avg('score'))['avg'] or 0
    overall_pass_rate = (pass_count / total_attempts) * 100 if total_attempts else 0

    user = request.session.get('user', {})
    user['name'] = executive.name
    user['role'] = executive.role
    user['email'] = executive.email
    user['date'] = str(executive.date)

    return render(request, 'dashboard.html', {
        'user': user,
        'next_stage': next_stage,
        'next_stage_label': _get_stage_label(next_stage) if next_stage else None,
        'is_completed': next_stage is None,
        'latest_assessment': latest_assessment,
        'overall_average_score': round(overall_average_score, 2),
        'overall_pass_rate': round(overall_pass_rate, 2),
        'total_attempts': total_attempts,
        'completed_stage_count': completed_stage_count,
        'performance_history': assessments[:10],
    })

def logout_view(request):
    request.session.flush()
    return redirect('/')


def start_assessment(request):
    executive = _get_logged_in_executive(request)

    if not executive:
        return redirect('login')

    next_stage = _get_next_stage_for_executive(executive)
    if next_stage is None:
        return redirect('dashboard')

    error = None

    should_reset = (
        request.GET.get('restart') == '1'
        or request.session.get('assessment_stage') != next_stage
        or not request.session.get('assessment_question_ids')
    )
    if should_reset:
        _start_assessment_session(request, next_stage)

    stage_number = request.session.get('assessment_stage', next_stage)
    question_ids = request.session.get('assessment_question_ids', [])
    total_questions = len(question_ids)
    index = request.session.get('assessment_q_index', 0)
    answers = request.session.get('assessment_answers', [])
    feedback = request.session.get('assessment_feedback')
    selected_option_id = request.session.get('assessment_selected_option_id')

    if total_questions < QUESTIONS_PER_STAGE:
        return render(request, 'assessment/question.html', {
            'question': None,
            'error': (
                f"{_get_stage_label(stage_number)} requires {QUESTIONS_PER_STAGE} questions. "
                f"Only {total_questions} found."
            ),
            'stage_number': stage_number,
            'stage_label': _get_stage_label(stage_number),
            'question_number': 0,
            'total_questions': QUESTIONS_PER_STAGE,
            'feedback': None,
            'selected_option_id': None,
            'assessment_unavailable': True,
        })

    if request.method == 'POST':
        action = request.POST.get('action', '')
        submitted_option_id = request.POST.get('option')

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

    if not request.session.get('assessment_completed') and not request.session.get('assessment_record_id'):
        return redirect('start_assessment')

    existing_assessment_id = request.session.get('assessment_record_id')
    if existing_assessment_id:
        assessment = Assessment.objects.filter(id=existing_assessment_id, executive=executive).first()
        if assessment:
            return render(request, 'result.html', {
                'score': assessment.score,
                'correct': assessment.correct_answers,
                'total': QUESTIONS_PER_STAGE,
                'passed': assessment.passed,
                'stage_number': assessment.stage,
                'stage_label': _get_stage_label(assessment.stage),
                'next_stage': _get_next_stage_for_executive(executive),
            })

    stage_number = request.session.get('assessment_stage')
    question_ids = request.session.get('assessment_question_ids', [])
    answer_ids = request.session.get('assessment_answers', [])

    if not stage_number or not question_ids or len(answer_ids) != len(question_ids):
        return redirect('start_assessment')

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

    stage_ref = Stage.objects.filter(order=stage_number, is_active=True).first()
    attempt_number = Assessment.objects.filter(executive=executive, stage=stage_number).count() + 1
    assessment = Assessment.objects.create(
        executive=executive,
        stage=stage_number,
        stage_ref=stage_ref,
        attempt_number=attempt_number,
        correct_answers=correct_count,
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

    if assessment.stage == TOTAL_STAGES:
        _notify_admins_about_completion(assessment, total)

    request.session['assessment_record_id'] = assessment.id
    _clear_assessment_session(request)

    return render(request, 'result.html', {
        'score': assessment.score,
        'correct': assessment.correct_answers,
        'total': total,
        'passed': assessment.passed,
        'stage_number': assessment.stage,
        'stage_label': _get_stage_label(assessment.stage),
        'next_stage': _get_next_stage_for_executive(executive),
    })
