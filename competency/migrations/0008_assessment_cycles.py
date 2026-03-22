from django.db import migrations, models
import django.db.models.deletion


def create_default_cycle_and_backfill(apps, schema_editor):
    Assessment = apps.get_model('competency', 'Assessment')
    AssessmentCycle = apps.get_model('competency', 'AssessmentCycle')
    Stage = apps.get_model('competency', 'Stage')

    default_cycle = AssessmentCycle.objects.create(
        name='Assessment 1',
        sequence=1,
        is_current=True,
    )

    stage_names = {
        stage.order: stage.name
        for stage in Stage.objects.all()
    }

    for assessment in Assessment.objects.all().iterator():
        if not assessment.stage_name:
            assessment.stage_name = stage_names.get(assessment.stage, f'Stage {assessment.stage}')
        assessment.cycle_id = default_cycle.id
        assessment.save(update_fields=['cycle', 'stage_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('competency', '0007_assessment_total_questions'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssessmentCycle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('sequence', models.PositiveIntegerField(unique=True)),
                ('is_current', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-sequence'],
            },
        ),
        migrations.AddField(
            model_name='assessment',
            name='cycle',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='assessments', to='competency.assessmentcycle'),
        ),
        migrations.AddField(
            model_name='assessment',
            name='stage_name',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.RunPython(create_default_cycle_and_backfill, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='assessment',
            name='cycle',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assessments', to='competency.assessmentcycle'),
        ),
    ]
