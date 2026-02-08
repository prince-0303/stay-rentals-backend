from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """Permission class to check if user is an admin."""
    
    message = 'You must be an admin to perform this action.'
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsLister(permissions.BasePermission):
    """Permission class to check if user is a lister."""
    
    message = 'You must be a lister to perform this action.'
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'lister'
        )


class IsUser(permissions.BasePermission):
    """Permission class to check if user is a regular user."""
    
    message = 'You must be a user to perform this action.'
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'user'
        )


class IsAdminOrLister(permissions.BasePermission):
    """Permission class to check if user is admin or lister."""
    
    message = 'You must be an admin or lister to perform this action.'
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'lister']
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission class to check if user is the owner of the object or an admin."""
    
    message = 'You must be the owner or an admin to perform this action.'
    
    def has_object_permission(self, request, view, obj):
        # Admins can access any object
        if request.user.role == 'admin':
            return True
        
        # Check if the object has a user/owner field
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        # If we can't determine ownership, deny access
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission class to allow read-only access to everyone,
    but only allow owners to edit.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        return False