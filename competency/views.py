from django.shortcuts import render, redirect
from .models import Question, Option

def login_view(request):
    errors = {}
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        role = request.POST.get('role', '').strip()
        date = request.POST.get('date', '').strip()

        if not name:
            errors['name'] = "Full name is required"
        if not role:
            errors['role'] = "Role is required"
        if not date:
            errors['date'] = "Date is required"

        if not errors:
            request.session['user'] = {
                'name': name,
                'role': role,
                'date': date
            }
            return redirect('dashboard')
            
    return render(request, 'auth/login.html', {'errors': errors})

def dashboard(request):
    user = request.session.get('user')

    if not user:
        return redirect('/')

    return render(request, 'dashboard.html', {'user': user})

def logout_view(request):
    request.session.flush()
    return redirect('/')

def start_assessment(request):
    error = None

    if request.method == "POST":
        selected_option_id = request.POST.get('option')

        if selected_option_id:
            # store selected answers in session
            answers = request.session.get('answers', [])
            answers.append(selected_option_id)
            request.session['answers'] = answers

            # get current question index
            current_index = request.session.get('q_index', 0)
            current_index += 1
            request.session['q_index'] = current_index
        else:
            error = "Please select an option before continuing."
    else:
        # initialize session
        request.session['q_index'] = 0
        request.session['answers'] = []

    # get all questions for stage 1
    questions = Question.objects.filter(stage=1).order_by('order')

    index = request.session.get('q_index', 0)

    if index >= questions.count():
        return redirect('/result/')  # placeholder

    question = questions[index]

    return render(request, 'assessment/question.html', {
        'question': question,
        'error': error,
    })


def result(request):
    answers = request.session.get('answers', [])

    correct_count = 0

    for option_id in answers:
        try:
            option = Option.objects.get(id=option_id)
            if option.is_correct:
                correct_count += 1
        except Option.DoesNotExist:
            continue

    total = len(answers)

    score = 0
    if total > 0:
        score = (correct_count / total) * 100

    return render(request, 'result.html', {
        'score': score,
        'correct': correct_count,
        'total': total
    })
