import pytest
import json
from datetime import datetime, timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from ninja.testing import TestClient

from core.models import User, Category, Article, Comment, Like, Bookmark
from blog.urls import api


@pytest.fixture
def api_client():
    """
    Фикстура для API клиента
    """
    return TestClient(api)


@pytest.fixture
def django_client():
    """
    Фи
        response = self.client.put(f"/api/comments/{comment.id}", 
                                 json=data,
                                 headers=self.auth_headers)
        self.assertEqual(response.status_code, 403)
