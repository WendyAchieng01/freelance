from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsClientAndOwnerOrReadOnly(BasePermission):
    """
    - Client users who own the training (job.client == user.profile and training.client == user) get full CRUD.
    - Freelancer users get read-only access.
    - Others denied.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Both client and freelancer can at least read
        return user.profile.user_type in ['client', 'freelancer']

    def has_object_permission(self, request, view, obj):
        user = request.user
        try:
            if request.method in SAFE_METHODS:
                return user.profile.user_type in ['client', 'freelancer']
            # Write permissions only for the job owner
            return (
                user.profile.user_type == 'client'
                and obj.job.client == user.profile
                and obj.client == user 
            )
        except Exception:
            return False
