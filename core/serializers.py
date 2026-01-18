from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import User, UserProfile, Category, Tag, Article, Comment, Like, Bookmark
from .utils import validate_password_strength, send_verification_email


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Сериализатор профиля пользователя
    """
    class Meta:
        model = UserProfile
        fields = [
            'id', 'twitter', 'facebook', 'linkedin', 'github',
            'public_profile', 'show_email', 'timezone', 'language',
            'article_count', 'comment_count', 'total_likes_received',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'article_count', 'comment_count', 'total_likes_received',
            'created_at', 'updated_at'
        ]


class UserSerializer(serializers.ModelSerializer):
    """
    Сериализатор пользователя
    """
    profile = UserProfileSerializer(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'bio', 'avatar', 'avatar_url', 'birth_date', 'website', 'location',
            'is_verified', 'email_verified', 'role',
            'receive_newsletter', 'email_notifications',
            'last_login', 'last_activity', 'login_count',
            'profile', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_verified', 'email_verified', 'role',
            'last_login', 'last_activity', 'login_count',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'password': {'write_only': True, 'required': False},
        }
    
    def get_avatar_url(self, obj):
        """
        Возвращает URL аватара
        """
        return obj.get_avatar_url()
    
    def get_full_name(self, obj):
        """
        Возвращает полное имя пользователя
        """
        return obj.get_full_name()
    
    def validate_email(self, value):
        """
        Валидирует email
        """
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Invalid email address.")
        
        # Проверяем уникальность
        if User.objects.filter(email=value).exists():
            if self.instance and self.instance.email == value:
                return value
            raise serializers.ValidationError("A user with this email already exists.")
        
        return value
    
    def validate_username(self, value):
        """
        Валидирует username
        """
        if not value.replace('_', '').replace('.', '').isalnum():
            raise serializers.ValidationError(
                "Username must be alphanumeric and can contain underscores and dots."
            )
        
        # Проверяем уникальность
        if User.objects.filter(username=value).exists():
            if self.instance and self.instance.username == value:
                return value
            raise serializers.ValidationError("A user with this username already exists.")
        
        return value
    
    def validate_password(self, value):
        """
        Валидирует пароль
        """
        return validate_password_strength(value)
    
    def create(self, validated_data):
        """
        Создает пользователя
        """
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """
        Обновляет пользователя
        """
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Сериализатор регистрации пользователя
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name'
        ]
    
    def validate(self, attrs):
        """
        Валидирует данные регистрации
        """
        # Проверяем совпадение паролей
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords do not match."
            })
        
        # Проверяем силу пароля
        validate_password_strength(attrs['password'])
        
        # Проверяем уникальность email
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({
                'email': "A user with this email already exists."
            })
        
        # Проверяем уникальность username
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({
                'username': "A user with this username already exists."
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Создает пользователя при регистрации
        """
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        
        # Отправляем email для верификации
        send_verification_email(user)
        
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Кастомный сериализатор для получения JWT токенов
    """
    def validate(self, attrs):
        """
        Валидирует данные аутентификации
        """
        # Получаем email или username
        username_or_email = attrs.get(self.username_field)
        
        # Проверяем, является ли ввод email
        try:
            validate_email(username_or_email)
            # Ищем пользователя по email
            user = User.objects.filter(email=username_or_email).first()
            if user:
                attrs[self.username_field] = user.username
        except DjangoValidationError:
            # Это username
            pass
        
        data = super().validate(attrs)
        
        # Добавляем данные пользователя
        user = self.user
        data['user'] = UserSerializer(user).data
        data['access_token_expires'] = timezone.now() + self.access_token.lifetime
        data['refresh_token_expires'] = timezone.now() + self.refresh_token.lifetime
        
        # Обновляем статистику пользователя
        request = self.context.get('request')
        if request:
            user.increment_login_count(request.META.get('REMOTE_ADDR'))
        
        return data
    
    @classmethod
    def get_token(cls, user):
        """
        Получает токен с кастомными claims
        """
        token = super().get_token(user)
        
        # Добавляем кастомные claims
        token['email'] = user.email
        token['is_verified'] = user.is_verified
        token['role'] = user.role
        
        return token


class PasswordResetSerializer(serializers.Serializer):
    """
    Сериализатор сброса пароля
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """
        Валидирует email
        """
        if not User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Сериализатор подтверждения сброса пароля
    """
    token = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """
        Валидирует данные
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords do not match."
            })
        
        validate_password_strength(attrs['password'])
        
        return attrs


class CategorySerializer(serializers.ModelSerializer):
    """
    Сериализатор категорий
    """
    article_count = serializers.IntegerField(read_only=True)
    parent_name = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description',
            'parent', 'parent_name', 'full_path',
            'color', 'icon', 'is_active', 'show_in_menu', 'sort_order',
            'meta_title', 'meta_description',
            'article_count', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'id', 'slug', 'article_count',
            'created_at', 'updated_at', 'created_by'
        ]
    
    def get_parent_name(self, obj):
        """
        Возвращает имя родительской категории
        """
        return obj.parent.name if obj.parent else None
    
    def get_full_path(self, obj):
        """
        Возвращает полный путь категории
        """
        return obj.get_full_path()
    
    def validate(self, attrs):
        """
        Валидирует данные категории
        """
        # Проверяем циклические зависимости
        parent = attrs.get('parent')
        if parent and parent == self.instance:
            raise serializers.ValidationError({
                'parent': "Category cannot be parent of itself."
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Создает категорию
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


class TagSerializer(serializers.ModelSerializer):
    """
    Сериализатор тегов
    """
    usage_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Tag
        fields = [
            'id', 'name', 'slug', 'description',
            'usage_count', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'id', 'slug', 'usage_count',
            'created_at', 'updated_at', 'created_by'
        ]
    
    def create(self, validated_data):
        """
        Создает тег
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        
        return super().create(validated_data)


class ArticleListSerializer(serializers.ModelSerializer):
    """
    Сериализатор списка статей (упрощенный)
    """
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    excerpt = serializers.SerializerMethodField()
    reading_time = serializers.IntegerField(read_only=True)
    word_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'excerpt',
            'author', 'category', 'tags',
            'status', 'article_type',
            'featured_image', 'image_caption',
            'is_featured', 'is_pinned',
            'view_count', 'like_count', 'comment_count',
            'published_at', 'reading_time', 'word_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_excerpt(self, obj):
        """
        Возвращает краткое содержание
        """
        if obj.excerpt:
            return obj.excerpt
        
        # Генерируем excerpt из content
        content = obj.content
        if len(content) > 500:
            return content[:497] + '...'
        return content


class ArticleDetailSerializer(serializers.ModelSerializer):
    """
    Сериализатор детальной информации статьи
    """
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    reading_time = serializers.IntegerField(read_only=True)
    word_count = serializers.IntegerField(read_only=True)
    related_articles = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'content', 'excerpt',
            'author', 'category', 'tags',
            'status', 'article_type',
            'featured_image', 'image_caption',
            'meta_title', 'meta_description', 'canonical_url',
            'is_featured', 'is_pinned',
            'allow_comments', 'allow_sharing', 'require_login',
            'view_count', 'like_count', 'comment_count', 'share_count',
            'published_at', 'scheduled_at',
            'reading_time', 'word_count',
            'related_articles',
            'created_at', 'updated_at',
            'last_edited_by', 'last_edited_at'
        ]
        read_only_fields = [
            'id', 'slug', 'view_count', 'like_count', 'comment_count', 'share_count',
            'reading_time', 'word_count', 'related_articles',
            'created_at', 'updated_at',
            'last_edited_by', 'last_edited_at'
        ]
    
    def get_related_articles(self, obj):
        """
        Возвращает связанные статьи
        """
        related = obj.get_related_articles(limit=3)
        return ArticleListSerializer(related, many=True).data
    
    def validate(self, attrs):
        """
        Валидирует данные статьи
        """
        # Проверяем scheduled публикацию
        scheduled_at = attrs.get('scheduled_at')
        status = attrs.get('status', self.instance.status if self.instance else 'draft')
        
        if scheduled_at and status != 'draft':
            raise serializers.ValidationError({
                'scheduled_at': "Scheduled articles must be in draft status."
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Создает статью
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user
            validated_data['last_edited_by'] = request.user
        
        # Обрабатываем теги
        tags_data = validated_data.pop('tags', [])
        article = Article.objects.create(**validated_data)
        
        if tags_data:
            article.tags.set(tags_data)
        
        return article
    
    def update(self, instance, validated_data):
        """
        Обновляет статью
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['last_edited_by'] = request.user
            validated_data['last_edited_at'] = timezone.now()
        
        # Обрабатываем теги
        tags_data = validated_data.pop('tags', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if tags_data is not None:
            instance.tags.set(tags_data)
        
        return instance


class CommentSerializer(serializers.ModelSerializer):
    """
    Сериализатор комментариев
    """
    author = UserSerializer(read_only=True)
    article_title = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    depth = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Comment
        fields = [
            'id', 'article', 'article_title', 'author', 'parent',
            'content', 'status', 'is_edited', 'edited_at', 'edit_reason',
            'like_count', 'dislike_count',
            'replies_count', 'depth',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'author', 'article_title', 'status', 'is_edited', 'edited_at',
            'like_count', 'dislike_count', 'replies_count', 'depth',
            'created_at', 'updated_at'
        ]
    
    def get_article_title(self, obj):
        """
        Возвращает заголовок статьи
        """
        return obj.article.title
    
    def get_replies_count(self, obj):
        """
        Возвращает количество ответов
        """
        return obj.replies.count()
    
    def validate(self, attrs):
        """
        Валидирует данные комментария
        """
        article = attrs.get('article', self.instance.article if self.instance else None)
        parent = attrs.get('parent')
        
        if not article.allow_comments:
            raise serializers.ValidationError({
                'article': "Comments are not allowed for this article."
            })
        
        # Проверяем глубину вложенности
        if parent:
            if parent.depth >= 5:
                raise serializers.ValidationError({
                    'parent': "Maximum comment depth reached."
                })
            
            # Проверяем, что родительский комментарий принадлежит той же статье
            if parent.article != article:
                raise serializers.ValidationError({
                    'parent': "Parent comment must belong to the same article."
                })
        
        return attrs
    
    def create(self, validated_data):
        """
        Создает комментарий
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user
        
        # Записываем IP и user agent
        if request:
            validated_data['ip_address'] = request.META.get('REMOTE_ADDR')
            validated_data['user_agent'] = request.META.get('HTTP_USER_AGENT')
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """
        Обновляет комментарий
        """
        # Не позволяем менять статью или родительский комментарий
        validated_data.pop('article', None)
        validated_data.pop('parent', None)
        
        # Отмечаем, что комментарий был отредактирован
        validated_data['is_edited'] = True
        validated_data['edited_at'] = timezone.now()
        
        return super().update(instance, validated_data)


class LikeSerializer(serializers.ModelSerializer):
    """
    Сериализатор лайков
    """
    user = UserSerializer(read_only=True)
    article_title = serializers.SerializerMethodField()
    comment_content = serializers.SerializerMethodField()
    
    class Meta:
        model = Like
        fields = [
            'id', 'user', 'article', 'article_title', 'comment', 'comment_content',
            'like_type', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']
    
    def get_article_title(self, obj):
        """
        Возвращает заголовок статьи
        """
        return obj.article.title if obj.article else None
    
    def get_comment_content(self, obj):
        """
        Возвращает содержание комментария
        """
        if obj.comment:
            return obj.comment.content[:100] + '...' if len(obj.comment.content) > 100 else obj.comment.content
        return None
    
    def validate(self, attrs):
        """
        Валидирует данные лайка
        """
        # Проверяем, что указана либо статья, либо комментарий
        article = attrs.get('article')
        comment = attrs.get('comment')
        
        if not article and not comment:
            raise serializers.ValidationError(
                "Like must be associated with either an article or a comment."
            )
        
        if article and comment:
            raise serializers.ValidationError(
                "Like cannot be associated with both an article and a comment."
            )
        
        # Проверяем, что статья опубликована
        if article and not article.is_published:
            raise serializers.ValidationError({
                'article': "Cannot like unpublished articles."
            })
        
        # Проверяем, что комментарий одобрен
        if comment and not comment.is_approved:
            raise serializers.ValidationError({
                'comment': "Cannot like unapproved comments."
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Создает лайк
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
        
        return super().create(validated_data)


class BookmarkSerializer(serializers.ModelSerializer):
    """
    Сериализатор закладок
    """
    user = UserSerializer(read_only=True)
    article = ArticleListSerializer(read_only=True)
    
    class Meta:
        model = Bookmark
        fields = ['id', 'user', 'article', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
    
    def validate(self, attrs):
        """
        Валидирует данные закладки
        """
        article = attrs.get('article', self.instance.article if self.instance else None)
        
        if not article.is_published:
            raise serializers.ValidationError({
                'article': "Cannot bookmark unpublished articles."
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Создает закладку
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
        
        return super().create(validated_data)


class ViewHistorySerializer(serializers.ModelSerializer):
    """
    Сериализатор истории просмотров
    """
    user = UserSerializer(read_only=True)
    article = ArticleListSerializer(read_only=True)
    
    class Meta:
        model = ViewHistory
        fields = [
            'id', 'user', 'article',
            'view_duration', 'ip_address', 'user_agent', 'referrer',
            'created_at'
        ]
        read_only_fields = fields


class SearchSerializer(serializers.Serializer):
    """
    Сериализатор поиска
    """
    q = serializers.CharField(required=True, min_length=2)
    category = serializers.CharField(required=False)
    tag = serializers.CharField(required=False)
    author = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    ordering = serializers.CharField(required=False)
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=10)
    
    def validate_ordering(self, value):
        """
        Валидирует поле сортировки
        """
        allowed_fields = ['created_at', 'published_at', 'view_count', 'like_count', 'comment_count']
        if value.startswith('-'):
            field = value[1:]
        else:
            field = value
        
        if field not in allowed_fields:
            raise serializers.ValidationError(
                f"Invalid ordering field. Allowed: {', '.join(allowed_fields)}"
            )
        
        return value
