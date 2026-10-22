from django.db import migrations

# The plan cards now print the daily messaging and call allowance themselves, so these
# hand-written lines would say it twice, and the old ones no longer match the allowance.
DROP = ["-messaging (limited)", "send and receive messages", "unlimited messages"]

def tidy(apps, schema_editor):
    for plan in apps.get_model("core", "Plan").objects.all():
        kept = [l for l in plan.features.splitlines() if l.strip().lower() not in DROP]
        if len(kept) != len(plan.features.splitlines()):
            plan.features = "\n".join(kept)
            plan.save(update_fields=["features"])

class Migration(migrations.Migration):
    dependencies = [("core", "0015_plan_daily_allowances")]
    operations = [migrations.RunPython(tidy, migrations.RunPython.noop)]
