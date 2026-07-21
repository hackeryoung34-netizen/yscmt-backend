from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):

    user=request.user


    return Response({

        "username":user.username,

        "email":user.email

    })