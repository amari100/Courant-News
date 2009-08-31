from django.conf import settings
from django.core import urlresolvers
from django import http
from django.utils.http import urlquote
import re

from django.views.debug import technical_500_response
import sys


class FileExtensionMiddleware(object):

    def _string_in_list(self, list, string):
        """
        Utility method for checking whether the request URL
        matches a list of regular expression.
        Written to support ignoring any files in media
        directories, as well as sitemap files.
        """
        for item in list:
            regex = re.compile(item)
            if regex.match(string):
                return True
        return False

    def process_request(self, request):
        """
        When Django receives a request, and before matching a URL,
        it should check for a file extension (e.g., .rss, .xml).
        This extension gets added to the request object, before being
        stripped from the request.path_info value so that proper URL
        matching can be done. request.path_info is used instead of request.path,
        because the URL system matches against path_info instead of path.
        """
        if request.path.rfind('.') > request.path.rfind('/') and not self._string_in_list(settings.FILE_EXTENSION_IGNORE, request.path):
            # Add extension to request object so that it can be accessed in views
            request.extension = request.path[request.path.rfind('.')+1:]

            # Change path_info so that URL matching occurs properly
            request.path_info = request.path[0:request.path.rfind('.')] + '/'
        else:
            # emulate's Django's APPEND_SLASH functionality
            if (not _is_valid_path(request.path_info) and
                    _is_valid_path("%s/" % request.path_info)):
                host = request.get_host()
                new_url = [host, request.path]
                newurl = "%s://%s%s/" % (request.is_secure() and 'https' or 'http', new_url[0], urlquote(new_url[1]))
                if request.GET:
                    newurl += '?' + request.META['QUERY_STRING']
                return http.HttpResponsePermanentRedirect(newurl)
            request.extension = 'html'

def _is_valid_path(path):
    """
    Returns True if the given path resolves against the default URL resolver,
    False otherwise.

    This is a convenience method to make working with "is this a match?" cases
    easier, avoiding unnecessarily indented try...except blocks.
    """
    try:
        urlresolvers.resolve(path)
        return True
    except urlresolvers.Resolver404:
        return False
    
class UserBasedExceptionMiddleware(object):
    def process_exception(self, request, exception):
        if request.user.is_superuser:
            return technical_500_response(request, *sys.exc_info())