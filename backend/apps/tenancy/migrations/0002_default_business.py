"""Turn the existing single shop into the first business.

Its name comes from the shop settings, so an upgraded site keeps its data and
logins under that business. A new, empty site starts with one business too.
"""

from django.db import migrations
from django.utils.text import slugify


def create_first_business(apps, schema_editor):
    Business = apps.get_model("tenancy", "Business")
    if Business.objects.exists():
        return
    ShopSettings = apps.get_model("core", "ShopSettings")
    shop = ShopSettings.objects.order_by("pk").first()
    name = shop.name if shop else ShopSettings._meta.get_field("name").default
    Business.objects.create(name=name, slug=slugify(name)[:60] or "shop")


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0001_initial"),
        ("core", "0002_alter_shopsettings_logo_and_more"),
    ]

    operations = [migrations.RunPython(create_first_business, migrations.RunPython.noop)]
