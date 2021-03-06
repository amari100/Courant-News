from django.contrib import admin

from models import *
from forms import *

from courant.core.dynamic_models.admin import AttributeInline

from actions import send_article_email_update, send_issue_email_update

class IssueArticleInline(admin.TabularInline):
    model = IssueArticle
    raw_id_fields = ('article',)
    extra = 10


class IssueAdmin(admin.ModelAdmin):
    date_hierarchy = 'published_at'
    list_display = ['name', 'display_type', 'published_at', 'published']
    list_filter = ['display_type', 'published']
    search_fields = ['name']
    raw_id_fields = ('lead_media',)

    fieldsets = (
        ('General', {
            'fields': ('name', 'display_type')
        }),
        ('Publishing Settings', {
            'fields': ('published_at', 'published')
        }),
        ('Media', {
            'fields': ('lead_media',)
        })
    )

    inlines = (IssueArticleInline,)

    actions = (send_issue_email_update, )
admin.site.register(Issue, IssueAdmin)


class DisplayTypeAdmin(admin.ModelAdmin):
    search_fields = ['name']
    prepopulated_fields = {'template_name': ("name",)}
admin.site.register(IssueDisplayType, DisplayTypeAdmin)
admin.site.register(ArticleDisplayType, DisplayTypeAdmin)


class SectionAdmin(admin.ModelAdmin):
    list_display = ['indented_name']
    ordering = ['full_path']
    prepopulated_fields = {'path': ('name',)}
admin.site.register(Section, SectionAdmin)


class ArticleStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(ArticleStatus, ArticleStatusAdmin)


class ArticleBylineInline(admin.TabularInline):
    model = ArticleByline
    fields = ('staffer', 'order')
    raw_id_fields = ("staffer",)


class ArticleMediaInline(admin.TabularInline):
    model = ArticleMedia
    fields = ('media_item', 'order')
    raw_id_fields = ('media_item',)


class ArticleIssueInline(admin.TabularInline):
    model = IssueArticle
    raw_id_fields = ('issue',)
    extra = 1


class ArticleAdmin(admin.ModelAdmin):
    date_hierarchy = 'published_at'
    list_display = ['heading', 'section', 'published_at', 'status', 'dynamic_type']
    list_filter = ['published_at', 'status', 'display_type', 'section','dynamic_type']
    search_fields = ['heading']
    prepopulated_fields = {'slug': ('heading',)}
    raw_id_fields = ['correction']
    form = ArticleAdminForm

    fieldsets = (
        ("Basics", {
            'fields': ('dynamic_type', 'section', 'display_type', 'status', 'published_at')
        }),
        ("Article Contents", {
            'fields': ('heading', 'subheading', 'summary', 'body')
        }),
        ("Tags", {
            'fields': ('tags',)
        }),
        ("Advanced", {
            'fields': ('slug', 'comment_options', 'correction'),
            'classes': ('collapse',)
        }),
    )

    inlines = [
        ArticleBylineInline,
        ArticleMediaInline,
        ArticleIssueInline,
        AttributeInline,
    ]

    actions = (send_article_email_update, )
admin.site.register(Article, ArticleAdmin)

# Remove the admin section for tagging's TaggedItem model,
# since it is not useful for users
admin.site.unregister(tagging.models.TaggedItem)