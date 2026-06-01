from django.shortcuts import render
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response
from django.middleware.csrf import get_token
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from backend.authentication import CookieOrHeaderJWTAuthentication
from rest_framework.permissions import IsAuthenticated
import base64
import hashlib
import secrets
import string
from django.conf import settings
import requests
from .models import User
# invalidate

# Create your views here.
def generate_pkce_pair():
    alphabet = string.ascii_letters + string.digits + '-._~'
    code_verifier = ''.join(secrets.choice(alphabet) for _ in range(64))
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return code_verifier, code_challenge

def exchange_google_code_for_tokens(code, code_verifier, redirect_uri):
    resp = requests.post(
        token_endpoint = 'https://oauth2.googleapis.com/token',
        headers={'Accept': 'application/json'},
        data = {
        'client_id': settings.GOOGLE_CLIENT_ID,
        'CLIENT_SECRET': settings.GOOGLE_CLIENT_SECRET,
        'code': code,
        'code_verifier': code_verifier,
        'redirect_uri': redirect_uri
        }
    )
    return resp.json()

def get_google_user_info(access_token):
    headers={'Authorization': f'Bearer {access_token}'}
    user_resp = requests.get('https://www.googleapis.com/oauth2/v1/userinfo', headers=headers)
    if user_resp.status_code != 200:
        raise Exception('Failed to fetch user info from Google')

    google_user = user_resp.json()
    email = google_user.get('email')

    if not email:
        email_resp = requests.get('https://www.googleapis.com/oauth2/v1/userinfo', headers=headers)
        if email_resp.status_code == 200:
          primary_email = next((e for e in email_resp.json() if e.get('primary')), None)
          email = primary_email['email'] if primary_email else ''  

    return google_user, email

def get_or_create_user(email, google_user):
    return User.objects.get_or_create(
        google_id=google_user['id'],
        defaults={
            'username': google_user['login'],
            'email': email or '',
            'google_avatar_url': google_user.get('avatar_url', ''),
            'login': google_user.get('login', ''),
        },
    )

def issue_jwt_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)

class loginView(TokenObtainPairView):
    pass

class refreshView(TokenRefreshView):
    pass

class GooglePKCEInitView(APIView):
    def get(self, request):
        redirect_uri = request.GET.get('redirect_uri', settings.GOOGLE_REDIRECT_URI)
        state = request.GET.get('state') or secrets.token_urlsafe(32)
        external_challenge = request.GET.get('code_challenge')

        if external_challenge:
            code_challenge = external_challenge
            code_verifier = None
        else:
            code_verifier, code_challenge = generate_pkce_pair()

        auth_url = (
            f'https://google.com/login/oauth/authorize'
            f'?client_id={settings.GOOGLE_CLIENT_ID}'
            f'&code_challenge={code_challenge}'
            f'&code_challenge_method=S256'
            f'&redirect_uri={redirecr_uri}'
            f'&state={state}'
            f'&scope=read:user user:email'
        )

        payload ={'authorization_url': auth_url, 'state': state}
        if code_verifier:
            payload['code_verifier'] = code_verifier

        return Response(payload)
        
class GoogleBrowserAuthView(APIView):
    def post(self, request):
        code = request.data.get('code')
        code_verifier = request.data.get('code_verifier')
        redirect_uri = request.data.get('redirect_uri', settings.GOOGLE_REDIRECT_URI)

        if not code or not code_verifier:
            return Response({'error': 'Missing code or code_verifier'}, status=400)

        tokens_data = exchange_google_code_for_tokens(code, code_verifier, redirect_uri)

        if 'access' not in tokens_data:
            return Response({'error': 'Failed to exchange code for tokens'}, status=400)
            access_token = tokens_data['access']

        google_user, email = get_google_user_info(tokens_data['access'])
        if not google_user:
            return Response({'error': 'Failed to fetch user info from Google'}, status=400)

        user, _ = get_or_create_user(email, google_user)
        access_token, refresh_token = issue_jwt_for_user(user)

        response =Response({'Message': 'Login successful', 'role': user.role})

        access_max_age = int(settings.SIMPLE_JWT[ACCESS_TOKEN_LIFETIME].total_seconds())
        refresh_max_age = int(settings.SIMPLE_JWT[REFRESH_TOKEN_LIFETIME].total_seconds())

        response.set_cookie(
            'access_token', access_token,
            httponly=True, secure=not settings.DEBUG,
            samesite='Lax', max_age=access_max_age,
        )
        response.set_cookie(
            'refresh_token', refresh_token,
            httponly=True, secure=not settings.DEBUG,
            samesite='Lax', max_age=refresh_max_age,
        )

        get_token(request)  # ensure CSRF cookie is set
        return response

class BrowserLogoutView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        response = Response({'message': 'Logged out'})
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response

class CallbackView(APIView):
    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state', '')
        if not code:
            return Response({'error': 'No code provided'}, status=400)

        return Response()

class MeView(APIView):
    def get(self, request):
        u = request.user
        return Response({
            'id': u.id,
            'user': u.username,
            'email': u.email,
            'avatar': u.avatar_url,
            'google_login': u.google.login
        })

    def get_user_dashboard(user_id):
        cache_key = f'user_dashboard:{user_id}'
        data = cache.get(cache_key)

        if not data:
            data = {
                'recent_activities': list(User.objects.filter(id=user_id).values()),
                'stats': compute_user_stats(user_id)
            }
            cache.set(cache_key, data, timeout=300)
        return data

class UserListView(APIView):
    def get(self, request):
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        offset = (page - 1) * page_size

        queryset = User.objects.all().order_by('id')
        total = queryset.count()
        users = queryset[offset: offset + page_size]

        return Response({
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': -(-total // page_size),
                'has_next': offset + page_size < total,
                'has_previous': page > 1
            },
            'results': [
                {
                    'id': u.id,
                    'user': u.username,
                    'email': u.email,
                    'avatar': u.avatar_url,
                    'role': u.role,
                    'google_login': u.google.login
                }
                for u in users
            ],
        })
