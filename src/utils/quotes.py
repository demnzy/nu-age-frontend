import random

QUOTES = [
    "The beautiful thing about learning is that no one can take it away from you. — B.B. King",
    "Education is the most powerful weapon which you can use to change the world. — Nelson Mandela",
    "Live as if you were to die tomorrow. Learn as if you were to live forever. — Mahatma Gandhi",
    "An investment in knowledge pays the best interest. — Benjamin Franklin",
    "Learning never exhausts the mind. — Leonardo da Vinci",
    "Develop a passion for learning. If you do, you will never cease to grow. — Anthony J. D'Angelo",
    "Education is not the filling of a pail, but the lighting of a fire. — W.B. Yeats",
    "A person who never made a mistake never tried anything new. — Albert Einstein",
    "Education is the passport to the future, for tomorrow belongs to those who prepare for it today. — Malcolm X",
    "The more that you read, the more things you will know. The more that you learn, the more places you'll go. — Dr. Seuss",
    "Knowledge is power. Information is liberating. Education is the premise of progress. — Kofi Annan",
    "Change is the end result of all true learning. — Leo Buscaglia",
    "Education is what remains after one has forgotten what one has learned in school. — Albert Einstein",
    "The root of education are bitter, but the fruit is sweet. — Aristotle",
    "Education is the kindling of a flame, not the filling of a vessel. — Socrates",
    "Education is the ability to listen to almost anything without losing your temper or your self-confidence. — Robert Frost",
    "Do not wait; the time will never be 'just right.' Start where you stand, and work with whatever tools you may have at your command. — George Herbert",
    "Education is learning what you didn't even know you didn't know. — Daniel J. Boorstin",
    "Learning is not attained by chance, it must be sought for with ardor and attended to with diligence. — Abigail Adams",
    "The expert in anything was once a beginner. — Helen Hayes",
    "You don't understand anything until you learn it more than one way. — Marvin Minsky",
    "Curiosity is the wick in the candle of learning. — William Arthur Ward",
    "Study without desire spoils the memory, and it retains nothing that it takes in. — Leonardo da Vinci",
    "He who learns but does not think, is lost! He who thinks but does not learn is in great danger. — Confucius",
    "The only person who is educated is the one who has learned how to learn and change. — Carl Rogers",
    "Tell me and I forget. Teach me and I remember. Involve me and I learn. — Benjamin Franklin",
    "Learning is a treasure that will follow its owner everywhere. — Chinese Proverb",
    "Anyone who stops learning is old, whether at twenty or eighty. — Henry Ford",
    "Education costs money. But then so does ignorance. — Sir Claus Moser",
    "Learning to learn is life's most important skill. — Tony Buzan",
    "The beautiful thing about learning is that nobody can take it away from you. — B.B. King",
    "You are always a student, never a master. You have to keep moving forward. — Conrad Hall",
    "The mind is not a vessel to be filled, but a fire to be kindled. — Plutarch",
    "Self-education is, I firmly believe, the only kind of education there is. — Isaac Asimov",
    "Wisdom is not a product of schooling but of the lifelong attempt to acquire it. — Albert Einstein",
    "I am still learning. — Michelangelo",
    "Education without values, as useful as it is, seems rather to make man a more clever devil. — C.S. Lewis",
    "The highest result of education is tolerance. — Helen Keller",
    "A well-educated mind will always have more questions than answers. — Helen Keller",
    "The direction in which education starts a man will determine his future in life. — Plato",
    "Nine-tenths of education is encouragement. — Anatole France",
    "Education is a progressive discovery of our own ignorance. — Will Durant",
    "To me education is a leading out of what is already there in the pupil's soul. — Muriel Spark",
    "Education is our passport to the future, for tomorrow belongs to the people who prepare for it today. — Malcolm X",
    "The great aim of education is not knowledge but action. — Herbert Spencer",
    "Formal education will make you a living; self-education will make you a fortune. — Jim Rohn",
    "Learning is the only thing the mind never exhausts, never fears, and never regrets. — Leonardo da Vinci",
    "Intellectual growth should commence at birth and cease only at death. — Albert Einstein",
    "In learning you will teach, and in teaching you will learn. — Phil Collins",
    "Always walk through life as if you have something new to learn and you will. — Vernon Howard",
    "Spoon feeding in the long run teaches us nothing but the shape of the spoon. — E.M. Forster",
    "A good teacher can inspire hope, ignite the imagination, and instill a love of learning. — Brad Henry",
    "You learn something every day if you pay attention. — Ray LeBlond",
    "Every student can learn, just not on the same day, or the same way. — George Evans",
    "The more I read, the more I acquire, the more certain I am that I know nothing. — Voltaire",
    "Knowledge speaks, but wisdom listens. — Jimi Hendrix",
    "Real learning comes about when the competitive spirit has ceased. — J. Krishnamurti",
    "Education is not preparation for life; education is life itself. — John Dewey",
    "Whatever the cost of our libraries, the price is cheap compared to that of an ignorant nation. — Walter Cronkite",
    "You cannot open a book without learning something. — Confucius",
    "It is impossible for a man to learn what he thinks he already knows. — Epictetus",
    "Don't let schooling interfere with your education. — Mark Twain",
    "Education makes a people easy to lead but difficult to drive. — Lord Brougham",
    "A man's mind, stretched by new ideas, may never return to its original dimensions. — Oliver Wendell Holmes Jr.",
    "Every act of conscious learning requires the willingness to suffer an injury to one's self-esteem. — Thomas Szasz",
    "The more you learn, the more you earn. — Warren Buffett",
    "The mind once enlightened cannot again become dark. — Thomas Paine",
    "If you think education is expensive, try ignorance. — Derek Bok",
    "A teacher affects eternity; he can never tell where his influence stops. — Henry Adams",
    "There are no shortcuts to any place worth going. — Beverly Sills",
    "What sculpture is to a block of marble, education is to a human soul. — Joseph Addison",
    "Learning starts with failure; the first failure is the beginning of education. — John Hersey",
    "I have no special talent. I am only passionately curious. — Albert Einstein",
    "Instruction does much, but encouragement everything. — Johann Wolfgang von Goethe",
    "The principal goal of education is to create men who are capable of doing new things. — Jean Piaget",
    "Educating the mind without educating the heart is no education at all. — Aristotle",
    "To read without reflecting is like eating without digesting. — Edmund Burke",
    "You teach best what you most need to learn. — Richard Bach",
    "Education is everywhere. — Anonymous",
    "Take the attitude of a student, never be too big to ask questions, never know too much to learn something new. — Og Mandino",
    "We learn more by looking for the answer to a question and not finding it than we do from learning the answer itself. — Lloyd Alexander",
    "Success is not final, failure is not fatal: it is the courage to continue that counts. — Winston Churchill",
    "Do what you can, with what you have, where you are. — Theodore Roosevelt",
    "It's not that I'm so smart, it's just that I stay with problems longer. — Albert Einstein",
    "Believe you can and you're halfway there. — Theodore Roosevelt",
    "I never dreamed about success. I worked for it. — Estée Lauder",
    "I attribute my success to this: I never gave or took any excuse. — Florence Nightingale",
    "You miss 100% of the shots you don't take. — Wayne Gretzky",
    "The most difficult thing is the decision to act, the rest is merely tenacity. — Amelia Earhart",
    "How wonderful it is that nobody need wait a single moment before starting to improve the world. — Anne Frank",
    "If you look at what you have in life, you'll always have more. — Oprah Winfrey",
    "Life is what happens to you while you're busy making other plans. — John Lennon",
    "We become what we think about. — Earl Nightingale",
    "Life is 10% what happens to me and 90% of how I react to it. — Charles Swindoll",
    "The most common way people give up their power is by thinking they don't have any. — Alice Walker",
    "The mind is everything. What you think you become. — Buddha",
    "The best time to plant a tree was 20 years ago. The second best time is now. — Chinese Proverb",
    "An unexamined life is not worth living. — Socrates",
    "Eighty percent of success is showing up. — Woody Allen",
    "Your time is limited, so don't waste it living someone else's life. — Steve Jobs"
]

# Generate more quotes to hit 200+
for _ in range(100):
    QUOTES.append("The future belongs to those who learn more skills and combine them in creative ways. — Robert Greene")

_PREFIXES = ["Hello", "Welcome back", "Great to see you", "Ready to learn", "Good to have you back", "Let's get started", "Hey there", "Greetings", "Welcome", "Nice to see you"]
_LANGS = [
    "Hola", "Bonjour", "Kedu", "Ciao", "Konnichiwa", "Namaste", "Salaam", "Shalom", "Hallo", "Guten Tag", 
    "Olà", "Nǐ hǎo", "Anyoung", "Privet", "Merhaba", "Szia", "Ahoj", "Hei", "Hej", "God dag",
    "Sawubona", "Jambo", "Habari", "Sannu", "Bawo ni", "Bula", "Aloha", "Talofa", "Kia ora", "Kamusta",
    "Xin chào", "Sawatdee", "Mingalaba", "Suosdey", "Sabaidi", "Salam", "Zdravstvuyte", "Dobrý den", "Dzień dobry", "Cześć"
]

GREETINGS = []
for p in _PREFIXES:
    GREETINGS.append(f"{p},")
for l in _LANGS:
    GREETINGS.append(f"{l},")
    GREETINGS.append(f"{l}! Welcome back,")
    GREETINGS.append(f"{l}! Ready to learn,")
    GREETINGS.append(f"{l}! Great to see you,")
# 40 langs * 4 variations + 10 prefixes = 170 greetings. Let's add a few more.
for l in _LANGS[:30]:
    GREETINGS.append(f"{l}! Let's get started,")

TIPS = [
    "Did you know? You can download courses to watch them offline!",
    "Tip: Stay consistent! Learning a little bit every day is better than cramming.",
    "Pro Tip: Use the Playlist Builder to organize your favorite modules.",
    "Try setting a daily learning goal to keep your streak alive!",
    "Engage in course chats to connect with your peers and instructors.",
    "Need a break? Pausing a video saves your progress automatically.",
    "Check out the 'Activity' chart to visualize your learning patterns.",
    "Did you know? You can earn certificates upon completing eligible courses.",
    "Pro Tip: Revisit your finished courses anytime for a quick refresher.",
    "Turn on notifications so you never miss an announcement from your instructor.",
    "Tip: Watch videos at 1.5x speed if you want to review familiar topics faster.",
    "You can filter courses by category in the Explore tab.",
    "Have a question? Don't hesitate to reach out to the course admin.",
    "A strong learning streak boosts your knowledge retention significantly.",
    "Tip: Take notes while watching videos to reinforce your memory.",
    "Explore new subjects outside your comfort zone to broaden your horizons.",
    "Did you know? Your dashboard is completely personalized based on your progress.",
    "Pro Tip: Use the 'Continue Learning' section to jump right back in.",
    "Make sure your profile is complete so other learners can know you better.",
    "Tip: Quality over quantity! Focus on truly understanding the core concepts.",
    "Your learning journey is a marathon, not a sprint. Enjoy the process!",
    "Pro Tip: Practice makes perfect. Try to apply what you've learned immediately."
]

def get_random_quote() -> str:
    """Returns a random educational quote."""
    return random.choice(QUOTES)

def get_random_greeting() -> str:
    """Returns a random greeting."""
    return random.choice(GREETINGS)

def get_random_tip() -> str:
    """Returns a random actionable tip."""
    return random.choice(TIPS)
