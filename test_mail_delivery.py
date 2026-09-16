import base64
import json
import tempfile
import unittest
import urllib.error
from email.message import EmailMessage
from unittest.mock import patch, MagicMock
import mail_delivery
import server


class MailTests(unittest.TestCase):
    def message(self):
        m=EmailMessage();m['To']='test@example.com';m['Subject']='Reading'
        m.set_content('Your private link');m.add_attachment(b'%PDF-test',maintype='application',subtype='pdf',filename='plan.pdf')
        return m

    def test_resend_preserves_attachment_and_idempotency(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"id":"provider-id"}'
        with patch('mail_delivery.urllib.request.urlopen',return_value=response) as call:
            result=mail_delivery.send({'resend_api_key':'secret','mail_from':'Sender <a@example.com>'},self.message(),'unique-id')
        self.assertEqual(result,'provider-id')
        request=call.call_args.args[0];payload=json.loads(request.data)
        self.assertEqual(request.full_url,'https://api.resend.com/emails')
        self.assertEqual(request.get_header('Idempotency-key'),'mail-unique-id')
        self.assertEqual(base64.b64decode(payload['attachments'][0]['content']),b'%PDF-test')
        self.assertIn('Your private link',payload['text'])

    def test_legacy_resend_password_migrates_but_other_smtp_does_not(self):
        self.assertEqual(mail_delivery.transport({'mail_from':'a@example.com','smtp_host':'smtp.resend.com','smtp_password':'secret'}),'resend')
        self.assertEqual(mail_delivery.transport({'mail_from':'a@example.com','smtp_host':'smtp.example.com','smtp_password':'secret'}),'smtp')
        self.assertEqual(mail_delivery.transport({'resend_api_key':'secret'}),'local')

    def test_api_errors_do_not_expose_private_provider_response(self):
        error=urllib.error.HTTPError('https://api.resend.com/emails',403,'secret text',{},None)
        with patch('mail_delivery.urllib.request.urlopen',side_effect=error):
            with self.assertRaisesRegex(mail_delivery.MailDeliveryError,'resend_http_403_sender_domain_or_permission') as raised:
                mail_delivery.send({'resend_api_key':'secret','mail_from':'a@example.com'},self.message(),'id')
        self.assertNotIn('secret',str(raised.exception))

    def test_success_without_provider_id_is_not_marked_sent(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{}'
        with patch('mail_delivery.urllib.request.urlopen',return_value=response):
            with self.assertRaisesRegex(mail_delivery.MailDeliveryError,'missing_message_id'):
                mail_delivery.send({'resend_api_key':'secret','mail_from':'a@example.com'},self.message(),'id')

    def test_dispatch_persists_result_and_never_replays_backlog(self):
        with tempfile.TemporaryDirectory() as directory:
            server.init({'resend_api_key':'secret','mail_from':'a@example.com'},directory)
            with server.connection() as con:
                for mid,status in [('new','pending'),('old','needs_review'),('preview','local')]:
                    con.execute('INSERT INTO mail(id,sid,recipient,subject,body,due,kind,created,delivery_status) VALUES(?,?,?,?,?,?,?,?,?)',(mid,'s','test@example.com','Reading','text',0,'access',0,status))
            with patch('mail_delivery.send',return_value='provider-id') as send:
                server.dispatch_mail_once();server.dispatch_mail_once()
                self.assertEqual(send.call_count,1)
            with server.connection() as con:
                row=con.execute("SELECT * FROM mail WHERE id='new'").fetchone()
                self.assertEqual(row['delivery_status'],'sent');self.assertEqual(row['provider_message_id'],'provider-id')
                con.execute("UPDATE mail SET delivery_status='pending' WHERE id='new'")
            with patch('mail_delivery.send',side_effect=mail_delivery.MailDeliveryError('resend_connection_or_timeout')):
                server.dispatch_mail_once()
            with server.connection() as con:
                row=con.execute("SELECT * FROM mail WHERE id='new'").fetchone()
                self.assertEqual(row['delivery_status'],'needs_review');self.assertEqual(row['delivery_error'],'resend_connection_or_timeout')


if __name__=='__main__':unittest.main()
