from django.contrib.auth.models import User
from rest_framework import serializers
from .models import TestSession, TestItem
from rest_framework.validators import UniqueValidator


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
                  'uploaded_code', 'pasted_code', 'generated_tests',
                  'notes', 'created_at', 'updated_at',
                  'item_limit',
                  'items',]
        read_only_fields = ['id', 'generated_tests',
                            'created_at', 'updated_at', 'user']

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
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            lookup='iexact',
            message='Email already in use.'
        )]
    )
    username = serializers.CharField(
        min_length=3,
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            lookup='iexact',
            message='Username already taken.'
        )]
    )
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user
