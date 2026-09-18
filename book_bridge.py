"""Book Bridge and Recommendation Engine for Rabbi David.

Maps user questionnaire answers and personal open-ended reflections ('note')
to their root financial leak and the optimal ancestral book companion.
Generates authoritative pastoral bridges for Rabbi David's audio narration
and 14-day plan milestones.
"""
import re

BOOK_CATALOG = {
    'rituals': {
        'id': 'rituals',
        'title': 'The 7 Hidden Money Rituals of Secret Jewish Dynasties',
        'price': 32,
        'currency': 'USD',
        'cover': '/images/cover-rituals.webp',
        'detailPage': 'the-seven-jewish-money-rituals.html',
        'theme': 'Daily physical rituals, sealing money leakage, tangible abundance',
        'key_ritual': 'Ritual 1: The Salt in the Wallet (Sealing the vessel against daily dissipation) and Ritual 6: Washing Hands with Intention',
        'milestones': {
            'day3': 'Ritual 3: The Hebrew Word Before Sleep (Kavanah for overnight financial peace)',
            'day7': 'Ritual 1: The Salt in the Wallet & Ritual 4: The 3 Coins of Consecration',
            'day14': 'Ritual 7: The Sacred Anchor in Your Pocket'
        },
        'leak_diagnosis': 'your primary leak is neither your effort nor your willingness to work. Your leak is daily dissipation—money enters your hands, yet unseen spiritual entropy and lack of physical boundaries cause it to dissolve like vapor before dusk.',
        'audio_bridge': "In your answers, and in the unspoken weight you carry, I see clearly: your primary leak is not a lack of hard work. You work with diligence. Your leak is dissipation—money enters your hands, yet it slips through like water through unsealed fingers. That is why I prepared 'The 7 Hidden Money Rituals of Secret Jewish Dynasties'. In Ritual 1—the Salt in the Wallet—and in Ritual 6, I teach the exact ancient physical disciplines that seal the daily vessel so what you earn can actually settle and remain in your home."
    },
    'ceo': {
        'id': 'ceo',
        'title': 'Ancient Jewish Rules for Commercial Dominance',
        'price': 46,
        'currency': 'USD',
        'cover': '/images/cover-commercial.webp',
        'detailPage': 'torah-ceo-code.html',
        'theme': 'Business strategy, negotiation silence, partnership vetting, market leverage',
        'key_ritual': 'Law 1: The Sealed Hand & Law 3: The Negotiation Silence (The power of pauses in commerce)',
        'milestones': {
            'day3': 'Law 1: The Sealed Hand (Guard your true numbers from competitor scrutiny)',
            'day7': 'Law 3: The Negotiation Silence & Law 2: The Partnership Crucible',
            'day14': 'Law 6: The Debt Doctrine & Law 12: Building Commercial Autonomy'
        },
        'leak_diagnosis': 'your primary leak is in commercial posture and negotiation leverage. You give away your position too early, over-explain in transactions, and carry burdens that belong to clients or partners rather than maintaining the sealed hand of the ancient merchants.',
        'audio_bridge': "In your professional striving, I see clearly: your primary leak is not your skill or the merit of your work. Your leak is in commercial posture and negotiation leverage. In the marketplace, over-explaining and revealing your bottom line prematurely strips you of power. That is why I wrote 'Ancient Jewish Rules for Commercial Dominance'. In Law 1—The Sealed Hand—and Law 3—The Negotiation Silence—I lay down the exact 3,000-year-old principles our sages used to command respect, negotiate without desperation, and dominate commerce with absolute integrity."
    },
    'legacy': {
        'id': 'legacy',
        'title': 'The Generational Vault: Wealth That Outlives You 4 Generations',
        'price': 62,
        'currency': 'USD',
        'cover': '/images/cover-generational.webp',
        'detailPage': 'generational-wealth.html',
        'theme': 'Dynastic legacy, family constitution, protecting children from ruin, 100-year plan',
        'key_ritual': 'Chapter 1: The Family Constitution & Chapter 2: The Inheritance Architecture',
        'milestones': {
            'day3': 'Chapter 3: The Money Curriculum for Young Heirs',
            'day7': 'Chapter 1: Establishing the Family Constitution',
            'day14': 'Chapter 5: The Fortress Strategy & Chapter 11: The 100-Year Plan'
        },
        'leak_diagnosis': 'your deepest concern is generational continuity. You fear that without a written spiritual and financial constitution, everything you labor to accumulate will be scattered or squandered by the next generation within thirty years.',
        'audio_bridge': "In what you shared with me regarding your family and your future, I hear the soul of a true builder. Your deepest concern is not merely surviving this year, but ensuring that your children and grandchildren do not lose what you have fought so hard to build. That is why I created 'The Generational Vault: Wealth That Outlives You 4 Generations'. In Chapter 1, I detail the Family Constitution—the exact written document that the greatest Jewish dynasties have used for centuries to prepare the heirs for the wealth, rather than merely leaving the wealth to unprepared heirs."
    },
    'protection': {
        'id': 'protection',
        'title': 'The Jewish Shield Against Financial Ruin',
        'price': 49,
        'currency': 'USD',
        'cover': '/images/cover-shield.webp',
        'detailPage': 'the-jewish-wealth-protection-code.html',
        'theme': 'Asset protection, crisis immunity, surviving market shocks, legal and debt shields',
        'key_ritual': 'Chapter 1: The Crisis Playbook (The Covenant of Reserves) & Chapter 2: The Guardian Protocol',
        'milestones': {
            'day3': 'Chapter 1: The Three Shields of Liquid Capital',
            'day7': 'Chapter 2: The Guardian Protocol (Thirty-Year Horizon Audit)',
            'day14': 'Chapter 6: The Operational Codex for Unshakeable Resilience'
        },
        'leak_diagnosis': 'your primary leak is defensive vulnerability. You build and strive without an impenetrable shield of reserves and structural custody, causing sudden economic shocks, debts, or external crises to threaten your peace of mind.',
        'audio_bridge': "Looking at the pressures you face, let me give you this pastoral truth: your principal leak is not a lack of ambition; it is vulnerability. In times of storm, the wise builder does not begin patching the roof; he stands inside a fortress already reinforced. That is why I authored 'The Jewish Shield Against Financial Ruin'. In Chapter 1—The Crisis Playbook—I reveal the ancient Covenant of Reserves and the three shields of asset immunity that protected our ancestors across centuries of economic upheaval."
    },
    'morning': {
        'id': 'morning',
        'title': "The Rabbi's Morning Wealth Blessing",
        'price': 22,
        'currency': 'USD',
        'cover': '/images/ebook-prayer-cover.webp',
        'detailPage': 'morning-wealth-blessing.html',
        'theme': 'Morning prayer, dawn devotions, overcoming morning panic, Parnasá Tová',
        'key_ritual': 'Chapter 1: The Mystery of Parnasá Tová & Chapter 3: The Moses Secret (Psalm 90:17)',
        'milestones': {
            'day3': 'Chapter 2: The Altar of the Kitchen Table at Dawn',
            'day7': 'Chapter 3: The Moses Secret & The Twofold Establishment Prayer',
            'day14': 'Chapter 14: The Full Liturgical System of 7 Morning Wealth Prayers'
        },
        'leak_diagnosis': 'your primary leak occurs in the first twenty minutes of your day. You awaken with a knot of anxiety in your chest, reacting to demands rather than sanctifying the threshold of dawn with the sacred prayer of honorable sustenance (Parnasá Tová).',
        'audio_bridge': "I recognize the heaviness you carry when the sun rises. Your battle is won or lost in the first twenty minutes of each morning. When you awaken in panic or hurry, the spiritual vessel contracts before your feet even touch the floor. That is why I wrote 'The Rabbi\'s Morning Wealth Blessing'. In Chapter 1 and Chapter 3, I share the ancient prayer of Moses from Psalm 90:17 and the sacred liturgical protocol that aligns your soul with unshakeable provision before the marketplace demands your energy."
    },
    'complete': {
        'id': 'complete',
        'title': 'The Master Kabbalah Wealth System: The 30-Day Financial Vault',
        'price': 120,
        'currency': 'USD',
        'cover': '/images/cover-kabbalah.webp',
        'detailPage': 'the-complete-rabbis-wealth-system.html',
        'theme': 'Complete financial overhaul, 30-day daily calendar, master abundance vault',
        'key_ritual': 'Week 1: The Purification and Opening & Week 2: Vessel Construction',
        'milestones': {
            'day3': 'Day 3 of the Master Calendar: The Complaint Fast',
            'day7': 'Day 7 of the Master Calendar: The Shabbat of Abundance Ceremony',
            'day14': 'Day 14 of the Master Calendar: The Midpoint Accounting and Vessel Sealing'
        },
        'leak_diagnosis': 'your leak is fragmentation. You have tried isolated financial tips and sporadic intentions, but your vessel lacks an integrated thirty-day discipline combining physical purification, prayer, and structural wealth building.',
        'audio_bridge': "You have accumulated scattered advice and made sincere efforts, yet the transformation remains incomplete because your approach has been fragmented. A vessel cannot be half-built. That is why I assembled 'The Master Kabbalah Wealth System: The 30-Day Financial Vault'. It provides the unbroken thirty-day blueprint—from the Day 1 Wallet Clearing to the Day 30 Final Blessing—that guides you through every single morning and evening to completely restructure your relationship with wealth."
    }
}


def _matches_any(text, patterns):
    for pat in patterns:
        if ' ' in pat:
            if pat in text:
                return True
        else:
            if re.search(r'\b' + re.escape(pat), text, re.IGNORECASE):
                return True
    return False


def resolve_book_recommendation(answers):
    """Analyze questionnaire answers and the open-ended note to recommend the exact book."""
    note = (answers.get('note') or answers.get('personal_detail') or '').strip().lower()
    goal = answers.get('goal', 'calm')
    focus = answers.get('focus', '')
    obstacle = answers.get('obstacle', '')
    stage = answers.get('stage', '')

    # 1. High-priority keyword intent matching from user's own words ('note')
    if note:
        # Children / Kids / Family inheritance / Legacy / Generational (prioritized over general protection)
        if _matches_any(note, ['child', 'children', 'son', 'daughter', 'kids', 'family', 'inherit', 'generat', 'grandchild', 'legacy', 'pass down', 'heir']):
            target = BOOK_CATALOG['legacy']
            return _enrich_recommendation(target, answers, 'family_intent')

        # Crisis / Ruin / Lawsuit / Foreclosure / Debt terror / Asset loss / Vulnerability
        if _matches_any(note, ['bankrupt', 'ruin', 'lawsuit', 'losing house', 'foreclos', 'reposses', 'scared of losing', 'crash', 'inflation', 'crisis', 'terrified', 'shield', 'vulnerab']):
            target = BOOK_CATALOG['protection']
            return _enrich_recommendation(target, answers, 'crisis_intent')

        # Commercial / Business / Clients / Negotiations
        if _matches_any(note, ['business', 'client', 'clients', 'sales', 'company', 'partner', 'negotiat', 'boss', 'freelanc', 'career', 'job', 'promot', 'employe', 'market']):
            target = BOOK_CATALOG['ceo']
            return _enrich_recommendation(target, answers, 'business_intent')

        # Morning panic / dawn anxiety / morning dread
        if _matches_any(note, ['morning panic', 'morning anxiety', 'wake up in panic', 'wake up terrified', 'morning dread', 'dawn dread', 'anxiety at dawn', 'panic at dawn', 'morning terror']) or (_matches_any(note, ['morning', 'wake up', 'waking up', 'dawn']) and _matches_any(note, ['panic', 'dread', 'terror', 'anxiety', 'knot in my chest', 'depress'])):
            target = BOOK_CATALOG['morning']
            return _enrich_recommendation(target, answers, 'morning_anxiety_intent')

        # Complete 30-day overhaul / Master vault / Kabbalah system
        if _matches_any(note, ['complete', '30-day', '30 day', 'overhaul', 'kabbalah', 'master system', 'all-in-one']):
            target = BOOK_CATALOG['complete']
            return _enrich_recommendation(target, answers, 'complete_system_intent')

        # Living paycheck to paycheck / money disappears / debt / rituals / bad luck
        if _matches_any(note, ['paycheck', 'month to month', 'drown', 'debt', 'disappear', 'slip', 'drain', 'curse', 'ritual', 'luck', 'barely', 'broke', 'dissipat']):
            target = BOOK_CATALOG['rituals']
            return _enrich_recommendation(target, answers, 'money_leak_intent')

    # 2. Match by questionnaire goal and focus
    if goal in ('legacy', 'family') or focus in ('stories', 'values', 'habits'):
        target = BOOK_CATALOG['legacy']
    elif goal == 'work' or stage == 'working':
        target = BOOK_CATALOG['ceo']
    elif obstacle == 'cost' or focus in ('uncertainty', 'choices', 'enough'):
        target = BOOK_CATALOG['rituals']
    elif goal == 'learning':
        target = BOOK_CATALOG['complete']
    elif goal == 'calm':
        target = BOOK_CATALOG['rituals']
    else:
        target = BOOK_CATALOG['rituals']

    return _enrich_recommendation(target, answers, 'goal_match')


def _enrich_recommendation(target, answers, match_reason):
    name = (answers.get('name') or 'my friend').strip()
    note_text = (answers.get('note') or answers.get('personal_detail') or '').strip()

    # Contextualize leak diagnosis with user's specific words if available
    diagnosis = target['leak_diagnosis']
    if note_text:
        short_note = note_text[:90].strip()
        if not short_note.endswith('.'):
            short_note += '...'
        personal_context = f'Regarding what you described—"{short_note}"—'
    else:
        personal_context = ''

    audio_speech = target['audio_bridge'].replace('{name}', name)

    return {
        'id': target['id'],
        'title': target['title'],
        'price': target['price'],
        'currency': target['currency'],
        'cover': target['cover'],
        'detailPage': target['detailPage'],
        'theme': target['theme'],
        'key_ritual': target['key_ritual'],
        'milestones': target['milestones'],
        'match_reason': match_reason,
        'personal_context': personal_context,
        'leak_diagnosis': f"{personal_context}{diagnosis}",
        'audio_bridge_script': audio_speech
    }
