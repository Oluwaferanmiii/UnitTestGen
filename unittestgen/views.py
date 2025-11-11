# pylint: disable=broad-exception-caught
# pylint: disable=no-member

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import TestSession, TestItem
from .serializers import (
    TestSessionSerializer,
    TestItemSerializer,
    RegisterSerializer,
)
from .ai.codet5_engine import generate_test_from_code
import ast


# -----------------------------
# Auth
# -----------------------------

def _client_key(request, username):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = (fwd.split(",")[0].strip()
          if fwd else request.META.get("REMOTE_ADDR", "0"))
    return f"login:{(username or '').lower().strip()}:{ip}"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    ATTEMPTS = 5          # max wrong attempts
    BLOCK_MIN = 5         # lockout minutes

    def _client_key(self, request, username):
        fwd = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = (fwd.split(",")[0].strip()
              if fwd else request.META.get("REMOTE_ADDR", "0"))
        return f"login:{(username or '').lower().strip()}:{ip}"

    def post(self, request, *args, **kwargs):
        username = (request.data.get("username") or "").strip()
        key = self._client_key(request, username)
        blocked_key = f"{key}:blocked"

        # If blocked, short-circuit
        if cache.get(blocked_key):
            return Response(
                {"detail": f"Too many failed attempts. Try again in {self.BLOCK_MIN} minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Validate credentials ourselves so we can control messaging
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            # Failed login: bump counter and maybe block
            attempts = (cache.get(key) or 0) + 1
            cache.set(key, attempts, timeout=60 * self.BLOCK_MIN)
            if attempts >= self.ATTEMPTS:
                cache.set(blocked_key, True, timeout=60 * self.BLOCK_MIN)
                return Response(
                    {"detail": f"Too many failed attempts. Try again in {self.BLOCK_MIN} minutes."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            remaining = max(self.ATTEMPTS - attempts, 0)
            return Response(
                {"detail": f"Invalid credentials. {remaining} attempt(s) left."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Success: reset counters and return tokens
        cache.delete(key)
        cache.delete(blocked_key)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User registered successfully"},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------
# Sessions (NEW FLOW)
# -----------------------------

class SessionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/sessions/   -> list current user's sessions (newest first)
    POST /api/sessions/   -> create an EMPTY session (no code required)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TestSessionSerializer

    def get_queryset(self):
        return (
            TestSession.objects
            .filter(user=self.request.user)
            .order_by("-created_at")
            .prefetch_related("items")
        )

    def perform_create(self, serializer):
        # Create a truly empty session (we'll add items via /sessions/<id>/items/)
        serializer.save(
            user=self.request.user,
            uploaded_code=None,
            pasted_code=None,
            generated_tests=None,
        )


class SessionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/sessions/<id>/   -> fetch one session (+ items)
    PATCH  /api/sessions/<id>/   -> update metadata (e.g., title/notes if present)
    DELETE /api/sessions/<id>/   -> delete session (cascade deletes items)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TestSessionSerializer

    def get_queryset(self):
        return (
            TestSession.objects
            .filter(user=self.request.user)
            .prefetch_related("items")
        )


# -----------------------------
# Items (per-session code turns)
# -----------------------------

class CreateTestItemView(APIView):
    """
    POST /api/sessions/<session_id>/items/
    Add a new code turn (paste or upload) to an existing session and generate tests.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: int):
        session = get_object_or_404(
            TestSession, id=session_id, user=request.user)

        # Enforce per-session limit (optional)
        if session.items.count() >= session.item_limit:
            return Response(
                {"error": "Session has reached its item limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pasted_code = request.data.get("pasted_code")
        uploaded_file = request.FILES.get("uploaded_code")

        if not pasted_code and not uploaded_file:
            return Response(
                {"error": "Provide pasted_code or uploaded_code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prepare raw code string
        if pasted_code:
            raw_code = pasted_code
        else:
            try:
                raw_code = uploaded_file.read().decode("utf-8")
            except Exception:
                return Response(
                    {"error": "Failed to read uploaded file as UTF-8."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Generate tests (first-pass: beam; regenerate uses sampling)
        try:
            test_output = generate_test_from_code(raw_code)
            # Validate generated Python to avoid returning broken code
            ast.parse(test_output)
        except SyntaxError as e:
            return Response(
                {"error": f"Generated invalid Python: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"error": f"Test generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Create a new item; do NOT overwrite legacy fields on the session
        item = TestItem.objects.create(
            session=session,
            pasted_code=pasted_code if pasted_code else None,
            uploaded_code=uploaded_file if uploaded_file else None,
            generated_tests=test_output,
            meta={"origin": "generate", "strategy": "beam"},
        )

        return Response(TestItemSerializer(item).data, status=status.HTTP_201_CREATED)


# -----------------------------
# Regenerate (sampling; newest item by default)
# -----------------------------

class RegenerateTestView(APIView):
    """
    POST /api/regenerate/<session_id>/?item_id=<optional>
    Regenerate tests for the latest item in the session, or for a specific item if item_id is given.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):  # pk == session_id
        session = get_object_or_404(TestSession, id=pk, user=request.user)

        # Choose target item: latest by default (ordering = ['-created_at'] on TestItem)
        item_id = request.query_params.get("item_id")
        if item_id:
            item = get_object_or_404(TestItem, id=item_id, session=session)
        else:
            item = session.items.first()
            if not item:
                return Response(
                    {"error": "No items in this session yet."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Load the source code for this item
        if item.pasted_code:
            raw_code = item.pasted_code
        elif item.uploaded_code:
            try:
                raw_code = item.uploaded_code.read().decode("utf-8")
            except Exception:
                return Response(
                    {"error": "Failed to read uploaded file as UTF-8."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"error": "No code available for this item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # (Optional) Gather previous outputs to avoid duplicates when we switch to sampling
        previous_texts = [
            it.generated_tests for it in session.items.all() if it.generated_tests]

        # For now, call the existing generator; we’ll wire strategy="sample" next
        try:
            # Example (when you update codet5_engine):
            # new_tests = generate_test_from_code(raw_code, strategy="sample", previous_texts=previous_texts)
            new_tests = generate_test_from_code(raw_code)
            ast.parse(new_tests)
        except SyntaxError as e:
            return Response(
                {"error": f"Generated invalid Python: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"error": f"Regeneration failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        regenerated = TestItem.objects.create(
            session=session,
            pasted_code=item.pasted_code,
            uploaded_code=item.uploaded_code,
            generated_tests=new_tests,
            meta={"origin": "regenerate", "strategy": "sample"},
        )

        return Response(TestItemSerializer(regenerated).data, status=status.HTTP_201_CREATED)


# -----------------------------
# Legacy single-shot endpoint (OPTIONAL)
# Keeps backward compatibility for earlier tests (create session + generate immediately)
# You can remove this later from urls.py if you go all-in on the new flow.
# -----------------------------

class CreateTestSessionView(generics.CreateAPIView):
    """
    POST /api/upload/  (legacy one-shot)
    Creates a session and immediately generates tests for the provided code.
    """
    queryset = TestSession.objects.all()
    serializer_class = TestSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        session = serializer.save(user=self.request.user)

        if session.pasted_code:
            raw_code = session.pasted_code
        elif session.uploaded_code:
            try:
                raw_code = session.uploaded_code.read().decode("utf-8")
            except Exception:
                session.generated_tests = "# Error: Failed to read uploaded file as UTF-8."
                session.save()
                return
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


# -----------------------------
# (Optional) User-focused list/detail for legacy compatibility
# If you keep using them elsewhere, they’re harmless alongside the new views.
# -----------------------------

class UserTestSessionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TestSessionSerializer

    def get_queryset(self):
        return (
            TestSession.objects
            .filter(user=self.request.user)
            .order_by("-created_at")
            .prefetch_related("items")
        )


class UserTestSessionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TestSessionSerializer

    def get_queryset(self):
        return TestSession.objects.filter(user=self.request.user).prefetch_related("items")
