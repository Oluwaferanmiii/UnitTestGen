from django.contrib.auth.models import User
from rest_framework import serializers
from .models import TestSession


class TestSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSession
        fields = ['id', 'user',
                  'uploaded_code', 'pasted_code',
                  'generated_tests', 'notes',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'generated_tests',
                            'created_at', 'updated_at', 'user']

    def validate(self, attrs):
        uploaded = attrs.get("uploaded_code")
        pasted = attrs.get("pasted_code")
        if not uploaded and not pasted:
            raise serializers.ValidationError(
                "Provide either uploaded_code or pasted_code.")

        if uploaded:
            name = getattr(uploaded, "name", "")
            if not name.endswith(".py"):
                raise serializers.ValidationError(
                    "Only .py files are allowed.")
            if uploaded.size > 512 * 1024:  # 512KB cap (tweak as needed)
                raise serializers.ValidationError(
                    "Uploaded file is too large.")
        return attrs

    # def create(self, validated_data):
    #     user = self.context['request'].user
    #     return TestSession.objects.create(user=user, **validated_data)  # pylint: disable=no-member


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
