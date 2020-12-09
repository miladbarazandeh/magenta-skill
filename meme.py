import random
import sqlite3
from typing import Optional, Tuple

from skill_sdk import skill, Response, tell, ask
from skill_sdk.l10n import _
from skill_sdk import context

import nltk, string
from sklearn.feature_extraction.text import TfidfVectorizer

# nltk.download('punkt') # if necessary...


stemmer = nltk.stem.porter.PorterStemmer()
remove_punctuation_map = dict((ord(char), None) for char in string.punctuation)

def stem_tokens(tokens):
    return [stemmer.stem(item) for item in tokens]

'''remove punctuation, lowercase, stem'''
def normalize(text):
    return stem_tokens(nltk.word_tokenize(text.lower().translate(remove_punctuation_map)))

vectorizer = TfidfVectorizer(tokenizer=normalize)

def cosine_sim(text1, text2):
    tfidf = vectorizer.fit_transform([text1, text2])
    return ((tfidf * tfidf.T).A)[0,1]



INTENT_NAME_CARD = 'TEAM_12_FRAGEN_CARD'
INTENT_NAME_MEMORIEREN = 'TEAM_12_MEMORIEREN'

connection = sqlite3.connect('/home/fateme/magenta/memebonanza-skill/assets/questions.db')



def get_last_quiz(user_id) -> Tuple:
    cursor = connection.cursor()
    cursor.execute("select id, quiz, answer, topic from questions where user_id = ? order by id desc limit 1", [user_id])
    question = cursor.fetchone()
    
    return question

def has_open_question(user_id) -> bool:
    question = get_last_quiz(user_id)
    if question is None or (question[0] and question[1] and question[2] and question[3]):
        return False
    else:
        return True

def has_open_question_no_quiz(user_id) -> bool:
    question = get_last_quiz(user_id)
    if question[0] and question[1] is None and question[2] is None:
        return True
    else:
        return False

def has_open_question_no_answer(user_id) -> bool:
    question = get_last_quiz(user_id)
    if question[2] is None and question[0] and question[1]:
        return True
    else:
        return False

def has_open_question_no_topic(user_id) -> bool:
    question = get_last_quiz(user_id)
    if question[3] is None and question[0] and question[1]:
        return True
    else:
        return False

@skill.intent_handler(INTENT_NAME_CARD)
def handler_card(text: str) -> Response:
    print('*******')
    print(context)
    user_id = '2'
    if not has_open_question(user_id):
        cursor = connection.cursor()
        cursor.execute("insert into questions (user_id) values (?) ", [user_id])
        connection.commit()
        msg = _('ASK_YOUR_QUESTION')
        return ask(msg)
    elif has_open_question_no_quiz(user_id):
        cursor = connection.cursor()
        question = get_last_quiz(user_id)
        cursor.execute("update questions set quiz = ? where id = ?", [text, question[0]])
        connection.commit()
        msg = _('INSERT_YOUR_ANSWER')
        return ask(msg)
    elif has_open_question_no_answer(user_id):
        cursor = connection.cursor()
        question = get_last_quiz(user_id)
        cursor.execute("update questions set answer = ? where id = ?", [text, question[0]])
        connection.commit()
        msg = _('WHAT_IS_THE_TOPIC')
        return ask(msg)
    else:
        cursor = connection.cursor()
        question = get_last_quiz(user_id)
        cursor.execute("update questions set topic = ? where id = ?", [text, question[0]])
        connection.commit()
        msg = _('DONE')
        return tell(msg)
        

    print("AFTER ALL IFS")


def start_round(text):
    return True if text.startswith("frag") else False

def similar_answer(answer, text):
    return cosine_sim(answer, text)>0.7


@skill.intent_handler(INTENT_NAME_MEMORIEREN)
def handler_memo(text: str):
    print(context)
    user_id = '2'
    if start_round(text):
        topic = text.split("thema ")[-1]
        cursor = connection.cursor()
        if topic == text:            
            question_id, quiz, answer, _ = cursor.execute("select questions.id, quiz, answer, max(user_questions.id) as max_id from questions left join user_questions on questions.id = user_questions.questions_id\
                where user_id = ? and step<6 group by questions.id order by max_id limit 1", [user_id]).fetchone()
        else:
            question_id, quiz, answer, _ = cursor.execute("select questions.id, quiz, answer, max(user_questions.id) as max_id from questions left join user_questions on questions.id = user_questions.questions_id\
                where user_id = ? and step<6 and topic = ? group by questions.id order by max_id limit 1", [user_id, topic]).fetchone()
        if quiz is None:
            msg = _("NO_MORE_QUIESTION")
            return tell(msg)
        cursor.execute("insert into user_questions (questions_id) values (?)", [question_id])
        connection.commit()
        return ask(quiz)

    else:
        cursor = connection.cursor()
        last_question_id, answer, step = cursor.execute("select questions_id, answer, step from user_questions uq\
        JOIN questions q on q.id = uq.questions_id where q.user_id = ? order by uq.id desc limit 1", [user_id]).fetchone()
        if similar_answer(answer, text):
            step += 1
        else:
            step = max(1, step-1)
        cursor.execute("update questions set step = ? where id = ?", [step, last_question_id])        
        connection.commit()

        return tell(_('END_QUESTION_REVIEW'))


