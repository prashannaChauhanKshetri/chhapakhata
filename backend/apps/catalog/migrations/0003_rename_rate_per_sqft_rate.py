from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_initial")]

    operations = [
        migrations.RenameField("mediatype", "rate_per_sqft", "rate"),
        migrations.RenameField("historicalmediatype", "rate_per_sqft", "rate"),
    ]
