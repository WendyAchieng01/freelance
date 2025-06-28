from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('', include('api.accounts.urls')),
    path('', include('api.core.urls')),
    path('academy/', include('api.academy.urls')),
    path('invoice/', include('api.invoicemanagement.urls')),
    path('payment/', include('api.payment.urls')),
    path('payments/', include('api.payments.urls')),
    path('wallet/', include('api.wallet.urls')),
    #path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    #comment the 3 lines below when in production
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
