import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from decouple import config
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import serializers

class FAQRequestSerializer(serializers.Serializer):
    question = serializers.CharField()

CHATBOT_SERVICE_URL = config("CHATBOT_SERVICE_URL", )

class FAQBotView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=FAQRequestSerializer,
        examples=[
            OpenApiExample(
                "Example",
                value={"question": "What is your refund policy?"}
            )
        ]
    )
    def post(self, request):
        question = request.data.get("question")

        if not question:
            return Response(
                {"error": "Question is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            response = requests.post(
                f"{CHATBOT_SERVICE_URL}/api/faq/",
                json={"question": question},
                timeout=15
            )
            response.raise_for_status()
            return Response(response.json(), status=status.HTTP_200_OK)

        except requests.exceptions.Timeout:
            return Response(
                {"error": "Chatbot service timed out. Please try again."},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except requests.exceptions.ConnectionError:
            return Response(
                {"error": "Chatbot service is unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except requests.exceptions.RequestException as e:
            return Response(
                {"error": "Failed to reach chatbot service."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )