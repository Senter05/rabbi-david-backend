"""Small, readable transactional emails; plaintext remains the source of truth."""
from html import escape
from urllib.parse import urlsplit


ACTION_LABELS = {
    'access': 'Open my reading', 'password_reset': 'Choose a new password',
    'welcome': 'Open my account', 'plan': 'Open my reading',
    'ebook': 'Download my book',
}


def add_html(message, kind, origin='https://rabbidavid.org'):
    """Add an accessible alternative, without changing tokens or attachments."""
    if kind == 'support' or message.get_body(preferencelist=('html',)):
        return
    plain = message.get_body(preferencelist=('plain',))
    if plain is None:
        return
    body = plain.get_content().strip()
    paragraphs = body.split('\n\n')
    action = next((p.strip() for p in paragraphs
                   if p.strip().startswith(('https://', 'http://'))
                   and not any(c.isspace() for c in p.strip())), None)
    # Never turn arbitrary text or javascript URLs into a button.
    if action:
        parsed=urlsplit(action); trusted=urlsplit(origin)
        if (parsed.scheme, parsed.netloc) != (trusted.scheme, trusted.netloc) or parsed.username:
            action = None
    label = ACTION_LABELS.get(kind, 'Open my reading')
    pieces = []
    for paragraph in paragraphs:
        if paragraph.strip() == action:
            pieces.append('<p style="margin:24px 0"><a href="' + escape(action, quote=True) +
                          '" style="display:inline-block;background:#17212b;color:#ffffff;'
                          'font-size:18px;font-weight:bold;text-decoration:none;padding:16px 22px;'
                          'border-radius:8px;line-height:1.4">' + escape(label) + '</a></p>')
        else:
            pieces.append('<p style="margin:0 0 18px">' + escape(paragraph).replace('\n', '<br>') + '</p>')
    title = str(message['Subject'] or 'Rabbi David').removeprefix('Rabbi David | ')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
            '<body style="margin:0;background:#f3f1eb;color:#20252b;font-family:Arial,sans-serif">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            '<td align="center" style="padding:24px 12px">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="max-width:560px;background:#ffffff;border-radius:12px"><tr>'
            '<td style="padding:28px 24px;font-size:18px;line-height:1.65;overflow-wrap:anywhere">'
            '<p style="margin:0 0 24px;font-size:16px;font-weight:bold;letter-spacing:2px">RABBI DAVID</p>'
            '<h1 style="margin:0 0 24px;font-size:26px;line-height:1.3">' + escape(title) + '</h1>' +
            ''.join(pieces) + '</td></tr></table></td></tr></table></body></html>')
    # A plan already has mixed MIME parts; attach the HTML to its text part.
    plain.add_alternative(html, subtype='html')
