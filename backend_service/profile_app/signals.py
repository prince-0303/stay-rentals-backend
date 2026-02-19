from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserProfile, ListerProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.role == 'user':
        UserProfile.objects.get_or_create(user=instance)

    elif instance.role == 'lister':
        ListerProfile.objects.get_or_create(user=instance)
