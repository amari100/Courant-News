"""Manage assets.

Usage:

    ./manage.py assets rebuild

        Rebuild all known assets; this requires tracking to be enabled:
        Only assets that have previously been built and tracked are
        considered "known".

    ./manage.py assets rebuild --parse-templates

        Try to find as many of the project's templates (hopefully all),
        and check them for the use of assets. Rebuild all the assets
        discovered in this way. If tracking is enabled, the tracking
        database will be replaced by the newly found assets.
"""

import os
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django import template
from courant.core.assets.conf import settings
from courant.core.assets.templatetags.assets import AssetsNode as AssetsNodeO
from django.templatetags.assets import AssetsNode as AssetsNodeMapped
from courant.core.assets.merge import merge
from courant.core.assets.tracker import get_tracker

try:
    import jinja2
except:
    jinja2 = None
else:
    from django_assets.jinja.extension import AssetsExtension
    # Prepare a Jinja2 environment we can later use for parsing.
    # If not specified by the user, put in there at least our own
    # extension, which we will need most definitely to achieve anything.
    _jinja2_extensions = getattr(settings, 'ASSETS_JINJA2_EXTENSIONS')
    if not _jinja2_extensions:
        _jinja2_extensions = [AssetsExtension.identifier]
    jinja2_env = jinja2.Environment(extensions=_jinja2_extensions)


def _shortpath(abspath):
    """Make an absolute path relative to the project's settings module,
    which would usually be the project directory."""
    b = os.path.dirname(
            os.path.normpath(
                os.sys.modules[settings.SETTINGS_MODULE].__file__))
    p = os.path.normpath(abspath)
    return p[len(os.path.commonprefix([b, p])):]


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--parse-templates', action='store_true',
            help='Rebuild assets found by parsing project templates '
                 'instead of using the tracking database.'),
        make_option('--verbosity', action='store', dest='verbosity',
            default='1', type='choice', choices=['0', '1', '2'],
            help='Verbosity; 0=minimal output, 1=normal output, 2=all output'),
    )
    help = 'Manage assets.'
    args = 'subcommand'
    requires_model_validation = True

    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError('You need to specify a subcommand')
        elif len(args) > 1:
            raise CommandError('Invalid number of subcommands passed: %s' %
                ", ".join(args))
        else:
            command = args[0]

        options['verbosity'] = int(options['verbosity'])

        if command == 'rebuild':
            if options.get('parse_templates') or not get_tracker():
                assets = self._parse_templates(options)
            else:
                assets = dict()
            self._rebuild_assets(options, assets)
        else:
            raise CommandError('Unknown subcommand: %s' % command)

    def _rebuild_assets(self, options, assets):
        for output, data in assets.items():
            if options.get('verbosity') >= 1:
                print "Building asset: %s" % output
            try:
                merge(data['sources'], output, data['filter'])
            except Exception, e:
                print self.style.ERROR("Failed, error was: %s" % e)

    def _parse_templates(self, options):
        # build a list of template directories based on configured loaders
        template_dirs = []
        if 'django.template.loaders.filesystem.load_template_source' in settings.TEMPLATE_LOADERS:
            template_dirs.extend(settings.TEMPLATE_DIRS)
        if 'django.template.loaders.app_directories.load_template_source' in settings.TEMPLATE_LOADERS:
            from django.template.loaders.app_directories import app_template_dirs
            template_dirs.extend(app_template_dirs)

        found_assets = {}
        # find all template files
        if options.get('verbosity') >= 1:
            print "Searching templates..."
        total_count = 0
        for template_dir in template_dirs:
            for directory, _ds, files in os.walk(template_dir):
                for filename in files:
                    if filename.endswith('.html'):
                        total_count += 1
                        tmpl_path = os.path.join(directory, filename)
                        self._parse_template(options, tmpl_path, found_assets)
        if options.get('verbosity') >= 1:
            print "Parsed %d templates, found %d valid assets." % (
                total_count, len(found_assets))
        return found_assets

    def _parse_template(self, options, tmpl_path, found_assets):

        def try_django(contents):
            # parse the template for asset nodes
            try:
                t = template.Template(contents)
            except template.TemplateSyntaxError, e:
                if options.get('verbosity') >= 2:
                    print self.style.ERROR('\tdjango parser failed, error was: %s'%e)
                return False
            else:
                result = []

                def _recurse_node(node):
                    # depending on whether the template tag is added to
                    # builtins, or loaded via {% load %}, it will be
                    # available in a different module
                    if isinstance(node, (AssetsNodeMapped, AssetsNodeO)):
                        # try to resolve this node's data; if we fail,
                        # then it depends on view data and we cannot
                        # manually rebuild it.
                        try:
                            output, files, filter = node.resolve()
                        except template.VariableDoesNotExist:
                            if options.get('verbosity') >= 2:
                                print self.style.ERROR('\tskipping asset %s, depends on runtime data.' % node.output)
                        else:
                            result.append((output, files, filter))
                    # see Django #7430
                    for subnode in hasattr(node, 'nodelist') \
                        and node.nodelist\
                        or []:
                            _recurse_node(subnode)
                for node in t:  # don't move into _recurse_node, ``Template`` has a .nodelist attribute
                    _recurse_node(node)
                return result

        def try_jinja(contents):
            try:
                t = jinja2_env.parse(contents.decode(settings.DEFAULT_CHARSET))
            except jinja2.exceptions.TemplateSyntaxError, e:
                if options.get('verbosity') >= 2:
                    print self.style.ERROR('\tjinja parser failed, error was: %s'%e)
                return False
            else:
                result = []

                def _recurse_node(node):
                    for node in node.iter_child_nodes():
                        if isinstance(node, jinja2.nodes.Call):
                            if isinstance(node.node, jinja2.nodes.ExtensionAttribute)\
                               and node.node.identifier == AssetsExtension.identifier:
                                filter, output, files = node.args
                                result.append((output.as_const(),
                                               files.as_const(),
                                               filter.as_const()))

                for node in t.iter_child_nodes():
                    _recurse_node(node)
                return result

        if options.get('verbosity') >= 2:
            print "Parsing template: %s" % _shortpath(tmpl_path)
        file = open(tmpl_path, 'rb')
        try:
            contents = file.read()
        finally:
            file.close()

        result = try_django(contents)
        if result is False and jinja2:
            result = try_jinja(contents)
        if result:
            for output, files, filter in result:
                if not output in found_assets:
                    if options.get('verbosity') >= 2:
                        print self.style.NOTICE('\tfound asset: %s' % output)
                    found_assets[output] = {
                        'sources': files,
                        'filter': filter,
                    }
