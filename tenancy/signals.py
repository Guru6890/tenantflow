from django.db.models.signals import pre_save
from django.dispatch import receiver

from django.utils.text import slugify
import uuid

from .models import Workspace

@receiver(pre_save, sender=Workspace)
def generate_workspace_slug(sender, instance, **kwargs):
    if instance.slug:
        return
    base_slug = slugify(instance.name)

    if not Workspace.objects.filter(slug=base_slug).exists():
        instance.slug = base_slug
        return
    
    short_suffix = uuid.uuid4().hex[:6]
    instance.slug = f'{base_slug}-{short_suffix}'