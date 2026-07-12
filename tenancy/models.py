from django.db import models

import uuid

# Create your models here.

class Workspace(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    members = models.ManyToManyField(
        'identity.User',
        through='WorkspaceMembership',
        related_name='workspaces'
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'workspaces'

class WorkspaceMembership(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.ForeignKey('identity.User', on_delete=models.CASCADE, related_name='memberships')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    role = models.ForeignKey('authorization.Role', on_delete=models.PROTECT, related_name='memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey('identity.User',
                                    on_delete=models.SET_NULL,
                                    blank=True,
                                    null=True,
                                    related_name='sent_invitations'
                )
    class Meta:
        db_table = 'workspace_memberships'
        constraints = [
            models.UniqueConstraint(fields=['user', 'workspace'], name='unique_user_in_workspaces')
        ]