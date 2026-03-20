from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import Executive, Option, Question, Stage


class AssessmentFlowTests(TestCase):
	def setUp(self):
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
