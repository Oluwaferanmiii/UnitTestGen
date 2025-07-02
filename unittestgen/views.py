# pylint: disable=broad-exception-caught
# pylint: disable=no-member

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import TestSession
from .serializers import TestSessionSerializer, RegisterSerializer
from .ai.codet5_engine import generate_test_from_code
import ast


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateTestSessionView(generics.CreateAPIView):
    queryset = TestSession.objects.all()
    serializer_class = TestSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        session = serializer.save(user=self.request.user)

        if session.pasted_code:
            raw_code = session.pasted_code
        elif session.uploaded_code:
            raw_code = session.uploaded_code.read().decode('utf-8')
        else:
            session.generated_tests = "# Error: No code input provided"
            session.save()
            return

        try:
            test_output = generate_test_from_code(raw_code)
            ast.parse(test_output)  # Validate Python syntax
            session.generated_tests = test_output
        except SyntaxError as e:
            session.generated_tests = f"# Error: Invalid Python syntax generated\n# {str(e)}"
        except Exception as e:
            session.generated_tests = f"# Error during generation: {str(e)}"

        session.save()


class UserTestSessionListView(generics.ListAPIView):
    serializer_class = TestSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TestSession.objects.filter(user=self.request.user).order_by('-created_at')


class RegenerateTestView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            session = TestSession.objects.get(
                pk=pk, user=request.user)
        except TestSession.DoesNotExist:
            return Response({"error": "Test session not found."}, status=status.HTTP_404_NOT_FOUND)

        # Step 1: Get the original code input
        if session.pasted_code:
            raw_code = session.pasted_code
        elif session.uploaded_code:
            raw_code = session.uploaded_code.read().decode('utf-8')
        else:
            return Response({"error": "No code input available for regeneration."}, status=status.HTTP_400_BAD_REQUEST)

        # Step 2: Generate tests using codeT5
        try:
            test_output = generate_test_from_code(raw_code)
            ast.parse(test_output)  # Check that it's valid Python
            session.generated_tests = test_output
            session.save()
        except SyntaxError as e:
            return Response({"error": f"Generated invalid Python code: {str(e)}"}, status=400)
        except Exception as e:
            return Response({"error": f"Test generation failed: {str(e)}"}, status=500)

        # Step 3: return updated session
        serializer = TestSessionSerializer(session)
        return Response(serializer.data, status=200)


print("Hello")
