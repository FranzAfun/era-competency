from django.db import models


class Executive(models.Model):
	name = models.CharField(max_length=255)
	role = models.CharField(max_length=100)
	date = models.DateField()
	created_at = models.DateTimeField(auto_now_add=True)


class Question(models.Model):
	text = models.TextField()
	stage = models.IntegerField()
	order = models.IntegerField()
	created_at = models.DateTimeField(auto_now_add=True)


class Option(models.Model):
	question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
	text = models.CharField(max_length=255)
	is_correct = models.BooleanField(default=False)


class Assessment(models.Model):
	executive = models.ForeignKey(Executive, on_delete=models.CASCADE)
	stage = models.IntegerField()
	score = models.FloatField(default=0)
	passed = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)


class Response(models.Model):
	assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='responses')
	question = models.ForeignKey(Question, on_delete=models.CASCADE)
	selected_option = models.ForeignKey(Option, on_delete=models.CASCADE)
	is_correct = models.BooleanField()
