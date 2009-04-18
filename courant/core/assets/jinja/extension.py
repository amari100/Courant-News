from jinja2.ext import Extension
from jinja2 import nodes
from courant.core.assets.conf import settings
from courant.core.assets.merge import get_merged_url, get_source_urls


__all__ = ('assets')


class AssetsExtension(Extension):
    """
    As opposed to the Django tag, this tag is slightly more capable due
    to the expressive powers inherited from Jinja. For example:

        {% assets "src1.js", "src2.js", get_src3(),
                  filter=("jsmin", "gzip"), output=get_output() %}
        {% endassets %}
    """
    tags = set(['assets'])

    def parse(self, parser):
        lineno = parser.stream.next().lineno

        files = []
        output = nodes.Const(None)
        filter = nodes.Const(None)

        # parse the arguments
        first = True
        while parser.stream.current.type is not 'block_end':
            if not first:
                parser.stream.expect('comma')
            first = False

            # lookahead to see if this is an assignment (an option)
            if parser.stream.current.test('name') and \
                parser.stream.look().test('assign'):

                name = parser.stream.next().value
                parser.stream.skip()
                value = parser.parse_expression()
                if name == 'filter':
                    filter = value
                elif name == 'output':
                    output = value
                else:
                    parser.fail('Invalid keyword argument: %s' % name)
            # otherwise assume a source file is given, which may
            # be any expression, except note that strings are handled
            # separately avove
            else:
                files.append(parser.parse_expression())

        # parse the contents of this tag, and return a block
        body = parser.parse_statements(['name:endassets'], drop_needle=True)
        return nodes.CallBlock(
                self.call_method('_render_assets',
                                 args=[filter, output, nodes.List(files)]),
                [nodes.Name('ASSETS_URL', 'store')], [], body).\
                    set_lineno(lineno)

    def _render_assets(self, filter, output, files, caller=None):
        if not settings.ASSETS_DEBUG:
            merged_url = get_merged_url(files, output, filter)
            if merged_url:
                return caller(merged_url)

        # At this point, either ASSETS_DEBUG is enabled, or
        # ``get_merged_url`` returned False, in both cases we render
        # the source assets.
        result = u""
        for f in get_source_urls(files):
            result += caller(f)
        return result


assets = AssetsExtension  # nicer import name
