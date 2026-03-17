from django.contrib import admin
from .models import Question, Option, Executive, Assessment, Response


class OptionInline(admin.TabularInline):
	model = Option
	extra = 4


class QuestionAdmin(admin.ModelAdmin):
	list_display = ('id', 'text', 'stage')
	list_filter = ('stage',)
	search_fields = ('text',)
	inlines = [OptionInline]

admin.site.register(Question, QuestionAdmin)
admin.site.register(Executive)
admin.site.register(Assessment)
admin.site.register(Response)
