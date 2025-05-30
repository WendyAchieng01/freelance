from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsClientAndOwnerOrReadOnly(BasePermission):
    """
    - Client users who own the training get full CRUD
    - Freelancer users get read-only access
    - Others denied
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Allow authenticated freelancers and clients to access
        return user.profile.user_type in ['client', 'freelancer']

    def has_object_permission(self, request, view, obj):
        user = request.user

        if request.method in SAFE_METHODS:
            # Freelancers and clients can read
            return user.profile.user_type in ['client', 'freelancer']

        # Write permissions only for the client owner
        return user.profile.user_type == 'client' and obj.client == user
