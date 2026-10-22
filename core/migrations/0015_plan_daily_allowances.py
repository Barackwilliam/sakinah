from django.db import migrations

# What each plan may use in 24 hours: (messages, call seconds). -1 means unlimited.
QUOTAS = {"Free": (0, 0), "Basic": (10, 30), "Silver": (50, 120), "Gold": (100, 300), "Tanzanite": (-1, 1800)}

def fill(apps, schema_editor):
    Plan = apps.get_model("core", "Plan")
    for name, (msgs, secs) in QUOTAS.items():
        Plan.objects.filter(name__iexact=name).update(daily_messages=msgs, daily_call_seconds=secs)

class Migration(migrations.Migration):
    dependencies = [("core", "0014_call_billed_seconds_plan_daily_call_seconds_and_more")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
