from django.utils import timezone

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
)

from .forms import PostForm, CommentForm, UserForm
from .models import Post, User, Comment, Category
from blogicum.settings import POSTS_ON_PAGE


def pagination_page(POSTS_ON_PAGE, arr, page_number=None):
    paginator = Paginator(arr, POSTS_ON_PAGE)
    return paginator.get_page(page_number.GET.get('page'))


def index(request):
    template_name = 'blog/index.html'
    post_list = (
        Post.objects.filter(
            is_published=True,
            category__is_published=True,
            pub_date__lte=timezone.now(),
        )
        .annotate(comment_count=Count('comment'))
        .order_by('-pub_date')
    )
    context = {
        'page_obj': pagination_page(POSTS_ON_PAGE, post_list, request),
    }
    return render(request, template_name, context)


def user_profile(request, username):
    template_name = 'blog/profile.html'
    profile = get_object_or_404(User, username=username)
    if request.user.username == username:
        post_list = (
            Post.objects.filter(author__username=username)
            .annotate(comment_count=Count('comment'))
            .order_by('-pub_date')
        )
    else:
        post_list = (
            Post.objects.filter(
                author__username=username,
                is_published=True,
                category__is_published=True,
                pub_date__lte=timezone.now(),
            )
            .annotate(comment_count=Count('comment'))
            .order_by('-pub_date')
        )
    context = {
        'profile': profile,
        'page_obj': pagination_page(POSTS_ON_PAGE, post_list, request),
    }
    return render(request, template_name, context)


class EditUserProfile(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user.username])


class CategoryPost(ListView):
    model = Post
    template_name = 'blog/category.html'
    paginate_by = POSTS_ON_PAGE
    category = None

    def get_queryset(self):
        self.category = get_object_or_404(
            Category,
            slug=self.kwargs['category_slug'],
            is_published=True,
        )
        queryset = (
            Post.objects.filter(
                category__slug=self.kwargs['category_slug'],
                is_published=True,
                category__is_published=True,
                pub_date__lte=timezone.now(),
            )
            .annotate(comment_count=Count('comment'))
            .order_by('-pub_date')
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context


class PostDetail(DetailView):
    model = Post
    template_name = 'blog/detail.html'
    pk_url_kwarg = 'post_id'
    context_object_name = 'post'

    def get_object(self):
        object = super(PostDetail, self).get_object()
        if self.request.user != object.author and (
            not object.is_published or not object.category.is_published
        ):
            raise Http404()
        return object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        context['comments'] = self.object.comment.select_related(
            'author'
        ).order_by('created_at')
        return context


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', post_id)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(
        Comment,
        post_id=post_id,
        id=comment_id,
        author__username=request.user,
    )
    form = CommentForm(request.POST or None, instance=comment)
    context = {
        'form': form,
        'comment': comment,
    }
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id)
    return render(request, 'blog/comment.html', context)


@login_required
def delete_comment(request, post_id, comment_id):
    delete_comment = get_object_or_404(
        Comment,
        post_id=post_id,
        id=comment_id,
        author__username=request.user,
    )
    if request.method != "POST":
        context = {
            'delete_comment': delete_comment,
        }
        return render(request, 'blog/comment.html', context)
    delete_comment.delete()
    return redirect('blog:post_detail', post_id)


class PostCreateView(LoginRequiredMixin, CreateView):
    form_class = PostForm
    template_name = 'blog/post_form.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().author != self.request.user:
            return redirect('blog:post_detail', self.kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)


@login_required
def delete_post(request, post_id):
    template_name = 'blog/post_form.html'
    delete_post = get_object_or_404(
        Post, pk=post_id, author__username=request.user
    )
    if request.method != "POST":
        context = {
            'post': delete_post,
        }
        return render(request, template_name, context)
    delete_post.delete()
    return redirect('blog:profile', request.user)
