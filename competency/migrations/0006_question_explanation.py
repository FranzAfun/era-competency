from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competency', '0005_alter_question_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='explanation',
            field=models.TextField(blank=True, default=''),
        ),
    ]
