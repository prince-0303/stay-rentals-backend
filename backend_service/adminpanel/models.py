from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=255)
    target_model = models.CharField(max_length=100)
    target_id = models.IntegerField()
    detail = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.admin} - {self.action} on {self.target_model}:{self.target_id}"