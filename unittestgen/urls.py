from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    # Auth
    RegisterView,
    ThrottledTokenObtainPairView,
    # Sessions (new flow)
    SessionListCreateView,
    SessionRetrieveUpdateDestroyView,
    # Items + Regenerate
    CreateTestItemView,
    RegenerateTestView,
    # (Optional legacy)
    # CreateTestSessionView,
)

urlpatterns = [
    # Auth
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", ThrottledTokenObtainPairView.as_view(),
         name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Sessions (new flow)
    # GET  /api/sessions/   -> list
    # POST /api/sessions/   -> create EMPTY session
    path("sessions/", SessionListCreateView.as_view(), name="sessions"),

    # GET/PATCH/DELETE /api/sessions/<id>/
    path("sessions/<int:pk>/", SessionRetrieveUpdateDestroyView.as_view(),
         name="session-detail"),

    # Items (per-session code turns)
    # POST /api/sessions/<session_id>/items/
    path("sessions/<int:session_id>/items/",
         CreateTestItemView.as_view(), name="session-items-create"),

    # Regenerate (latest item by default or ?item_id=)
    # POST /api/regenerate/<session_id>/
    path("regenerate/<int:pk>/", RegenerateTestView.as_view(),
         name="regenerate-session"),

    # (Optional legacy one-shot endpoint; keep commented if not needed)
    # path("upload/", CreateTestSessionView.as_view(), name="upload-session"),
]
