from django.contrib import admin
from .models import Question, Option, Executive, Assessment, Response, Stage, LoginOTP


class OptionInline(admin.TabularInline):
	model = Option
	extra = 4


class QuestionAdmin(admin.ModelAdmin):
	list_display = ('id', 'text', 'stage', 'stage_ref', 'order')
	list_filter = ('stage', 'stage_ref')
	search_fields = ('text',)
	inlines = [OptionInline]


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
	list_display = ('order', 'name', 'is_active', 'created_at')
	list_filter = ('is_active',)
	search_fields = ('name',)
	ordering = ('order',)


@admin.register(Executive)
class ExecutiveAdmin(admin.ModelAdmin):
	list_display = ('id', 'name', 'email', 'role', 'date', 'created_at')
	search_fields = ('name', 'email', 'role')
	list_filter = ('role',)


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
	list_display = ('id', 'executive', 'stage', 'stage_ref', 'attempt_number', 'correct_answers', 'score', 'passed', 'created_at')
	list_filter = ('passed', 'stage', 'stage_ref')
	search_fields = ('executive__name', 'executive__email')


@admin.register(LoginOTP)
class LoginOTPAdmin(admin.ModelAdmin):
	list_display = ('id', 'executive', 'expires_at', 'is_used', 'attempts_left', 'created_at')
	list_filter = ('is_used',)
	search_fields = ('executive__name', 'executive__email')


admin.site.register(Question, QuestionAdmin)
admin.site.register(Response)
