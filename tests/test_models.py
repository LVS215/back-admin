from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Article, Comment, Category

User = get_user_model()

class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com"
        )
        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.check_password("testpass123"))
        self.assertIsNotNone(user.token)
        self.assertEqual(len(user.token), 43)  # Длина token_urlsafe(32)

    def test_generate_token(self):
        user = User.objects.create_user(
            username="testuser2",
            password="testpass123"
        )
        old_token = user.token
        new_token = user.generate_token()
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(user.token, new_token)

class CategoryModelTest(TestCase):
    def test_create_category(self):
        category = Category.objects.create(
            name="Technology",
            slug="technology"
        )
        self.assertEqual(category.name, "Technology")
        self.assertEqual(category.slug, "technology")
        self.assertEqual(str(category), "Technology")

class ArticleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author",
            password="testpass123"
        )
        self.category = Category.objects.create(
            name="Tech",
            slug="tech"
        )

    def test_create_article(self):
        article = Article.objects.create(
            title="Test Article",
            content="This is test content",
            author=self.user,
            category=self.category
        )
        self.assertEqual(article.title, "Test Article")
        self.assertEqual(article.author, self.user)
        self.assertEqual(article.category, self.category)
        self.assertTrue(article.is_published)
        self.assertEqual(str(article), "Test Article")

    def test_article_ordering(self):
        article1 = Article.objects.create(
            title="Article 1",
            content="Content 1",
            author=self.user
        )
        article2 = Article.objects.create(
            title="Article 2",
            content="Content 2",
            author=self.user
        )
        articles = Article.objects.all()
        self.assertEqual(articles[0], article2)  # Последний созданный первый

class CommentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="commenter",
            password="testpass123"
        )
        self.article = Article.objects.create(
            title="Test Article",
            content="Content",
            author=self.user
        )

    def test_create_comment(self):
        comment = Comment.objects.create(
            article=self.article,
            author=self.user,
            content="Great article!"
        )
        self.assertEqual(comment.article, self.article)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.content, "Great article!")
        self.assertIsNone(comment.parent)
        self.assertEqual(
            str(comment),
            f"Comment by {self.user.username} on {self.article.title}"
        )

    def test_reply_comment(self):
        parent_comment = Comment.objects.create(
            article=self.article,
            author=self.user,
            content="Parent comment"
        )
        reply_comment = Comment.objects.create(
            article=self.article,
            author=self.user,
            content="Reply comment",
            parent=parent_comment
        )
        self.assertEqual(reply_comment.parent, parent_comment)
        self.assertEqual(parent_comment.replies.first(), reply_comment)
