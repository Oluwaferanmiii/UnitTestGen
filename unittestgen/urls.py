from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    CreateTestSessionView,
    RegisterView,
    UserTestSessionListView,
    RegenerateTestView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('upload/', CreateTestSessionView.as_view(), name='upload-session'),
    path('sessions/', UserTestSessionListView.as_view(), name='user-sessions'),
    path('regenerate/<int:pk>/', RegenerateTestView.as_view(),
         name='regenerate-session'),
]
