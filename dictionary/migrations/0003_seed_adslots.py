from django.db import migrations


def seed_ad_slots(apps, schema_editor):
    AdSlot = apps.get_model('dictionary', 'AdSlot')
    defaults = [
        ('home_top', 'Ana Sayfa Ust Banner', 'Reklam alani (Homepage Top Banner)'),
        ('en_tr_inline', 'EN-TR Detay Ara Banner', 'Reklam alani (Detail Inline Banner)'),
        ('tr_en_bottom', 'TR-EN Detay Alt Banner', 'Reklam alani (Detail Bottom Banner)'),
    ]
    for key, name, placeholder in defaults:
        AdSlot.objects.get_or_create(
            key=key,
            defaults={
                'name': name,
                'placeholder_text': placeholder,
                'is_active': True,
            },
        )


def unseed_ad_slots(apps, schema_editor):
    AdSlot = apps.get_model('dictionary', 'AdSlot')
    AdSlot.objects.filter(key__in=['home_top', 'en_tr_inline', 'tr_en_bottom']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('dictionary', '0002_adslot'),
    ]

    operations = [
        migrations.RunPython(seed_ad_slots, unseed_ad_slots),
    ]
