from django.db import migrations, models


def backfill_total_questions(apps, schema_editor):
    Assessment = apps.get_model('competency', 'Assessment')
    Response = apps.get_model('competency', 'Response')

    response_counts = {}
    for row in Response.objects.values('assessment_id').annotate(total=models.Count('id')):
        response_counts[row['assessment_id']] = row['total']

    for assessment in Assessment.objects.all().iterator():
        total_questions = response_counts.get(assessment.id, 0)
        if assessment.total_questions != total_questions:
            assessment.total_questions = total_questions
            assessment.save(update_fields=['total_questions'])


class Migration(migrations.Migration):

    dependencies = [
        ('competency', '0006_question_explanation'),
    ]

    operations = [
        migrations.AddField(
            model_name='assessment',
            name='total_questions',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_total_questions, migrations.RunPython.noop),
    ]
