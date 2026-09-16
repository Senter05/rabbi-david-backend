"""Mail transport with private, bounded diagnostics and HTTPS Resend delivery."""
import base64
import json
import smtplib
import ssl
import urllib.error
import urllib.request


class MailDeliveryError(Exception):
    pass


def resend_key(config):
    if config.get('resend_api_key'):
        return config['resend_api_key']
    # Resend SMTP passwords are Resend API keys. Migrate existing deployments.
    if str(config.get('smtp_host', '')).strip().lower() == 'smtp.resend.com':
        return config.get('smtp_password', '')
    return ''


def transport(config):
    if not config.get('mail_from'):
        return 'local'
    if resend_key(config):
        return 'resend'
    return 'smtp' if config.get('smtp_host') else 'local'


def send(config, message, mail_id):
    if transport(config) == 'resend':
        payload = {'from': config['mail_from'], 'to': [str(message['To'])],
                   'subject': str(message['Subject'])}
        for kind in ('plain', 'html'):
            body = message.get_body(preferencelist=(kind,))
            if body:
                payload['text' if kind == 'plain' else 'html'] = body.get_content()
        attachments = [
            {'filename': part.get_filename() or 'attachment',
             'content': base64.b64encode(part.get_payload(decode=True)).decode('ascii')}
            for part in message.iter_attachments()
        ]
        if attachments:
            payload['attachments'] = attachments
        request = urllib.request.Request(
            'https://api.resend.com/emails',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + resend_key(config),
                     'Content-Type': 'application/json',
                     'User-Agent': 'RabbiDavid/1.0',
                     'Idempotency-Key': 'mail-' + mail_id},
            method='POST')
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as error:
            # Never log provider bodies: they may echo addresses, tokens or keys.
            reasons = {400: 'invalid_request', 401: 'invalid_api_key',
                       403: 'sender_domain_or_permission', 409: 'idempotency_conflict',
                       422: 'invalid_payload', 429: 'rate_limit'}
            raise MailDeliveryError('resend_http_%s_%s' % (
                error.code, reasons.get(error.code, 'provider_error'))) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise MailDeliveryError('resend_connection_or_timeout') from None
        except (ValueError, TypeError):
            raise MailDeliveryError('resend_invalid_response') from None
        if not isinstance(result, dict) or not isinstance(result.get('id'), str) or not result['id']:
            raise MailDeliveryError('resend_missing_message_id')
        return result['id']
    try:
        with smtplib.SMTP(config['smtp_host'], int(config.get('smtp_port', 587)), timeout=20) as client:
            client.starttls(context=ssl.create_default_context())
            if config.get('smtp_username'):
                client.login(config['smtp_username'], config.get('smtp_password', ''))
            client.send_message(message)
    except smtplib.SMTPAuthenticationError:
        raise MailDeliveryError('smtp_authentication_failed') from None
    except smtplib.SMTPException:
        raise MailDeliveryError('smtp_delivery_rejected') from None
    except OSError:
        raise MailDeliveryError('smtp_connection_or_timeout') from None
    return None
