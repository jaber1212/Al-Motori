from django.db import migrations

def create_missing_tables(apps, schema_editor):
    CarMake = apps.get_model('mainapp', 'CarMake')
    CarModel = apps.get_model('mainapp', 'CarModel')

    schema_editor.create_model(CarMake)
    schema_editor.create_model(CarModel)

class Migration(migrations.Migration):

    atomic = False  # 🔑 مهم جدًا لـ MySQL

    dependencies = [
        ('mainapp', '0003_carmake_qrcode_profile_email_profile_player_id_and_more'),
    ]

    operations = [
        migrations.RunPython(create_missing_tables),
    ]
