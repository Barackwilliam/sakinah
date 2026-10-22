from django.db import migrations
from django.utils.text import slugify


def give_logins(apps, schema_editor):
    """A member with no account of their own cannot be called, because there is no browser to ring.

    Older seeded profiles were created without one. Each gets an account with an unusable
    password, so they can be reached without becoming a way into the site.
    """
    Member, User = apps.get_model("core", "Member"), apps.get_model("auth", "User")
    for member in Member.objects.filter(user__isnull=True):
        base = slugify(member.name.split()[0]) or f"member{member.pk}"
        name, n = f"demo_{base}", 1
        while User.objects.filter(username=name).exists():
            n += 1
            name = f"demo_{base}{n}"
        member.user = User.objects.create(username=name, email=f"{name}@example.com",
                                          first_name=member.name.split()[0], password="!")
        member.save(update_fields=["user"])


class Migration(migrations.Migration):
    dependencies = [("core", "0017_message_opens")]
    operations = [migrations.RunPython(give_logins, migrations.RunPython.noop)]
