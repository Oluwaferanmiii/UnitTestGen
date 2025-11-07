from django.contrib.auth.models import User
from rest_framework import serializers
from .models import TestSession, TestItem


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
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
