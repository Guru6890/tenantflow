from django.db import models
from django.contrib.auth.models import AbstractUser

import uuid

from django.utils.translation import gettext_lazy as _

from .managers import UserManager

# Create your models here.

class User(AbstractUser):
    username = None
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    email = models.EmailField(_('email address'), unique=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
    
    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')
    