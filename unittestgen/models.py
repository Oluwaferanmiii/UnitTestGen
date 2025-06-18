from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class TestSession(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='test_sessions')
    uploaded_code = models.FileField(
        upload_to='uploaded_code/', blank=True, null=True)
    pasted_code = models.TextField(blank=True, null=True)
    generated_tests = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Session {self.id} by {self.user.username} on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"  # pylint: disable = no-member
