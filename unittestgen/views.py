from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import TestSession
from .serializers import TestSessionSerializer, RegisterSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateTestSessionView(generics.CreateAPIView):
    queryset = TestSession.objects.all()    # pylint: disable=no-member
    serializer_class = TestSessionSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserTestSessionListView(generics.ListAPIView):
    serializer_class = TestSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TestSession.objects.filter(user=self.request.user).order_by('-created_at')   # pylint: disable=no-member


class RegenerateTestView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            session = TestSession.objects.get(      # pylint: disable=no-member
                pk=pk, user=request.user)
        except TestSession.DoesNotExist:                                    # pylint: disable=no-member
            return Response({"error": "Test session not found."}, status=status.HTTP_404_NOT_FOUND)

        # 🔧 Placeholder for AI logic — replace with CodeBERT output later
        session.generated_tests = "# Regenerated test cases (placeholder)"
        session.save()

        serializer = TestSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)
