import tempfile
import time
import unittest
from email.message import EmailMessage
from unittest.mock import patch
from email_templates import add_html
import server
import test_app
from content import fallback_reading


class EmailTemplateTests(unittest.TestCase):
    def test_private_link_is_preserved_and_html_escaped(self):
        msg=EmailMessage();msg['Subject']='Rabbi David | Your sign-in link'
        link='https://rabbidavid.org/access?token=private-value&next=reading'
        msg.set_content('Shalom <script>alert(1)</script>,\n\n'+link+'\n\nExpires in 15 minutes.')
        add_html(msg,'access')
        html=msg.get_body(preferencelist=('html',)).get_content()
        self.assertIn('token=private-value&amp;next=reading',html)
        self.assertNotIn('<script>',html)
        self.assertIn('Open my reading',html)
        self.assertEqual(html.count('<a '),1)
        self.assertIn(link,msg.get_body(preferencelist=('plain',)).get_content())
        self.assertIn('font-size:18px',html)

    def test_alternative_keeps_existing_attachment_and_is_idempotent(self):
        msg=EmailMessage();msg['Subject']='Your plan'
        msg.set_content('Your PDF is attached.\n\nhttps://rabbidavid.org/account.html')
        msg.add_attachment(b'%PDF-test',maintype='application',subtype='pdf',filename='plan.pdf')
        add_html(msg,'plan');add_html(msg,'plan')
        self.assertEqual(len(list(msg.iter_attachments())),1)
        self.assertEqual(list(msg.iter_attachments())[0].get_payload(decode=True),b'%PDF-test')
        self.assertEqual(len([p for p in msg.walk() if p.get_content_type()=='text/html']),1)

    def test_does_not_turn_unsafe_scheme_into_button(self):
        msg=EmailMessage();msg['Subject']='Test'
        msg.set_content('javascript:alert(1)')
        add_html(msg,'password_reset')
        self.assertNotIn('<a ',msg.get_body(preferencelist=('html',)).get_content())

    def test_ready_notice_is_short_and_does_not_repeat_private_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            server.init({},directory)
            sid=server.new_session();answers=test_app.example()
            answers['note']='A private issue that should stay in my account.'
            server.update(sid,lambda d:d.update(email='test@example.com',answers=answers,
                status='ready',reading=fallback_reading(answers),tier='reading',marketing=False))
            server.sync_delivery(sid)
            with server.connection() as con:
                rows=con.execute('SELECT * FROM mail').fetchall()
            self.assertEqual(len(rows),1)
            self.assertLess(len(rows[0]['body'].split()),100)
            self.assertNotIn(answers['note'],rows[0]['body'])
            self.assertIn('/account.html',rows[0]['body'])
            self.assertTrue(rows[0]['subject'].startswith('Rabbi David |'))

    def test_recovery_keeps_real_one_use_expiry_and_dispatches_html(self):
        with tempfile.TemporaryDirectory() as directory:
            server.init({'resend_api_key':'dummy','mail_from':'test@example.com'},directory)
            sid=server.new_session()
            server.update(sid,lambda d:d.update(email='test@example.com'))
            before=time.time();server.recovery_mail(sid)
            with server.connection() as con:
                expires=con.execute('SELECT expires FROM access').fetchone()['expires']
            self.assertAlmostEqual(expires-before,900,delta=2)
            with patch('mail_delivery.send',return_value='test-provider-id') as send:
                server.dispatch_mail_once()
            message=send.call_args.args[1]
            html=message.get_body(preferencelist=('html',)).get_content()
            self.assertIn('15 minutes',html)
            self.assertIn('/access?token=',html)
            self.assertIn('works once',html)
            self.assertNotIn('OTP',html)


if __name__=='__main__':unittest.main()
