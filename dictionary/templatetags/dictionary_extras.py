from html import escape
from html.parser import HTMLParser

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = {'b', 'strong', 'i', 'em', 'u', 'br'}
LINE_BREAK_TAGS = {'p', 'div', 'li'}


class _SimpleRichTextSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = (tag or '').lower()
        if tag in ALLOWED_TAGS:
            if tag == 'br':
                self.parts.append('<br>')
            else:
                self.parts.append(f'<{tag}>')
        elif tag in LINE_BREAK_TAGS and self.parts:
            if self.parts[-1] != '<br>':
                self.parts.append('<br>')

    def handle_endtag(self, tag):
        tag = (tag or '').lower()
        if tag in ALLOWED_TAGS and tag != 'br':
            self.parts.append(f'</{tag}>')
        elif tag in LINE_BREAK_TAGS:
            if self.parts and self.parts[-1] != '<br>':
                self.parts.append('<br>')

    def handle_data(self, data):
        self.parts.append(escape(data))

    def handle_entityref(self, name):
        self.parts.append(f'&{name};')

    def handle_charref(self, name):
        self.parts.append(f'&#{name};')


@register.filter(name='dict_get')
def dict_get(mapping, key):
    if isinstance(mapping, dict):
        return mapping.get(key, '')
    return ''


@register.filter(name='render_richtext')
def render_richtext(value):
    parser = _SimpleRichTextSanitizer()
    parser.feed(str(value or ''))
    parser.close()
    cleaned = ''.join(parser.parts)
    cleaned = cleaned.replace('\r\n', '\n').replace('\n', '<br>')
    while '<br><br><br>' in cleaned:
        cleaned = cleaned.replace('<br><br><br>', '<br><br>')
    cleaned = cleaned.strip()
    while cleaned.startswith('<br>'):
        cleaned = cleaned[4:]
    while cleaned.endswith('<br>'):
        cleaned = cleaned[:-4]
    return mark_safe(cleaned)
