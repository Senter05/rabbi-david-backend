"""Versioned editorial content. Personal plans are draft educational exercises."""
VERSION = '2026-09-16-mobile-results-v6'

def choice(key, title, hint, options):
    return dict(id=key, title=title, hint=hint, type='choice', options=[dict(value=v,label=l) for v,l in options])

QUESTIONS = [
    choice('goal','What would you most like to work on right now?','Choose one priority for your reading.',[
        ('calm','More peace around money'),('direction','Clearer everyday priorities'),('family','A more supported family'),('legacy','A meaningful legacy'),('work','More purpose in my work'),('learning','Time to learn and grow')]),
    choice('stage','What best describes your everyday life right now?','If several fit, choose the one that shapes your days most.',[
        ('working','Working or running a business'),('retired','Retired'),('transition','Making a life change'),('caring','Caring for someone'),('other','Something else'),('private','I prefer not to say')]),
    choice('need','What would be most useful to take away from your reading?','Choose what you need now, even if you have tried it before.',[
        ('perspective','A fresh perspective'),('routine','A simple routine'),('conversation','A thoughtful conversation'),('confidence','Confidence in my next step'),('curiosity','Exploring with no particular problem')]),
    choice('feeling','How do you feel about this part of your life today?','Choose the closest fit. There is no right answer.',[
        ('hopeful','Hopeful'),('uncertain','Uncertain'),('overwhelmed','A little overwhelmed'),('content','Content, and curious to learn'),('mixed','A mixture'),('private','I prefer not to say')]),
    choice('experience','Think of a difficult decision you faced. What helped you see it more clearly?','Choose what actually helped. It is fine to be unsure.',[
        ('reflection','Quiet reflection or prayer'),('writing','Writing things down'),('talking','Talking with someone I trust'),('learning','Reading and learning'),('new','I am trying something new'),('unsure','I am not sure what helps yet')]),
    choice('time','How much time would comfortably fit one daily exercise?','This adapts your activities and optional plan, not the length of this test.',[
        ('5','About 5 minutes'),('10','About 10 minutes'),('15','About 15 minutes'),('flexible','I need something flexible')]),
    choice('style','How would you like Jewish wisdom explained in your reading?','No religious knowledge or belief is required.',[
        ('balanced','Spiritual reflection and everyday application'),('spiritual','More spiritual, with concepts explained'),('practical','Mostly practical, with light spiritual context')]),
    choice('pace','What would help you return to a small practice during a busy week?','Choose the structure that would fit your life.',[
        ('gentle','A gentle pace, with room to pause'),('structure','A clear daily structure'),('flexible','Options I can adapt'),('accountability','A weekly moment to review')]),
    choice('obstacle','What most often makes it difficult to take a small step?','This helps us keep your activities realistic.',[
        ('time','Limited time'),('energy','Limited energy'),('cost','I need no-cost activities'),('unclear','Not knowing where to begin'),('none','Nothing in particular')]),
    dict(id='note',title='In your own words, what is happening in your life right now that you wish to transform?',hint='The more detail and context you share about your situation, challenges, and goals, the deeper, richer, and more accurate Rabbi David’s personal reading will be for your life. (Optional, but highly recommended).',type='text',optional=True,maxLength=1200),
]
BRANCHES = {
    'calm':[choice('focus','Which concern about money would you most like to reflect on?','Choose the closest fit. No amounts or account details are needed.',[('uncertainty','Living with uncertainty about the future'),('comparison','Comparing what I have with others'),('choices','Making everyday choices with less pressure'),('enough','Knowing what is enough for me'),('exploring','Exploring my relationship with money')])],
    'family':[choice('focus','Where would you most like a change in family life?','Choose one area. You do not need to name anyone.',[('listening','Listening more closely'),('boundaries','Clearer boundaries'),('together','Time together'),('values','Sharing our values')])],
    'legacy':[choice('focus','What would you most like to leave for others to carry forward?','This can be something you share now.',[('stories','Family stories'),('values','Values and wisdom'),('conversation','An important conversation'),('habits','Helpful habits')])],
    'work':[choice('focus','Which part of your working life needs attention?','Choose what matters most at the moment.',[('purpose','Meaning and purpose'),('balance','Balance and rest'),('integrity','Acting on my values'),('next','My next step at work')])],
    'direction':[choice('focus','Where would clearer priorities make the biggest difference?','Choose one place to begin.',[('routine','A steadier routine'),('learning','Learning something meaningful'),('space','Less unnecessary busyness'),('choice','One clearer decision')])],
    'learning':[choice('focus','Which idea would you most like to understand and use?','We will explain it through everyday examples.',[('gratitude','Gratitude and appreciating what I have'),('purpose','Purpose and responsibility'),('tradition','Jewish wisdom and tradition'),('habits','Thoughtful everyday habits')])]
}

# Preserve the meaning of money answers saved before the revised concern question.
LEGACY_MONEY_FOCUS = choice('focus','When would a calmer approach to money-related concerns help you most?','Choose a time or situation for your first reflection.',[('morning','The start of my day'),('evening','The end of my day'),('decisions','Before everyday decisions'),('general','In general')])

def route(answers):
    branch=BRANCHES.get(answers.get('goal'),[])
    if answers.get('goal')=='calm' and answers.get('focus') in {o['value'] for o in LEGACY_MONEY_FOCUS['options']}:
        branch=[LEGACY_MONEY_FOCUS]
    base=QUESTIONS[:2]+branch+QUESTIONS[2:]
    if answers.get('obstacle')=='cost':
        base=base[:-1]+[choice('no_cost','Which no-cost approach suits you?','No purchase or donation is needed to take part.',[('journal','Use a notebook I already have'),('quiet','A quiet spoken reflection'),('conversation','A conversation with someone I trust')])]+base[-1:]
    return base

GOALS = {
 'calm':dict(title='A calmer relationship with abundance',theme='calm',book='rituals',insight='You are looking for a little more steadiness, rather than another demand on your attention.',action='Notice one moment when you feel settled. Write what made that moment different.'),
 'direction':dict(title='Clearer priorities for everyday life',theme='priorities',book='rituals',insight='Your answers point toward making room for what matters, one deliberate choice at a time.',action='Write down one priority you want to give attention to, and one task that can wait.'),
 'family':dict(title='Abundance in the life you share',theme='connection',book='legacy',insight='For you, abundance includes the quality of the support and understanding within your family.',action='Write one question you could ask a family member with the intention of listening.'),
 'legacy':dict(title='The legacy only you can share',theme='legacy',book='legacy',insight='Your priority is what you can pass on: experience, stories, values and thoughtful habits.',action='Write one short story about a value you learned through experience.'),
 'work':dict(title='Purpose in the work of your hands',theme='purpose',book='rituals',insight='You want your everyday work and your values to feel more connected.',action='Name one value you want your next ordinary work decision to express.'),
 'learning':dict(title='Learning with purpose',theme='learning',book='rituals',insight='Curiosity is a worthwhile starting point. You do not need to invent a problem to explore a new perspective.',action='Choose one question about abundance you would like to understand more clearly.')
}

PRACTICES = [
 dict(id='enough',title='Notice what already supports you',time='5 minutes',image='torah-desk.webp',concept='Gratitude',intro='A reflection on appreciating what you have, inspired by Pirkei Avot 4:1.',steps=['Choose a comfortable place. No special objects are needed.','Name three ordinary things that supported you today.','Choose one of them and write why it mattered.','Close with an intention to notice it again tomorrow.'],source='https://www.sefaria.org/Pirkei_Avot.4.1',sourceLabel='Pirkei Avot 4:1',note='This is an original reflective exercise, not a traditional prescribed ritual or a promise of financial gain.'),
 dict(id='intention',title='Give one small action a purpose',time='5 minutes',image='torah-open.webp',concept='Intention',intro='Make room for personal responsibility without trying to change everything at once.',steps=['Name one value you want to express today.','Choose a small action within your control.','Write when and where you could do it.','At the end of the day, notice what you learned.'],source='https://www.sefaria.org/Pirkei_Avot.1.14',sourceLabel='Pirkei Avot 1:14',note='An original application for reflection. You can adapt or skip any step.'),
 dict(id='legacy',title='Leave a few words worth keeping',time='10 minutes',image='torah-desk.webp',concept='Connection',intro='A short writing practice for the experiences and values you want to share.',steps=['Think of a lesson that changed how you treat people.','Write the story in a few sentences.','Add what you hope someone else might take from it.','Keep it privately or share it with someone you choose.'],source=None,sourceLabel='Original Rabbi David reflection',note='No special materials, purchase or donation are required.')
]

DAY_TITLES=['Begin where you are','Notice your resources','Make your intention small','Create a gentle cue','Listen to your own words','Make room for another perspective','Review your first week','Return to what helped','Practise one deliberate choice','Share or record a lesson','Notice what can wait','Repeat without adding more','Name what has changed','Choose what to carry forward']

def fallback_reading(a):
    g=GOALS[a['goal']]; name=a.get('name') or 'Friend'
    labels={q['id']:{o['value']:o['label'] for o in q.get('options',[])} for q in route(a)}
    picked=lambda k:labels.get(k,{}).get(a.get(k),'your preferred approach')
    return dict(title=g['title'],summary=f"{name}, {g['insight']} You chose {picked('time').lower()} and {picked('style').lower()}.",insight=g['action'],sections=[
      dict(title='What your answers tell us',text=f"Your chosen priority is {g['theme']}. You described this season as {picked('stage').lower()}, and said that {picked('need').lower()} would help. These are preferences you shared, not a diagnosis."),
      dict(title='A perspective to consider',text='Abundance can include attention, relationships, meaning and the resources already available to you. Noticing these does not deny practical challenges; it helps you decide what deserves your energy.'),
      dict(title='An approach that respects your pace',text=f"You prefer {picked('pace').lower()}. You said your main constraint is {picked('obstacle').lower()}. Choose a pace that leaves room for your real circumstances, rather than treating reflection as another obligation."),
      dict(title='A question to return to',text=f"What would a small, meaningful improvement in {g['theme']} look like to you? You can change your answer as you learn. Your reading is an invitation to reflect, not a prediction of what will happen.")])

def draft_plan(a):
    g=GOALS[a['goal']]; minutes=a.get('time','5'); minutes=minutes if minutes in ('5','10','15') else '5'
    actions=[g['action'],'List three supports you already have: a habit, a person, or a resource.','Choose one small intention related to your priority. Write it in your own words.','Choose a comfortable time and place for this reflection.','Read yesterday\'s intention. Make it simpler if it feels demanding.','Consider how someone you trust might see your chosen priority.','Look back over the week. Keep one thing that helped and set aside one that did not.',g['action'],'Repeat one useful action from last week. Notice how it feels this time.','Write a short lesson from your own experience. Share it only if you want to.','Name one unnecessary demand you can set aside for today.','Return to your most useful practice without making it longer.','Describe a change in clarity, consistency or understanding, if you noticed one. It is also okay to record no change.','Choose one practice to keep and one question to revisit next week.']
    return [dict(day=i+1,title=t,minutes=int(minutes),action=actions[i],reflection=f"How did this connect with your wish for {g['theme']}?",adaptation='Use a spoken reflection instead of writing if that suits you better.' if a.get('experience')=='reflection' or a.get('no_cost')=='quiet' else 'Use materials you already have. Pause or shorten this activity whenever you need to.') for i,t in enumerate(DAY_TITLES)]
