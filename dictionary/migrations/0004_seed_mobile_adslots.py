from django.db import migrations


def seed_mobile_ad_slots(apps, schema_editor):
    AdSlot = apps.get_model('dictionary', 'AdSlot')
    defaults = [
        ('home_top_mobile', 'Ana Sayfa Ust Banner (Mobil)', 'Reklam alani (Homepage Top Banner - Mobile)'),
        ('home_bottom', 'Ana Sayfa Alt Banner', 'Reklam alani (Homepage Bottom Banner)'),
        ('home_bottom_mobile', 'Ana Sayfa Alt Banner (Mobil)', 'Reklam alani (Homepage Bottom Banner - Mobile)'),
        ('en_tr_inline_mobile', 'EN-TR Detay Ara Banner (Mobil)', 'Reklam alani (Detail Inline Banner - Mobile)'),
        ('tr_en_bottom_mobile', 'TR-EN Detay Alt Banner (Mobil)', 'Reklam alani (Detail Bottom Banner - Mobile)'),
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


def unseed_mobile_ad_slots(apps, schema_editor):
    AdSlot = apps.get_model('dictionary', 'AdSlot')
    AdSlot.objects.filter(
        key__in=[
            'home_top_mobile',
            'home_bottom',
            'home_bottom_mobile',
            'en_tr_inline_mobile',
            'tr_en_bottom_mobile',
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('dictionary', '0003_seed_adslots'),
    ]

    operations = [
        migrations.RunPython(seed_mobile_ad_slots, unseed_mobile_ad_slots),
    ]
