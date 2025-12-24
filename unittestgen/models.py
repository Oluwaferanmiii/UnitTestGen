from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class TestSession(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='test_sessions')
    title = models.CharField(max_length=120, blank=True, default="New Session")
    uploaded_code = models.FileField(
        upload_to='uploaded_code/', blank=True, null=True)
    pasted_code = models.TextField(blank=True, null=True)
    generated_tests = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    item_limit = models.PositiveIntegerField(default=50)

    def __str__(self):
        return f"Session {self.id} by {self.user.username} on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"  # pylint: disable = no-member


class TestItem(models.Model):
    session = models.ForeignKey(
        TestSession, on_delete=models.CASCADE, related_name='items')

    source_code = models.TextField()

    input_method = models.CharField(
        max_length=10,
        choices=[("paste", "paste"), ("upload", "upload")],
        default="paste",
    )
    source_filename = models.CharField(max_length=255, blank=True, null=True)

    pasted_code = models.TextField(blank=True, null=True)
    uploaded_code = models.FileField(
        upload_to='uploaded_code/', blank=True, null=True)

    generated_tests = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']  # newest first

    def __str__(self):
        return f"Item {self.id} in Session {self.session_id}"
