import pytest
from django.contrib.auth.models import User
from ninja.testing import TestClient

from blog.urls import api
from core.models import Post, Category

class TestPostsAPI:
    """Тесты CRUD операций для статей"""
    
    def test_list_posts_empty(self, api_client, helpers):
        """Тест получения пустого списка статей"""
        response = api_client.get("/api/posts")
        result = helpers.assert_response_ok(response)
        
        assert "posts" in result
        assert len(result["posts"]) == 0
        assert result["total_count"] == 0
        assert result["current_page"] == 1
    
    def test_list_posts_with_data(self, api_client, post, helpers):
        """Тест получения списка статей с данными"""
        response = api_client.get("/api/posts")
        result = helpers.assert_response_ok(response)
        
        assert len(result["posts"]) >= 1
        assert result["total_count"] >= 1
        
        first_post = result["posts"][0]
        assert first_post["title"] == post.title
        assert first_post["author"]["username"] == post.author.username
        assert first_post["status"] == "published"
    
    def test_list_posts_pagination(self, api_client, user, helpers):
        """Тест пагинации статей"""
        # Создаем 25 статей
        posts = []
        for i in range(25):
            post = Post.objects.create(
                title=f"Test Post {i}",
                content=f"Content {i}",
                author=user,
                status=Post.STATUS_PUBLISHED
            )
            posts.append(post)
        
        # Первая страница
        response = api_client.get("/api/posts?page=1&page_size=10")
        result = helpers.assert_response_ok(response)
        
        assert len(result["posts"]) == 10
        assert result["total_count"] == 25
        assert result["total_pages"] == 3
        assert result["current_page"] == 1
        assert result["has_next"] is True
        assert result["has_previous"] is False
        
        # Вторая страница
        response = api_client.get("/api/posts?page=2&page_size=10")
        result = helpers.assert_response_ok(response)
        
        assert len(result["posts"]) == 10
        assert result["current_page"] == 2
        assert result["has_next"] is True
        assert result["has_previous"] is True
        
        # Последняя страница
        response = api_client.get("/api/posts?page=3&page_size=10")
        result = helpers.assert_response_ok(response)
        
        assert len(result["posts"]) == 5
        assert result["current_page"] == 3
        assert result["has_next"] is False
        assert result["has_previous"] is True
    
    def test_list_posts_filter_category(self, api_client, category, helpers):
        """Тест фильтрации статей по категории"""
        # Создаем статью в категории
        post = Post.objects.create(
            title="Category Test",
            content="Content",
            author=User.objects.create_user(username="author1"),
            category=category,
            status=Post.STATUS_PUBLISHED
        )
        
        # Создаем статью без категории
        Post.objects.create(
            title="No Category",
            content="Content",
            author=User.objects.create_user(username="author2"),
            status=Post.STATUS_PUBLISHED
        )
        
        # Фильтруем по категории
        response = api_client.get(f"/api/posts?category_id={category.id}")
        result = helpers.assert_response_ok(response)
        
        assert result["total_count"] == 1
        assert result["posts"][0]["title"] == "Category Test"
        assert result["posts"][0]["category"]["id"] == category.id
    
    def test_list_posts_filter_author(self, api_client, user, helpers):
        """Тест фильтрации статей по автору"""
        # Создаем статьи разных авторов
        post1 = Post.objects.create(
            title="Author 1 Post",
            content="Content",
            author=user,
            status=Post.STATUS_PUBLISHED
        )
        
        user2 = User.objects.create_user(username="author2")
        Post.objects.create(
            title="Author 2 Post",
            content="Content",
            author=user2,
            status=Post.STATUS_PUBLISHED
        )
        
        # Фильтруем по автору
        response = api_client.get(f"/api/posts?author_id={user.id}")
        result = helpers.assert_response_ok(response)
        
        assert result["total_count"] == 1
        assert result["posts"][0]["title"] == "Author 1 Post"
        assert result["posts"][0]["author"]["id"] == user.id
    
    def test_list_posts_search(self, api_client, helpers):
        """Тест поиска статей"""
        # Создаем статьи с разным содержанием
        user = User.objects.create_user(username="searchuser")
        
        Post.objects.create(
            title="Python Tutorial",
            content="Learn Python programming",
            author=user,
            status=Post.STATUS_PUBLISHED
        )
        
        Post.objects.create(
            title="Django Guide",
            content="Building web apps with Django",
            author=user,
            status=Post.STATUS_PUBLISHED
        )
        
        Post.objects.create(
            title="JavaScript Basics",
            content="Frontend development",
            author=user,
            status=Post.STATUS_PUBLISHED
        )
        
        # Ищем по слову "Python"
        response = api_client.get("/api/posts?search=Python")
        result = helpers.assert_response_ok(response)
        
        assert result["total_count"] == 1
        assert "Python" in result["posts"][0]["title"]
        
        # Ищем по слову "Django"
        response = api_client.get("/api/posts?search=Django")
        result = helpers.assert_response_ok(response)
        
        assert result["total_count"] == 1
        assert "Django" in result["posts"][0]["title"]
        
        # Ищем по слову "development" в содержании
        response = api_client.get("/api/posts?search=development")
        result = helpers.assert_response_ok(response)
        
        assert result["total_count"] == 1
        assert "JavaScript" in result["posts"][0]["title"]
    
    def test_get_post_success(self, api_client, post, helpers):
        """Тест получения конкретной статьи"""
        response = api_client.get(f"/api/posts/{post.id}")
        result = helpers.assert_response_ok(response)
        
        assert result["id"] == post.id
        assert result["title"] == post.title
        assert result["content"] == post.content
        assert result["author"]["username"] == post.author.username
        assert result["status"] == "published"
        
        # Проверяем, что счетчик просмотров увеличился
        post.refresh_from_db()
        assert post.view_count == 1
    
    def test_get_post_not_found(self, api_client, helpers):
        """Тест получения несуществующей статьи"""
        response = api_client.get("/api/posts/999999")
        assert response.status_code == 404
    
    def test_get_draft_post_unauthorized(self, api_client, user):
        """Тест получения черновика без авторизации"""
        draft_post = Post.objects.create(
            title="Draft Post",
            content="Draft content",
            author=user,
            status=Post.STATUS_DRAFT
        )
        
        response = api_client.get(f"/api/posts/{draft_post.id}")
        assert response.status_code == 404  # Черновик не найден для неавторизованных
    
    def test_get_draft_post_author(self, authenticated_client, post):
        """Тест получения черновика автором"""
        # Меняем статью на черновик
        post.status = Post.STATUS_DRAFT
        post.save()
        
        response = authenticated_client.get(f"/api/posts/{post.id}")
        assert response.status_code == 200  # Автор видит свой черновик
    
    def test_create_post_success(self, authenticated_client, category, helpers):
        """Тест успешного создания статьи"""
        data = {
            "title": "New Test Post",
            "content": "This is the content of the new post.",
            "excerpt": "Short excerpt",
            "category_id": category.id,
            "status": "draft"
        }
        
        response = authenticated_client.post("/api/posts", json=data)
        result = helpers.assert_response_ok(response)
        
        assert result["title"] == data["title"]
        assert result["content"] == data["content"]
        assert result["excerpt"] == data["excerpt"]
        assert result["category"]["id"] == category.id
        assert result["status"] == "draft"
        
        # Проверяем, что статья создана в БД
        post = Post.objects.get(title=data["title"])
        assert post.content == data["content"]
        assert post.author.username == result["author"]["username"]
    
    def test_create_post_unauthenticated(self, api_client, helpers):
        """Тест создания статьи без авторизации"""
        data = {
            "title": "New Post",
            "content": "Content"
        }
        
        response = api_client.post("/api/posts", json=data)
        assert response.status_code == 401
    
    def test_create_post_short_title(self, authenticated_client, helpers):
        """Тест создания статьи с коротким заголовком"""
        data = {
            "title": "A",  # Слишком короткий
            "content": "Valid content here"
        }
        
        response = authenticated_client.post("/api/posts", json=data)
        result = helpers.assert_response_error(response, 400)
        
        assert result["detail"] == "Title must be at least 3 characters long"
        assert result["code"] == "title_too_short"
    
    def test_create_post_short_content(self, authenticated_client, helpers):
        """Тест создания статьи с коротким содержанием"""
        data = {
            "title": "Valid Title",
            "content": "Short"  # Слишком короткий
        }
        
        response = authenticated_client.post("/api/posts", json=data)
        result = helpers.assert_response_error(response, 400)
        
        assert result["detail"] == "Content must be at least 10 characters long"
        assert result["code"] == "content_too_short"
    
    def test_update_post_success(self, authenticated_client, post, helpers):
        """Тест успешного обновления статьи"""
        data = {
            "title": "Updated Title",
            "content": "Updated content here",
            "status": "published"
        }
        
        response = authenticated_client.put(f"/api/posts/{post.id}", json=data)
        result = helpers.assert_response_ok(response)
        
        assert result["title"] == data["title"]
        assert result["content"] == data["content"]
        assert result["status"] == "published"
        
        # Проверяем, что статья обновлена в БД
        post.refresh_from_db()
        assert post.title == data["title"]
        assert post.content == data["content"]
        assert post.status == "published"
    
    def test_update_post_not_owner(self, authenticated_client, user):
        """Тест обновления чужой статьи"""
        # Создаем статью другого автора
        other_user = User.objects.create_user(username="other")
        other_post = Post.objects.create(
            title="Other's Post",
            content="Content",
            author=other_user
        )
        
        data = {"title": "Hacked Title"}
        
        response = authenticated_client.put(f"/api/posts/{other_post.id}", json=data)
        assert response.status_code == 404  # Статья не найдена для этого автора
    
    def test_update_post_unauthenticated(self, api_client, post, helpers):
        """Тест обновления статьи без авторизации"""
        data = {"title": "Updated"}
        
        response = api_client.put(f"/api/posts/{post.id}", json=data)
        assert response.status_code == 401
    
    def test_delete_post_success(self, authenticated_client, post, helpers):
        """Тест успешного удаления статьи"""
        response = authenticated_client.delete(f"/api/posts/{post.id}")
        result = helpers.assert_response_ok(response)
        
        assert result["message"] == "Post deleted successfully"
        
        # Проверяем, что статья удалена из БД
        with pytest.raises(Post.DoesNotExist):
            Post.objects.get(id=post.id)
    
    def test_delete_post_not_owner(self, authenticated_client, user):
        """Тест удаления чужой статьи"""
        other_user = User.objects.create_user(username="other")
        other_post = Post.objects.create(
            title="Other's Post",
            content="Content",
            author=other_user
        )
        
        response = authenticated_client.delete(f"/api/posts/{other_post.id}")
        assert response.status_code == 404
    
    def test_delete_post_unauthenticated(self, api_client, post):
        """Тест удаления статьи без авторизации"""
        response = api_client.delete(f"/api/posts/{post.id}")
        assert response.status_code == 401
    
    def test_my_posts(self, authenticated_client, user, helpers):
        """Тест получения статей текущего пользователя"""
        # Создаем несколько статей для пользователя
        posts = []
        for i in range(3):
            post = Post.objects.create(
                title=f"My Post {i}",
                content=f"Content {i}",
                author=user,
                status=Post.STATUS_PUBLISHED if i % 2 == 0 else Post.STATUS_DRAFT
            )
            posts.append(post)
        
        # Создаем статью другого автора
        other_user = User.objects.create_user(username="other")
        Post.objects.create(
            title="Other's Post",
            content="Content",
            author=other_user
        )
        
        response = authenticated_client.get("/api/posts/my")
        result = helpers.assert_response_ok(response)
        
        # Должны видеть только свои статьи (включая черновики)
        assert len(result) == 3
        for post_data in result:
            assert post_data["author"]["username"] == user.username
        
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    # Тест 1: Создание статьи (успешно)
    def test_create_post_success(self):
        post_data = {
            "title": "Test Post",
            "content": "This is a test post content.",
            "category_id": self.category.id,
            "status": "draft"
        }
        
        response = self.client.post(
            "/posts/", 
            json=post_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 1)
        
        post = Post.objects.first()
        self.assertEqual(post.title, "Test Post")
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.category, self.category)
    
    # Тест 2: Создание статьи без авторизации
    def test_create_post_unauthorized(self):
        post_data = {
            "title": "Test Post",
            "content": "Content"
        }
        
        response = self.client.post("/posts/", json=post_data)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Post.objects.count(), 0)
    
    # Тест 3: Получение списка статей
    def test_list_posts(self):
        # Создаем несколько статей
        Post.objects.create(
            title="Post 1",
            content="Content 1",
            author=self.user,
            category=self.category,
            status="published"
        )
        Post.objects.create(
            title="Post 2",
            content="Content 2",
            author=self.user,
            category=self.category,
            status="published"
        )
        
        response = self.client.get("/posts/")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
    
    # Тест 4: Получение конкретной статьи
    def test_get_post(self):
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=self.user,
            category=self.category,
            status="published"
        )
        
        response = self.client.get(f"/posts/{post.id}")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Post")
        self.assertEqual(response.json()["view_count"], 1)  # Счетчик должен увеличиться
    
    # Тест 5: Обновление статьи (автор)
    def test_update_post_author(self):
        post = Post.objects.create(
            title="Old Title",
            content="Old Content",
            author=self.user,
            category=self.category
        )
        
        update_data = {
            "title": "Updated Title",
            "content": "Updated Content"
        }
        
        response = self.client.put(
            f"/posts/{post.id}",
            json=update_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        
        post.refresh_from_db()
        self.assertEqual(post.title, "Updated Title")
        self.assertEqual(post.content, "Updated Content")
    
    # Тест 6: Обновление статьи (не автор)
    def test_update_post_not_author(self):
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123"
        )
        
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=other_user,  # Другой автор!
            category=self.category
        )
        
        update_data = {
            "title": "Updated Title"
        }
        
        response = self.client.put(
            f"/posts/{post.id}",
            json=update_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)  # Post not found для этого автора
    
    # Тест 7: Удаление статьи (автор)
    def test_delete_post_author(self):
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=self.user,
            category=self.category
        )
        
        response = self.client.delete(
            f"/posts/{post.id}",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)
    
    # Тест 8: Удаление статьи (не автор)
    def test_delete_post_not_author(self):
        other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123"
        )
        
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=other_user,
            category=self.category
        )
        
        response = self.client.delete(
            f"/posts/{post.id}",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Post.objects.count(), 1)
