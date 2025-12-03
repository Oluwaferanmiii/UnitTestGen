from django.contrib.auth.models import User
from rest_framework import serializers
from .models import TestSession, TestItem
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password


MAX_CODE_CHARS = 8000


class TestItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestItem
        fields = ['id', 'pasted_code', 'uploaded_code',
                  'generated_tests', 'created_at', 'meta']
        read_only_fields = ['id', 'generated_tests', 'created_at', 'meta']


class TestSessionSerializer(serializers.ModelSerializer):
    items = TestItemSerializer(many=True, read_only=True)

    class Meta:
        model = TestSession
        fields = ['id', 'user',
                  "title",
                  'uploaded_code', 'pasted_code', 'generated_tests',
                  'notes', 'created_at', 'updated_at',
                  'item_limit',
                  'items',]
        read_only_fields = ['id', 'generated_tests',
                            'created_at', 'updated_at', 'user']

    def validate_pasted_code(self, value):
        if value and len(value) > MAX_CODE_CHARS:
            raise serializers.ValidationError(
                f"Code is too long (>{MAX_CODE_CHARS} characters). "
                "Please shorten it or split into multiple sessions."
            )
        return value

    # == LEGACY UNUSED CODE TO ENFORCE SESSION CANNOT BE EMPTY
    # def validate(self, attrs):
    #     uploaded = attrs.get("uploaded_code")
    #     pasted = attrs.get("pasted_code")
    #     if not uploaded and not pasted:
    #         raise serializers.ValidationError(
    #             "Provide either uploaded_code or pasted_code.")

    #     if uploaded:
    #         name = getattr(uploaded, "name", "")
    #         if not name.endswith(".py"):
    #             raise serializers.ValidationError(
    #                 "Only .py files are allowed.")
    #         if uploaded.size > 512 * 1024:  # 512KB cap (tweak as needed)
    #             raise serializers.ValidationError(
    #                 "Uploaded file is too large.")
    #     return attrs


class RegisterSerializer(serializers.ModelSerializer):
    # Enforce real email validation + max length + case-insensitive uniqueness
    email = serializers.EmailField(
        required=True,
        max_length=254,
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            lookup='iexact',
            message='Email already in use.'
        )]
    )
    # Enforce min & max length + case-insensitive uniqueness
    # (User.username supports up to 150 chars; keep that as an upper bound)
    username = serializers.CharField(
        min_length=3,
        max_length=150,
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            lookup='iexact',
            message='Username already taken.'
        )]
    )
    # Keep 8+ chars; (optional: use validate_password for richer checks)
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    # Trim whitespace so "  John  " doesn’t get stored with spaces
    def validate_username(self, v: str):
        v = (v or "").strip()
        if not v:
            raise serializers.ValidationError("Username is required.")
        return v

    def validate_email(self, v: str):
        v = (v or "").strip()
        if not v:
            raise serializers.ValidationError("Email is required.")
        return v

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def validate_password(self, value):
        validate_password(value)
        return value
