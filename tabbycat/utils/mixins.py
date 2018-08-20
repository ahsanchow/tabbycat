import os
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import connection
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import cache_page
from django.views.generic.base import ContextMixin

logger = logging.getLogger(__name__)


class TabbycatPageTitlesMixin(ContextMixin):
    """Allows all views to set header information in their subclassess obviating
    the need for page template boilerplate and/or page specific templates"""

    page_title = ''
    page_subtitle = ''
    page_emoji = ''

    def get_page_title(self):
        return self.page_title

    def get_page_emoji(self):
        return self.page_emoji

    def get_page_subtitle(self):
        return self.page_subtitle

    def get_context_data(self, **kwargs):
        if "page_title" not in kwargs:
            kwargs["page_title"] = self.get_page_title()
        if "page_subtitle" not in kwargs:
            kwargs["page_subtitle"] = self.get_page_subtitle()

        if "page_emoji" not in kwargs:
            emoji = self.get_page_emoji()
            if emoji:
                kwargs["page_emoji"] = emoji

        return super().get_context_data(**kwargs)


class AdministratorMixin(UserPassesTestMixin, ContextMixin):
    """Mixin for views that are for administrators.
    Requires use to be a superuser."""

    def get_context_data(self, **kwargs):
        kwargs["user_role"] = "admin"
        return super().get_context_data(**kwargs)

    def test_func(self):
        return self.request.user.is_superuser


class AssistantMixin(LoginRequiredMixin, ContextMixin):
    """Mixin for views that are for assistants."""

    def get_context_data(self, **kwargs):
        kwargs["user_role"] = "assistant"
        return super().get_context_data(**kwargs)


class WarnAboutDatabaseUseMixin(ContextMixin):
    """Mixin for views that should stop people exceeding database counts"""
    """ If a user has hit 8000 rows they have received Heroku's shut down
    notification. They are probably fine to finish current tournament even if
    it exceeds these limits because of the one-week grace period. However they
    should not create new tournaments as this typically happens after the grace
    period and is thus subject to major disruptions"""
    db_warning_severity = messages.WARNING

    def get_database_row_count(self):
        cursor = connection.cursor()
        cursor.execute("SELECT schemaname,relname,n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;")
        return sum([row[2] for row in cursor.fetchall()])

    def get_standings_error_message(self, rows):
        url = "https://devcenter.heroku.com/articles/upgrading-heroku-postgres-databases"
        return gettext_lazy(
            "You have current used %(rows)s rows on your database. "
            "If you have not upgraded your Heroku database to a non-free tier "
            "it is limited to a maximum of 10,000 rows. As you are relatively "
            "close to this limit you should <strong>not create new tournaments"
            "</strong> on this tab site unless you first <a href=\" %(url)s \">"
            "upgrade the database</a> or have already upgraded it."
            % {'rows': rows, 'url': url}
        )

    def get_context_data(self, **kwargs):
        if 'DATABASE_URL' in os.environ and self.request.user.is_authenticated:
            rows = self.get_database_row_count()
            if rows >= 80:
                messages.add_message(self.request, self.db_warning_severity,
                                     self.get_standings_error_message(rows))

        return super().get_context_data(**kwargs)


class CacheMixin:
    """Mixin for views that cache the page and need to update quickly."""

    cache_timeout = settings.PUBLIC_FAST_CACHE_TIMEOUT

    @method_decorator(cache_page(cache_timeout))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
