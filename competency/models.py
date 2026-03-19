from django.db import models
from django.utils import timezone


class Stage(models.Model):
	name = models.CharField(max_length=120)
	order = models.PositiveSmallIntegerField(unique=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['order']

	def __str__(self):
		return f"Stage {self.order}: {self.name}"


class Executive(models.Model):
	name = models.CharField(max_length=255)
	role = models.CharField(max_length=100)
	email = models.EmailField(unique=True, null=True, blank=True)
	date = models.DateField()
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name


class Question(models.Model):
	text = models.TextField()
	stage = models.IntegerField()
	stage_ref = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
	order = models.IntegerField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['stage', 'order', 'id']
		constraints = [
			models.CheckConstraint(
				condition=models.Q(order__gte=1) & models.Q(order__lte=25),
				name='question_order_between_1_and_25',
			),
			models.UniqueConstraint(
				fields=['stage_ref', 'order'],
				condition=models.Q(stage_ref__isnull=False),
				name='unique_stage_ref_question_order',
			),
		]


class Option(models.Model):
	question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
	text = models.CharField(max_length=255)
	is_correct = models.BooleanField(default=False)


class Assessment(models.Model):
	executive = models.ForeignKey(Executive, on_delete=models.CASCADE)
	stage = models.IntegerField()
	stage_ref = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessments')
	attempt_number = models.PositiveIntegerField(default=1)
	correct_answers = models.PositiveIntegerField(default=0)
	score = models.FloatField(default=0)
	passed = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)


class Response(models.Model):
	assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='responses')
	question = models.ForeignKey(Question, on_delete=models.CASCADE)
	selected_option = models.ForeignKey(Option, on_delete=models.CASCADE)
	is_correct = models.BooleanField()


class LoginOTP(models.Model):
	executive = models.ForeignKey(Executive, on_delete=models.CASCADE, related_name='login_otps')
	code_hash = models.CharField(max_length=255)
	expires_at = models.DateTimeField()
	is_used = models.BooleanField(default=False)
	attempts_left = models.PositiveSmallIntegerField(default=5)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def is_expired(self):
		return timezone.now() >= self.expires_at
