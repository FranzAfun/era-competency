from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import Assessment, AssessmentCycle, Executive, Option, Question, Response, Stage


class AssessmentFlowTests(TestCase):
	def setUp(self):
		self.current_cycle = AssessmentCycle.objects.get(is_current=True)
		self.stage = Stage.objects.create(name='Stage 1', order=1, is_active=True)
		self.executive = Executive.objects.create(
			name='Test User',
			role='Sales',
			email='test@example.com',
			date=date.today(),
		)

		for index in range(1, 26):
			question = Question.objects.create(
				text=f'Question {index}',
				stage=1,
				stage_ref=self.stage,
				order=index,
			)
			Option.objects.create(question=question, text='Correct', is_correct=True)
			Option.objects.create(question=question, text='Incorrect 1', is_correct=False)
			Option.objects.create(question=question, text='Incorrect 2', is_correct=False)
			Option.objects.create(question=question, text='Incorrect 3', is_correct=False)

		session = self.client.session
		session['executive_id'] = self.executive.id
		session['user'] = {
			'name': self.executive.name,
			'role': self.executive.role,
			'email': self.executive.email,
			'date': str(self.executive.date),
		}
		session.save()

	def test_missing_action_after_feedback_advances_to_next_question(self):
		response = self.client.get(reverse('start_assessment') + '?restart=1')
		self.assertEqual(response.status_code, 200)

		session = self.client.session
		first_question_id = session['assessment_question_ids'][0]
		option = Option.objects.filter(question_id=first_question_id, is_correct=True).first()
		self.assertIsNotNone(option)

		submit_response = self.client.post(reverse('start_assessment'), {
			'action': 'submit',
			'option': option.id,
		})
		self.assertEqual(submit_response.status_code, 200)
		self.assertContains(submit_response, 'Correct answer.')

		# Simulate a client-side submit where action button value is not sent.
		next_response = self.client.post(reverse('start_assessment'), {})
		self.assertEqual(next_response.status_code, 302)
		self.assertEqual(next_response.url, reverse('start_assessment'))

		session = self.client.session
		self.assertEqual(session['assessment_q_index'], 1)
		self.assertIsNone(session['assessment_feedback'])

	def test_stage_with_fewer_than_25_questions_can_start(self):
		Question.objects.filter(stage_ref=self.stage, order__gt=22).delete()

		response = self.client.get(reverse('start_assessment') + '?restart=1')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Question 1 of 22')
		self.assertNotContains(response, 'requires 25 questions')

		session = self.client.session
		self.assertEqual(len(session['assessment_question_ids']), 22)
		self.assertEqual(session['assessment_cycle_id'], self.current_cycle.id)

	def test_result_uses_dynamic_total_for_partial_stage(self):
		Question.objects.filter(stage_ref=self.stage, order__gt=22).delete()

		response = self.client.get(reverse('start_assessment') + '?restart=1')
		self.assertEqual(response.status_code, 200)

		session = self.client.session
		question_ids = list(session['assessment_question_ids'])
		answer_ids = []

		for question_id in question_ids:
			option = Option.objects.get(question_id=question_id, is_correct=True)
			answer_ids.append(option.id)

		session['assessment_answers'] = answer_ids
		session['assessment_q_index'] = len(question_ids)
		session['assessment_completed'] = True
		session.save()

		result_response = self.client.get(reverse('result'))

		self.assertEqual(result_response.status_code, 200)
		self.assertContains(result_response, 'Total: <span class="text-white">22</span>', html=True)
		self.assertContains(result_response, 'Score: <span class="text-white">100.0%</span>', html=True)

	def test_existing_result_page_uses_saved_response_count(self):
		assessment = Assessment.objects.create(
			executive=self.executive,
			cycle=self.current_cycle,
			stage=1,
			stage_name=self.stage.name,
			stage_ref=self.stage,
			attempt_number=1,
			correct_answers=3,
			total_questions=4,
			score=75.0,
			passed=True,
		)

		questions = list(Question.objects.filter(stage_ref=self.stage).order_by('order')[:4])
		for index, question in enumerate(questions, start=1):
			selected_option = question.options.filter(is_correct=index <= 3).first()
			Response.objects.create(
				assessment=assessment,
				question=question,
				selected_option=selected_option,
				is_correct=selected_option.is_correct,
			)

		session = self.client.session
		session['assessment_record_id'] = assessment.id
		session.save()

		response = self.client.get(reverse('result'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Total: <span class="text-white">4</span>', html=True)

	def test_existing_result_page_keeps_total_after_stage_questions_are_deleted(self):
		assessment = Assessment.objects.create(
			executive=self.executive,
			cycle=self.current_cycle,
			stage=1,
			stage_name=self.stage.name,
			stage_ref=self.stage,
			attempt_number=1,
			correct_answers=2,
			total_questions=3,
			score=66.67,
			passed=False,
		)

		questions = list(Question.objects.filter(stage_ref=self.stage).order_by('order')[:3])
		for index, question in enumerate(questions, start=1):
			selected_option = question.options.filter(is_correct=index <= 2).first()
			Response.objects.create(
				assessment=assessment,
				question=question,
				selected_option=selected_option,
				is_correct=selected_option.is_correct,
			)

		Question.objects.filter(stage_ref=self.stage).delete()

		session = self.client.session
		session['assessment_record_id'] = assessment.id
		session.save()

		response = self.client.get(reverse('result'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Total: <span class="text-white">3</span>', html=True)

	def test_admin_completion_email_is_sent_after_last_active_stage(self):
		stage_two = Stage.objects.create(name='Stage 2', order=2, is_active=True)
		Stage.objects.create(name='Stage 4', order=4, is_active=False)

		for index in range(1, 4):
			question = Question.objects.create(
				text=f'Stage 2 Question {index}',
				stage=2,
				stage_ref=stage_two,
				order=index,
			)
			Option.objects.create(question=question, text='Correct', is_correct=True)
			Option.objects.create(question=question, text='Incorrect 1', is_correct=False)
			Option.objects.create(question=question, text='Incorrect 2', is_correct=False)
			Option.objects.create(question=question, text='Incorrect 3', is_correct=False)

		user_model = get_user_model()
		user_model.objects.create_superuser(
			username='superadmin',
			email='admin@example.com',
			password='secret123',
		)

		Assessment.objects.create(
			executive=self.executive,
			cycle=self.current_cycle,
			stage=1,
			stage_name=self.stage.name,
			stage_ref=self.stage,
			attempt_number=1,
			correct_answers=25,
			total_questions=25,
			score=100,
			passed=True,
		)

		session = self.client.session
		session['assessment_stage'] = 2
		session['assessment_question_ids'] = list(
			Question.objects.filter(stage_ref=stage_two).order_by('order').values_list('id', flat=True)
		)
		session['assessment_answers'] = list(
			Option.objects.filter(question__stage_ref=stage_two, is_correct=True)
			.order_by('question__order')
			.values_list('id', flat=True)
		)
		session['assessment_q_index'] = 3
		session['assessment_completed'] = True
		session.save()

		response = self.client.get(reverse('result'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(mail.outbox), 2)
		self.assertEqual(mail.outbox[0].to, ['admin@example.com'])
		self.assertIn('Completed All Available Stages', mail.outbox[0].subject)

	def test_save_and_exit_keeps_progress_for_dashboard_resume(self):
		response = self.client.get(reverse('start_assessment') + '?restart=1')
		self.assertEqual(response.status_code, 200)

		session = self.client.session
		first_question_id = session['assessment_question_ids'][0]
		option = Option.objects.filter(question_id=first_question_id, is_correct=True).first()
		self.assertIsNotNone(option)

		self.client.post(reverse('start_assessment'), {
			'action': 'submit',
			'option': option.id,
		})
		save_exit_response = self.client.post(reverse('start_assessment'), {
			'action': 'save_exit',
		})

		self.assertEqual(save_exit_response.status_code, 302)
		self.assertEqual(save_exit_response.url, reverse('dashboard'))

		dashboard_response = self.client.get(reverse('dashboard'))
		self.assertContains(dashboard_response, 'Continue')

	def test_start_new_cycle_preserves_history_and_restarts_progression(self):
		Assessment.objects.create(
			executive=self.executive,
			cycle=self.current_cycle,
			stage=1,
			stage_name=self.stage.name,
			stage_ref=self.stage,
			attempt_number=1,
			correct_answers=25,
			total_questions=25,
			score=100,
			passed=True,
		)

		user_model = get_user_model()
		admin_user = user_model.objects.create_user(
			username='cycleadmin',
			password='secret123',
			is_staff=True,
		)
		self.client.force_login(admin_user)

		response = self.client.post(reverse('admin_portal_reset_cycle'))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(Assessment.objects.count(), 1)
		self.assertEqual(AssessmentCycle.objects.filter(is_current=True).count(), 1)
		new_cycle = AssessmentCycle.objects.get(is_current=True)
		self.assertNotEqual(new_cycle.id, self.current_cycle.id)

		self.client.logout()
		session = self.client.session
		session['executive_id'] = self.executive.id
		session['user'] = {
			'name': self.executive.name,
			'role': self.executive.role,
			'email': self.executive.email,
			'date': str(self.executive.date),
		}
		session.save()

		dashboard_response = self.client.get(reverse('dashboard'))
		self.assertContains(dashboard_response, 'Assessment 2')
		self.assertContains(dashboard_response, 'Start')


class AdminStageManagementTests(TestCase):
	def setUp(self):
		self.current_cycle = AssessmentCycle.objects.get(is_current=True)
		self.stage = Stage.objects.create(name='Stage 1', order=1, is_active=True)
		for index in range(1, 4):
			question = Question.objects.create(
				text=f'Question {index}',
				stage=1,
				stage_ref=self.stage,
				order=index,
			)
			Option.objects.create(question=question, text='Correct', is_correct=True)
			Option.objects.create(question=question, text='Incorrect 1', is_correct=False)
			Option.objects.create(question=question, text='Incorrect 2', is_correct=False)
			Option.objects.create(question=question, text='Incorrect 3', is_correct=False)

		user_model = get_user_model()
		self.admin_user = user_model.objects.create_user(
			username='admin',
			password='secret123',
			is_staff=True,
		)
		self.client.force_login(self.admin_user)

	def test_admin_can_update_stage_name_and_status(self):
		response = self.client.post(reverse('admin_portal_stages'), {
			'edit_stage_id': self.stage.id,
			'name': 'Updated Stage Name',
			'order': 1,
			# omit is_active to simulate turning it off
		})

		self.assertEqual(response.status_code, 302)
		self.stage.refresh_from_db()
		self.assertEqual(self.stage.name, 'Updated Stage Name')
		self.assertFalse(self.stage.is_active)

	def test_admin_can_change_stage_order_when_no_assessments_exist(self):
		response = self.client.post(reverse('admin_portal_stages'), {
			'edit_stage_id': self.stage.id,
			'name': self.stage.name,
			'order': 2,
			'is_active': 'on',
		})

		self.assertEqual(response.status_code, 302)
		self.stage.refresh_from_db()
		self.assertEqual(self.stage.order, 2)
		self.assertEqual(
			set(Question.objects.filter(stage_ref=self.stage).values_list('stage', flat=True)),
			{2},
		)

	def test_stage_order_change_is_blocked_when_assessments_exist(self):
		executive = Executive.objects.create(
			name='Stage History User',
			role='Manager',
			email='history@example.com',
			date=date.today(),
		)
		Assessment.objects.create(
			executive=executive,
			cycle=self.current_cycle,
			stage=1,
			stage_name=self.stage.name,
			stage_ref=self.stage,
			attempt_number=1,
			correct_answers=2,
			total_questions=3,
			score=66.67,
			passed=False,
		)

		response = self.client.post(reverse('admin_portal_stages'), {
			'edit_stage_id': self.stage.id,
			'name': 'Still Stage 1',
			'order': 2,
			'is_active': 'on',
		}, follow=True)

		self.assertEqual(response.status_code, 200)
		self.stage.refresh_from_db()
		self.assertEqual(self.stage.order, 1)
		self.assertContains(response, 'already has assessment history')

	def test_admin_can_clear_all_questions_from_a_stage(self):
		response = self.client.post(reverse('admin_portal_clear_stage_questions', args=[self.stage.id]))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('admin_portal_stages'))
		self.assertEqual(Question.objects.filter(stage_ref=self.stage).count(), 0)

	def test_clear_stage_reports_when_nothing_is_available(self):
		Question.objects.filter(stage_ref=self.stage).delete()

		response = self.client.post(reverse('admin_portal_clear_stage_questions', args=[self.stage.id]), follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'does not have any questions to clear')

	def test_admin_can_delete_stage_without_assessment_history(self):
		Question.objects.filter(stage_ref=self.stage).delete()

		response = self.client.post(reverse('admin_portal_delete_stage', args=[self.stage.id]))

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Stage.objects.filter(id=self.stage.id).exists())
		self.assertEqual(Question.objects.filter(stage_ref=self.stage).count(), 0)

	def test_stage_delete_is_blocked_when_questions_still_exist(self):
		response = self.client.post(reverse('admin_portal_delete_stage', args=[self.stage.id]), follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(Stage.objects.filter(id=self.stage.id).exists())
		self.assertContains(response, 'still has questions')

	def test_stage_delete_is_blocked_when_assessments_exist(self):
		executive = Executive.objects.create(
			name='Delete History User',
			role='Manager',
			email='delete-history@example.com',
			date=date.today(),
		)
		Assessment.objects.create(
			executive=executive,
			cycle=self.current_cycle,
			stage=1,
			stage_name=self.stage.name,
			stage_ref=self.stage,
			attempt_number=1,
			correct_answers=3,
			total_questions=3,
			score=100,
			passed=True,
		)
		Question.objects.filter(stage_ref=self.stage).delete()

		response = self.client.post(reverse('admin_portal_delete_stage', args=[self.stage.id]), follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(Stage.objects.filter(id=self.stage.id).exists())
		self.assertContains(response, 'cannot be deleted')
