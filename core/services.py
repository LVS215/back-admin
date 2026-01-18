from django.contrib.auth import authenticate
from .models import User, Article, Comment
from .logging_config import logger

class AuthService:
    @staticmethod
    def register_user(username: str, password: str, email: str = None):
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email
            )
            token = user.generate_token()
            
            logger.info("user_registered", 
                       username=username, 
                       user_id=user.id)
            
            return user, token
        except Exception as e:
            logger.error("user_registration_failed", 
                        username=username, 
                        error=str(e))
            raise

    @staticmethod
    def login_user(username: str, password: str):
        user = authenticate(username=username, password=password)
        if user:
            token = user.generate_token()
            
            logger.info("user_logged_in", 
                       username=username, 
                       user_id=user.id)
            
            return user, token
        
        logger.warning("login_failed", username=username)
        return None, None

class ArticleService:
    @staticmethod
    def create_article(user: User, data: dict):
        try:
            article = Article.objects.create(
                title=data['title'],
                content=data['content'],
                author=user,
                category_id=data.get('category_id'),
                is_published=data.get('is_published', True)
            )
            
            logger.info("article_created", 
                       article_id=article.id, 
                       author_id=user.id,
                       title=article.title)
            
            return article
        except Exception as e:
            logger.error("article_creation_failed", 
                        author_id=user.id, 
                        error=str(e))
            raise

    @staticmethod
    def update_article(user: User, article_id: int, data: dict):
        try:
            article = Article.objects.get(id=article_id, author=user)
            
            for field, value in data.items():
                if value is not None:
                    setattr(article, field, value)
            
            article.save()
            
            logger.info("article_updated", 
                       article_id=article.id, 
                       author_id=user.id)
            
            return article
        except Article.DoesNotExist:
            logger.warning("article_update_unauthorized", 
                          article_id=article_id, 
                          user_id=user.id)
            raise
        except Exception as e:
            logger.error("article_update_failed", 
                        article_id=article_id, 
                        error=str(e))
            raise

    @staticmethod
    def delete_article(user: User, article_id: int):
        try:
            article = Article.objects.get(id=article_id, author=user)
            article.delete()
            
            logger.info("article_deleted", 
                       article_id=article_id, 
                       author_id=user.id)
            
            return True
        except Article.DoesNotExist:
            logger.warning("article_delete_unauthorized", 
                          article_id=article_id, 
                          user_id=user.id)
            raise

class CommentService:
    @staticmethod
    def create_comment(user: User, data: dict):
        try:
            comment = Comment.objects.create(
                article_id=data['article_id'],
                author=user,
                content=data['content'],
                parent_id=data.get('parent_id')
            )
            
            logger.info("comment_created", 
                       comment_id=comment.id, 
                       author_id=user.id,
                       article_id=data['article_id'])
            
            return comment
        except Exception as e:
            logger.error("comment_creation_failed", 
                        author_id=user.id, 
                        error=str(e))
            raise

    @staticmethod
    def update_comment(user: User, comment_id: int, data: dict):
        try:
            comment = Comment.objects.get(id=comment_id, author=user)
            comment.content = data['content']
            comment.save()
            
            logger.info("comment_updated", 
                       comment_id=comment.id, 
                       author_id=user.id)
            
            return comment
        except Comment.DoesNotExist:
            logger.warning("comment_update_unauthorized", 
                          comment_id=comment_id, 
                          user_id=user.id)
            raise

    @staticmethod
    def delete_comment(user: User, comment_id: int):
        try:
            comment = Comment.objects.get(id=comment_id, author=user)
            comment.delete()
            
            logger.info("comment_deleted", 
                       comment_id=comment_id, 
                       author_id=user.id)
            
            return True
        except Comment.DoesNotExist:
            logger.warning("comment_delete_unauthorized", 
                          comment_id=comment_id, 
                          user_id=user.id)
            raise
