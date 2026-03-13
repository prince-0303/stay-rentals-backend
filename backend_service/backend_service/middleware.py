# middleware.py
from django.http import JsonResponse
from django.urls import resolve

class ListerRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        forbidden_for_listers = [
            'property-list', 
            'saved-properties', 
            'user-preferences', 
            'recommendations', 
            'ai-search',
            'ai-compare'
        ]

        if request.user.is_authenticated and request.user.role == 'lister':
            try:
                current_url = resolve(request.path_info).url_name
                if current_url in forbidden_for_listers:
                    return JsonResponse(
                        {"error": "Listers do not have access to consumer features."}, 
                        status=403
                    )
            except:
                pass

        return self.get_response(request)