# Generated by Django 3.2.8 on 2021-12-05 01:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("djpieuvre", "0004_alter_pieuvretask_unique_together"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pieuvretask",
            name="process",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tasks",
                to="djpieuvre.pieuvreprocess",
            ),
        ),
    ]
