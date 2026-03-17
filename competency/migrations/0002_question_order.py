from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competency', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='order',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]
