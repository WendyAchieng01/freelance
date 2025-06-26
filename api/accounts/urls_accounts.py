from django.urls import path
from .views import (
    UserViewSet,
    ProfileViewSet,
    SkillViewSet,
    LanguageViewSet,
)


# UserViewSet Actions
user_list_create = UserViewSet.as_view({
    'get': 'list', 
    'post': 'create'
})
user_detail_actions = UserViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})


# ProfileViewSet Actions
profile_list_create = ProfileViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
profile_detail = ProfileViewSet.as_view({
    'get': 'retrieve'
})
profile_me = ProfileViewSet.as_view({
    'get': 'me',
    'put': 'me',
    'patch': 'me',
    'delete': 'me'
})

# SkillViewSet Actions
skill_list_create = SkillViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
skill_detail_actions = SkillViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

# LanguageViewSet Actions
language_list_create = LanguageViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
language_detail_actions = LanguageViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})


# --- URL Patterns ---
urlpatterns = [
    # User URLs (
    path('users/', user_list_create, name='user-list-create'),
    path('users/<int:pk>/', user_detail_actions, name='user-detail'),
    
    # Profile URLs
    path('profiles/', profile_list_create, name='profile-list-create'),
    path('profiles/me/', profile_me, name='profile-me'),

    # Skill URLs
    path('skills/', skill_list_create, name='skill-list-create'),
    path('skills/<int:pk>/', skill_detail_actions, name='skill-detail'),

    # Language URLs
    path('languages/', language_list_create, name='language-list-create'),
    path('languages/<int:pk>/', language_detail_actions, name='language-detail'),

]
