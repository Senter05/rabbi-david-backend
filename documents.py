"""White, accessible branded reading PDFs. Access rules remain server-side."""
from io import BytesIO
import math
from pathlib import Path
from html import escape
from reading_access import reading_view
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable, KeepTogether

ROOT = Path(__file__).resolve().parent / 'public' / 'assets'
NAVY = colors.HexColor('#182D40')
INK = colors.HexColor('#293744')
GOLD = colors.HexColor('#947127')
for name, filename in [('RDInter','a699af1dea30.ttf'), ('RDSemibold','87e867b52640.ttf'), ('RDFraunces','959364b06f81.ttf'), ('RDCinzel','59b1fd406398.ttf')]:
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(ROOT / 'fonts' / filename)))


def reading_pdf(data):
    reading, access = reading_view(data['reading'], data['tier'])
    name = str(data.get('answers', {}).get('name') or 'you')
    styles = {
        'body': ParagraphStyle('body', fontName='RDInter', fontSize=13, leading=20, textColor=INK, spaceAfter=12),
        'title': ParagraphStyle('title', fontName='RDFraunces', fontSize=30, leading=36, textColor=NAVY, spaceAfter=16, keepWithNext=True),
        'head': ParagraphStyle('head', fontName='RDFraunces', fontSize=20, leading=26, textColor=NAVY, spaceBefore=18, spaceAfter=10, keepWithNext=True),
        'label': ParagraphStyle('label', fontName='RDSemibold', fontSize=10, leading=15, textColor=GOLD, spaceBefore=8, spaceAfter=9, keepWithNext=True),
        'small': ParagraphStyle('small', fontName='RDInter', fontSize=10, leading=15, textColor=INK, spaceAfter=12),
        'insight': ParagraphStyle('insight', fontName='RDFraunces', fontSize=16, leading=24, textColor=NAVY, backColor=colors.HexColor('#F7F5EF'), borderColor=colors.HexColor('#D8C9A6'), borderWidth=.6, borderPadding=15, spaceBefore=16, spaceAfter=24),
    }
    def p(text, style='body'):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), styles[style])
    def page_frame(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)
        logo = ROOT / 'logo.webp'
        if logo.exists():
            canvas.drawImage(ImageReader(str(logo)), 48, h-73, width=35, height=35, preserveAspectRatio=True, mask='auto')
        canvas.setFillColor(NAVY)
        canvas.setFont('RDCinzel', 15)
        canvas.drawString(94, h-49, 'RABBI DAVID')
        canvas.setFillColor(GOLD)
        canvas.setFont('RDInter', 8)
        canvas.drawString(94, h-64, 'Ancient Jewish Wisdom for Modern Life')
        canvas.setStrokeColor(colors.HexColor('#D8C9A6'))
        canvas.setLineWidth(.6)
        canvas.line(48, h-85, w-48, h-85)
        canvas.line(48, 49, w-48, 49)
        canvas.setFillColor(INK)
        canvas.setFont('RDInter', 9)
        canvas.drawString(48, 32, 'Your personal reading  |  Rabbi David')
        canvas.drawRightString(w-48, 32, f'Page {doc.page}')
        canvas.restoreState()
    tier_label = {'free':'YOUR OPENING READING', 'reading':'YOUR COMPLETE READING', 'personal':'YOUR PERSONAL READING & ACTION PLAN'}.get(data['tier'], 'YOUR PERSONAL READING')
    story = [p(tier_label, 'label'), p(reading['title'], 'title'), p('Prepared for '+name), p('Based on the priorities you shared. Spiritual reflection, not a prediction or financial advice.', 'small'), HRFlowable(width=42, thickness=2, color=GOLD, spaceAfter=18)]
    if reading.get('summary'): story.append(p(reading['summary']))
    if reading.get('insight'): story.extend([p('A THOUGHT TO CARRY WITH YOU', 'label'), p(reading['insight'], 'insight')])
    evidence = reading.get('evidence', [])
    if evidence:
        story.append(p('How your answers connect', 'head'))
        for item in evidence: story.append(p(item['interpretation']))
    step = reading.get('first_step')
    if step:
        story.extend([p('Your first practical step', 'head'), p(step['action'])])
        for label, key in [('WHY THIS FITS YOU','why'), ('PAUSE & REFLECT','reflection')]:
            if step.get(key): story.extend([p(label,'label'),p(step[key])])
    for i, section in enumerate(reading.get('sections', []), 1):
        story.extend([p(f'{i:02d}  /  '+section['title'], 'head'), p(section['text'])])
        source=_plan_sources().get(section.get('source_id'))
        if source:story.append(p('Source: '+source['title']+' | '+source['url'],'small'))
    if data['tier'] == 'free':
        story.extend([Spacer(1, 12), p('ABOUT THIS EDITION','label'),p('This PDF contains your opening 40% preview. Your complete reading continues with the remaining perspectives.', 'small')])
    if data['tier'] == 'personal' and data.get('plan'):
        story.extend([PageBreak(), p('REFLECTION INTO PRACTICE','label'), p('Your fourteen-day plan','title'), p('Small steps, at your own pace. Adapt each activity to your circumstances. No financial outcome is promised.', 'small')])
        for day in data['plan']:
            day_start = len(story)
            story.extend([p(f"Day {day['day']} / {day['title']}", 'head'), p(str(day['minutes'])+' MINUTES  |  YOUR DAILY PRACTICE','label'),p(day['action'])])
            for label, key in [('REFLECT','reflection'),('MAKE IT YOURS','adaptation')]:
                if day.get(key): story.extend([p(label,'label'),p(day[key])])
            story[day_start:] = [KeepTogether(story[day_start:])]
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=54, leftMargin=54, topMargin=107, bottomMargin=69, title='Your personal reading - Rabbi David', author='Rabbi David')
    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return buf.getvalue()


def _plan_sources():
    """Resolve source IDs only against the editorial library, never model URLs."""
    from source_library import SOURCES
    return {str(item['id']): item for item in SOURCES}


def plan_pdf(data):
    """An independent 17-page plan: cover, guide, fourteen days, and Rabbi David's personal blessing.

    Content is measured before drawing. Oversized input fails explicitly rather
    than overflowing, dropping text or quietly adding an eighteenth page.
    """
    days = data.get('plan') or []
    if len(days) != 14 or [item.get('day') for item in days] != list(range(1, 15)):
        raise ValueError('A plan PDF requires fourteen ordered days, numbered 1–14.')
    sources = _plan_sources()
    answers = data.get('answers') or {}
    name = str(answers.get('name') or 'you')
    legacy = any(not item.get('teaching') or not item.get('why') or not item.get('source_id') for item in days)
    guided = data.get('plan_source') == 'guided'
    buf = BytesIO()
    canvas = pdfcanvas.Canvas(buf, pagesize=A4)
    canvas.setTitle('Your fourteen-day plan - Rabbi David')
    canvas.setAuthor('Rabbi David')
    width, height = A4
    left, right, top, bottom = 54, width - 54, height - 111, 70
    # The fixed page frame leaves a generous reading area and clear page numbers.
    ivory = colors.HexColor('#FBF8F0')
    pale_gold = colors.HexColor('#DACBA6')

    def draw_star_of_david(c, x, y, r=4.2):
        c.saveState()
        c.setStrokeColor(GOLD)
        c.setLineWidth(0.7)
        p1 = c.beginPath()
        for i, a in enumerate([90, 210, 330]):
            rad = math.radians(a)
            px, py = x + r * math.cos(rad), y + r * math.sin(rad)
            if i == 0: p1.moveTo(px, py)
            else: p1.lineTo(px, py)
        p1.close()
        c.drawPath(p1, stroke=1, fill=0)
        p2 = c.beginPath()
        for i, a in enumerate([270, 30, 150]):
            rad = math.radians(a)
            px, py = x + r * math.cos(rad), y + r * math.sin(rad)
            if i == 0: p2.moveTo(px, py)
            else: p2.lineTo(px, py)
        p2.close()
        c.drawPath(p2, stroke=1, fill=0)
        c.restoreState()

    def frame(page, label):
        canvas.setFillColor(ivory)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - 6, width, 6, fill=1, stroke=0)
        logo = ROOT / 'logo.webp'
        if logo.exists():
            canvas.drawImage(ImageReader(str(logo)), left, height - 74, width=35, height=35, preserveAspectRatio=True, mask='auto')
        canvas.setFillColor(NAVY)
        canvas.setFont('RDCinzel', 14)
        canvas.drawString(left + 48, height - 48, 'RABBI DAVID')
        canvas.setFont('RDInter', 8)
        canvas.setFillColor(GOLD)
        canvas.drawString(left + 48, height - 64, 'Ancient Jewish Wisdom for Modern Life')
        canvas.setStrokeColor(pale_gold)
        canvas.setLineWidth(.7)
        canvas.line(left, height - 89, right, height - 89)
        canvas.line(left, 51, right, 51)
        canvas.setFillColor(INK)
        canvas.setFont('RDInter', 8)
        canvas.drawString(left, 34, label)
        canvas.drawRightString(right, 34, f'{page} / 17')

    def render(page, label, items, compact=False):
        """Measure the whole page at a readable size before painting any text."""
        options = [11.8, 11.4, 11.0] if not compact else [10.5, 10.0, 9.5]
        measured = None
        for attempt, size in enumerate(options):
            dense_day = 3 <= page <= 17
            leading = size * ([1.43, 1.35, 1.25][attempt] if dense_day else 1.43)
            title_size = [23, 21, 19][attempt] if dense_day else (27 if page == 1 else 23)
            title_leading = [27, 24, 22][attempt] if dense_day else (31 if page == 1 else 27)
            gap_scale = [1, .75, .45][attempt] if dense_day else 1
            styles = {
                'body': ParagraphStyle('pb', fontName='RDInter', fontSize=size, leading=leading, textColor=INK),
                'title': ParagraphStyle('pt', fontName='RDFraunces', fontSize=title_size, leading=title_leading, textColor=NAVY),
                'label': ParagraphStyle('pl', fontName='RDSemibold', fontSize=9, leading=13, textColor=GOLD),
                'small': ParagraphStyle('ps', fontName='RDInter', fontSize=11 if not compact else size, leading=14 if dense_day else 15, textColor=INK),
                'note_box': ParagraphStyle('pnb', fontName='RDInter', fontSize=11 if not compact else size, leading=14 if dense_day else 15, textColor=NAVY),
                'signature': ParagraphStyle('psig', fontName='RDFraunces', fontSize=18, leading=22, textColor=NAVY),
                'signature_sub': ParagraphStyle('psigsub', fontName='RDCinzel', fontSize=9.5, leading=13, textColor=GOLD),
                'signature_bless': ParagraphStyle('psigbless', fontName='RDInter', fontSize=10, leading=14, textColor=INK, leftIndent=16),
            }
            measured = []
            total = 0
            for text, style, gap in items:
                gap *= gap_scale
                paragraph = Paragraph(escape(str(text)).replace('\n', '<br/>'), styles[style])
                _, ph = paragraph.wrap(right-left, height)
                measured.append((paragraph, ph, gap, style))
                total += ph + gap
            if total <= top-bottom:
                break
        else:
            raise ValueError(f'Plan page {page} exceeds its readable page area ({total:.0f} points needed, {top-bottom:.0f} available); shorten the supplied content.')
        frame(page, label)
        y = top
        for paragraph, ph, gap, style in measured:
            if style == 'signature':
                canvas.saveState()
                canvas.setStrokeColor(GOLD)
                canvas.setLineWidth(1.5)
                canvas.line(left, y + 2, left + 42, y + 2)
                canvas.restoreState()
            elif style == 'signature_bless':
                draw_star_of_david(canvas, left + 5, y - ph / 2, 4.2)
            paragraph.drawOn(canvas, left, y-ph)
            y -= ph + gap
        canvas.showPage()

    from content import route
    labels = {}
    for question in route(answers):
        key = question['id']
        for option in question.get('options', []):
            if str(option['value']) == str(answers.get(key)):
                labels[key] = option['label']
    profile = [('Your focus', labels.get('goal')), ('The time you chose', labels.get('time')), ('Your preferred approach', labels.get('style')), ('What to take into account', labels.get('obstacle'))]
    cover = [('YOUR FOURTEEN-DAY COMPANION', 'label', 17), ('A Little Wisdom.\nA Step of Your Own.', 'title', 23), ('Prepared for ' + name, 'body', 22), ('Fourteen days of reflection and practical exercises. Read one page each day, take the step that fits, and notice what you learn.', 'body', 22)]
    for title, value in profile:
        if value:
            cover.extend([(title.upper(), 'label', 5), (value, 'body', 13)])
    if not any(value for _, value in profile):
        cover.append(('The priorities from this saved edition are not available here. The daily pages below reproduce your saved plan without inferring personal details.', 'small', 16))
    if guided:
        cover.append(('GUIDED EDITION: These exercises use your chosen priority and practice time. Your detailed personal plan could not be completed yet. You can request it again from your reading.', 'small', 14))
    elif legacy:
        cover.append(('SAVED EARLIER EDITION: Some daily teaching, source or explanation fields were not part of this plan. Those omissions are clearly marked. No new personal explanation has been invented.', 'small', 14))
    cover.append(('Educational and spiritual reflection. This plan does not predict events or promise a financial outcome.', 'small', 0))
    render(1, 'Your fourteen-day plan', cover)
    render(2, 'How to use your plan', [
        ('BEGIN WHERE YOU ARE', 'label', 12), ('How to Use These Pages', 'title', 19),
        ('Read one day at a time. You do not need to catch up if you miss a day. Return when you can and choose a pace you can sustain.', 'body', 17),
        ('FIRST: READ THE TEACHING', 'label', 5), ('Where included, this is a reflection connected to a named text in the source library. It is a paraphrase or interpretation, not a claim that the source prescribed your daily exercise.', 'body', 16),
        ('THEN: TRY THE MODERN EXERCISE', 'label', 5), ('The action, reflection and adaptation are contemporary prompts. Use what fits your life. You may shorten a step, speak instead of write, or skip an activity that does not suit your circumstances.', 'body', 16),
        ('LOOK FOR SMALL, OBSERVABLE CHANGES', 'label', 5), ('Notice whether you can name a priority more clearly, keep a manageable routine or approach a conversation more thoughtfully. These are things to observe, not results you are expected to achieve.', 'body', 16),
        ('KEEP A SIMPLE NOTE', 'label', 5), ('After each day, record one sentence: What did I try, and what did I notice? A notebook you already own or a spoken reflection is enough. No purchase or donation is needed.', 'body', 16),
        ('YOUR PACE BELONGS TO YOU', 'label', 5), ('This material is not financial, legal, medical or mental-health advice. Seek qualified help for decisions that need it. The plan is a companion for reflection, not a substitute for personal support.', 'small', 0),
    ])
    from book_bridge import resolve_book_recommendation
    rec = resolve_book_recommendation(answers)

    for day in days:
        dnum = day['day']
        sid = str(day.get('source_id') or '')
        source = sources.get(sid)
        items = [(f"DAY {dnum:02d} OF 14  ·  {day.get('minutes', 'Your chosen')} MINUTES", 'label', 8), (str(day.get('title') or 'Your daily practice'), 'title', 15)]
        teaching = day.get('teaching')
        if teaching:
            items.extend([('A TEACHING TO CONSIDER', 'label', 5), (teaching, 'body', 9)])
            if source:
                items.append(('Source: ' + str(source['title']), 'small', 12))
            else:
                items.append(('No verified source reference was saved for this teaching. Treat it as an unattributed reflection, not a quotation from a traditional text.', 'small', 12))
        elif guided:
            items.extend([('A GUIDED PRACTICE', 'label', 5), ('An original reflection based on your chosen priority. This edition does not include a separate daily teaching or source commentary.', 'small', 14)])
        else:
            items.extend([('ABOUT THIS SAVED EDITION', 'label', 5), ('A separate teaching and source were not included in this earlier plan. The modern exercise below is preserved as saved.', 'small', 14)])
        if day.get('why'):
            items.extend([('WHY THIS STEP WAS CHOSEN', 'label', 5), (day['why'], 'body', 12)])
        items.extend([('YOUR MODERN PRACTICE', 'label', 5), (str(day.get('action') or 'No action was saved for this day.'), 'body', 12), ('PAUSE & REFLECT', 'label', 5), (str(day.get('reflection') or 'What did you notice today?'), 'body', 12), ('MAKE IT WORK FOR YOU', 'label', 5), (str(day.get('adaptation') or 'You may shorten this practice or pause and return later.'), 'body', 0 if dnum not in (3, 7, 14) else 8)])

        mkey = f"day{dnum}"
        if mkey in rec.get('milestones', {}):
            m_text = rec['milestones'][mkey]
            items.extend([
                ('SACRED MILESTONE · DEEPENING IN THE TEXT', 'label', 4),
                (f"Rabbi David's Note: For the sacred vessel-sealing formulas of Day {dnum:02d}, consult '{rec['title']}' ({m_text}).", 'note_box', 0)
            ])

        render(dnum+2, f"Day {dnum:02d} | Your saved daily practice", items)

    display_name = name if name and name.lower() != 'you' else 'Friend'
    goal_label = labels.get('goal')
    time_label = labels.get('time')
    obstacle_label = labels.get('obstacle')

    if goal_label:
        goal_phrase = f"seeking {goal_label.lower()}"
    else:
        goal_phrase = "seeking a deeper sense of peace and purposeful abundance"

    if time_label:
        time_phrase = f"devoting {time_label.lower()} each day"
    else:
        time_phrase = "setting aside quiet moments each day"

    if obstacle_label:
        obstacle_phrase = f"even while navigating {obstacle_label.lower()}"
        obstacle_sentence = f"Never let {obstacle_label.lower()} or the noise of daily demands lead you to believe your steps are too small."
    else:
        obstacle_phrase = "even amidst the pressures of daily life"
        obstacle_sentence = "Never let the noise and haste of the world lead you to believe your steps are too small."

    p1 = (
        f"My friend {display_name}, as we complete these fourteen days together, I write to you not to give you "
        f"another task or obligation, but to offer a personal pastoral blessing for your journey. When you began "
        f"these pages, you shared that your heart is {goal_phrase}. In our sacred tradition, we know that true "
        f"abundance—berachah—is not the frantic accumulation of more possessions, but the deep presence of peace (shalom) "
        f"and gratitude within what you already hold."
    )
    p2 = (
        f"You chose to give your time to this daily practice, {time_phrase}, {obstacle_phrase}. "
        f"In the eyes of Heaven, a single honest pause and an intentional act of goodness carry greater weight than years "
        f"of rushed ambition. {obstacle_sentence} Every time you choose integrity, patience, and kindness in your daily decisions, "
        f"you build an enduring vessel for blessing in your home, your family, and your livelihood."
    )
    p3 = (
        "As you walk forward beyond this companion, may you move with quiet confidence and courage, knowing you are never "
        "alone in your striving. May the Almighty watch over you and keep you. May light illuminate your path, and may peace, "
        "health, and true prosperity accompany every step you take."
    )
    p_companion = (
        f"For your continued journey beyond these fourteen days, I have designated '{rec['title']}' as your foundational companion. "
        "Return to its teachings whenever you need to fortify your vessel against dissipation."
    )

    page17_items = [
        ('A PASTORAL BLESSING FROM RABBI DAVID', 'label', 12),
        (f'Walking Forward in Peace & Blessing, {display_name}', 'title', 16),
        (p1, 'body', 12),
        (p2, 'body', 12),
        (p3, 'body', 12),
        (p_companion, 'small', 14),
        ('Rabbi David', 'signature', 3),
        ('Rav David ben-Avraham · Jerusalem', 'signature_sub', 10),
        ('May peace and blessing rest upon the work of your hands.', 'signature_bless', 0),
    ]
    render(17, 'A personal blessing from Rabbi David', page17_items)
    canvas.save()
    return buf.getvalue()

