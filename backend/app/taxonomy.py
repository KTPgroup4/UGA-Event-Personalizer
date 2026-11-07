"""The fixed lists of options that every part of the backend uses.

Save this file as: app/taxonomy.py

What it is: the one agreed vocabulary of allowed values. The frontend shows the
user-facing parts of it (interests, majors) as choices; the AI tagger may only
pick from it; the scorer compares values from it. Some parts are NOT shown to
users (EVENT_TYPES, and the college tags the AI puts on events).
If these lists differ between files, matching breaks, so there is only ONE copy.

Rules for this file:
    - It must NEVER import app/schemas/event.py (they would import each other and crash).
    - To add an interest, add one line to a category below. Don't change an existing
      ID: events and user profiles already saved with it would stop matching.
    - An interest's full tag ID is "<category id>:<child id>", for example
      "engineering-making:civil". Major and college IDs are plain, like "computer-science".
    - College IDs, major IDs and interest IDs never overlap (a test checks this),
      so any ID can be told apart from the others.
"""

import copy

# ------------------------------------------------------------------ INTERESTS
# Cultural interests describe what a user wants to explore, not their identity.
# Users choose these voluntarily. Culture, language and faith are independent;
# selecting one never automatically adds another. These are proposed interest
# options, not a claim that every culture has a registered UGA club.
# Calendar examples informing the taxonomy (reviewed 2026-10-28):
# https://calendar.uga.edu/group/center-for-global-and-cultural-student-engagement
# https://calendar.uga.edu/event/hispanic-heritage-month
# https://calendar.uga.edu/event/lecture-dwayne-tomah-the-doctrine-of-discovery
# The program does not fetch or synchronize live UGA calendar events.
#
# Each child is written as (id, display name). Display names are written out in
# full on purpose, so "AI" and "UGA Football" show up correctly.

_INTEREST_DATA = [
    {
        "id": "technology-coding",
        "name": "Technology & Coding",
        "children": [
            ("programming", "Programming"),
            ("computer-science", "Computer Science"),
            ("software", "Software"),
            ("web-development", "Web Development"),
            ("ai", "AI"),
            ("cybersecurity", "Cybersecurity"),
            ("hackathons", "Hackathons"),
        ],
    },
    {
        "id": "engineering-making",
        "name": "Engineering & Making",
        "children": [
            ("mechanical", "Mechanical"),
            ("electrical", "Electrical"),
            ("computer", "Computer"),
            ("aerospace", "Aerospace"),
            ("civil", "Civil"),
            ("biomedical", "Biomedical"),
            ("environmental", "Environmental"),
            ("robotics", "Robotics"),
            ("cad", "CAD"),
            ("fabrication", "Fabrication"),
        ],
    },
    {
        "id": "science-research",
        "name": "Science & Research",
        "children": [
            ("biology", "Biology"),
            ("chemistry", "Chemistry"),
            ("physics", "Physics"),
            ("research", "Research"),
            ("lab", "Lab"),
            ("science", "Science"),
        ],
    },
    {
        "id": "business-entrepreneurship",
        "name": "Business & Entrepreneurship",
        "children": [
            ("startups", "Startups"),
            ("entrepreneurship", "Entrepreneurship"),
            ("marketing", "Marketing"),
            ("business", "Business"),
            ("pitch-competitions", "Pitch Competitions"),
        ],
    },
    {
        "id": "finance-investing",
        "name": "Finance & Investing",
        "children": [
            ("investing", "Investing"),
            ("finance", "Finance"),
            ("budgeting", "Budgeting"),
            ("markets", "Markets"),
        ],
    },
    {
        "id": "healthcare-medicine",
        "name": "Healthcare & Medicine",
        "children": [
            ("medicine", "Medicine"),
            ("healthcare", "Healthcare"),
            ("pre-med", "Pre-Med"),
            ("public-health", "Public Health"),
            ("clinical-volunteering", "Clinical Volunteering"),
        ],
    },
    {
        "id": "law-government-policy",
        "name": "Law, Government & Public Policy",
        "children": [
            ("law", "Law"),
            ("government", "Government"),
            ("politics", "Politics"),
            ("public-policy", "Public Policy"),
            ("mock-trial", "Mock Trial"),
        ],
    },
    {
        "id": "education-mentoring",
        "name": "Education & Mentoring",
        "children": [
            ("teaching", "Teaching"),
            ("tutoring", "Tutoring"),
            ("mentoring", "Mentoring"),
            ("education", "Education"),
        ],
    },
    {
        "id": "environment-sustainability",
        "name": "Environment & Sustainability",
        "children": [
            ("environment", "Environment"),
            ("sustainability", "Sustainability"),
            ("conservation", "Conservation"),
            ("climate", "Climate"),
            ("cleanup", "Cleanup"),
        ],
    },
    {
        "id": "psychology-human-behavior",
        "name": "Psychology & Human Behavior",
        "children": [
            ("psychology", "Psychology"),
            ("behavior", "Behavior"),
            ("counseling", "Counseling"),
            ("human-behavior", "Human Behavior"),
        ],
    },
    {
        "id": "writing-literature",
        "name": "Writing & Literature",
        "children": [
            ("writing", "Writing"),
            ("books", "Books"),
            ("poetry", "Poetry"),
            ("literature", "Literature"),
            ("creative-writing", "Creative Writing"),
            ("book-clubs", "Book Clubs"),
            ("journaling", "Journaling"),
        ],
    },
    {
        "id": "languages-global-cultures",
        "name": "Languages & Global Cultures",
        "children": [
            ("languages", "Languages"),
            ("spanish", "Spanish"),
            ("french", "French"),
            ("culture", "Culture"),
            ("international", "International"),
            ("language-exchange", "Language Exchange"),
            ("korean", "Korean"),
            ("japanese", "Japanese"),
            ("mandarin-chinese", "Mandarin Chinese"),
            ("arabic", "Arabic"),
            ("portuguese", "Portuguese"),
            ("german", "German"),
            ("hindi", "Hindi"),
            ("turkish", "Turkish"),
            ("american-sign-language", "American Sign Language"),
            ("yoruba", "Yoruba"),
        ],
    },
    {
        "id": "visual-art-design",
        "name": "Visual Art & Design",
        "children": [
            ("art", "Art"),
            ("drawing", "Drawing"),
            ("graphic-design", "Graphic Design"),
            ("painting", "Painting"),
            ("illustration", "Illustration"),
            ("pottery", "Pottery"),
            ("sculpture", "Sculpture"),
            ("crafts", "Crafts"),
            ("watercolor", "Watercolor"),
            ("digital-art", "Digital Art"),
        ],
    },
    {
        "id": "music",
        "name": "Music",
        "children": [
            ("music", "Music"),
            ("concerts", "Concerts"),
            ("singing", "Singing"),
            ("instrument", "Instrument"),
            ("jam-sessions", "Jam Sessions"),
            ("guitar", "Guitar"),
            ("piano", "Piano"),
            ("songwriting", "Songwriting"),
            ("live-music", "Live Music"),
        ],
    },
    {
        "id": "dance-performing-arts",
        "name": "Dance & Performing Arts",
        "children": [
            ("dance", "Dance"),
            ("theater", "Theater"),
            ("acting", "Acting"),
            ("improv", "Improv"),
            ("performing-arts", "Performing Arts"),
        ],
    },
    {
        "id": "film-photography",
        "name": "Film & Photography",
        "children": [
            ("film", "Film"),
            ("photography", "Photography"),
            ("video", "Video"),
            ("editing", "Editing"),
            ("screenings", "Screenings"),
            ("nature-photography", "Nature Photography"),
            ("movie-nights", "Movie Nights"),
        ],
    },
    {
        "id": "gaming-esports",
        "name": "Gaming & Esports",
        "children": [
            ("gaming", "Gaming"),
            ("video-games", "Video Games"),
            ("esports", "Esports"),
            ("tournaments", "Tournaments"),
        ],
    },
    {
        "id": "board-games-tabletop-rpgs",
        "name": "Board Games & Tabletop RPGs",
        "children": [
            ("board-games", "Board Games"),
            ("dungeons-and-dragons", "Dungeons & Dragons"),
            ("tabletop", "Tabletop"),
            ("rpg", "RPG"),
            ("chess", "Chess"),
            ("card-games", "Card Games"),
        ],
    },
    {
        "id": "sports-recreation",
        "name": "Sports & Recreation",
        "children": [
            ("sports", "Sports"),
            ("intramurals", "Intramurals"),
            ("pickup-games", "Pickup Games"),
            ("recreation", "Recreation"),
            ("basketball", "Basketball"),
            ("soccer", "Soccer"),
            ("volleyball", "Volleyball"),
            ("tennis", "Tennis"),
            ("pickleball", "Pickleball"),
            ("badminton", "Badminton"),
            ("ultimate-frisbee", "Ultimate Frisbee"),
            ("running", "Running"),
            ("swimming", "Swimming"),
        ],
    },
    {
        "id": "fitness-wellness",
        "name": "Fitness & Wellness",
        "children": [
            ("fitness", "Fitness"),
            ("workouts", "Workouts"),
            ("yoga", "Yoga"),
            ("wellness", "Wellness"),
            ("pilates", "Pilates"),
            ("weightlifting", "Weightlifting"),
            ("meditation", "Meditation"),
            ("cycling", "Cycling"),
        ],
    },
    {
        "id": "outdoors-adventure",
        "name": "Outdoors & Adventure",
        "children": [
            ("hiking", "Hiking"),
            ("camping", "Camping"),
            ("climbing", "Climbing"),
            ("kayaking", "Kayaking"),
            ("outdoors", "Outdoors"),
            ("backpacking", "Backpacking"),
            ("outdoor-skills", "Outdoor Skills"),
            ("trail-walking", "Trail Walking"),
        ],
    },
    {
        "id": "food-cooking",
        "name": "Food & Cooking",
        "children": [
            ("cooking", "Cooking"),
            ("food", "Food"),
            ("baking", "Baking"),
            ("culinary", "Culinary"),
            ("vegetarian-cooking", "Vegetarian Cooking"),
            ("international-food", "International Food"),
            ("cake-decorating", "Cake Decorating"),
        ],
    },
    {
        "id": "fashion-personal-style",
        "name": "Fashion & Personal Style",
        "children": [
            ("fashion", "Fashion"),
            ("style", "Style"),
            ("clothing", "Clothing"),
            ("design", "Design"),
        ],
    },
    {
        "id": "community-service",
        "name": "Community Service",
        "children": [
            ("volunteering", "Volunteering"),
            ("service", "Service"),
            ("fundraising", "Fundraising"),
            ("community", "Community"),
        ],
    },
    {
        "id": "social-justice-advocacy",
        "name": "Social Justice & Advocacy",
        "children": [
            ("advocacy", "Advocacy"),
            ("social-justice", "Social Justice"),
            ("awareness", "Awareness"),
            ("human-rights", "Human Rights"),
        ],
    },
    {
        "id": "nature-wildlife",
        "name": "Nature & Wildlife",
        "children": [
            ("birdwatching", "Birdwatching"),
            ("plant-identification", "Plant Identification"),
            ("wildlife", "Wildlife"),
            ("pollinators", "Pollinators"),
            ("ecology", "Ecology"),
            ("nature-walks", "Nature Walks"),
        ],
    },
    {
        "id": "gardening-plants",
        "name": "Gardening & Plants",
        "children": [
            ("gardening", "Gardening"),
            ("houseplants", "Houseplants"),
            ("native-plants", "Native Plants"),
            ("composting", "Composting"),
            ("seed-starting", "Seed Starting"),
        ],
    },
    {
        "id": "animals-pets",
        "name": "Animals & Pets",
        "children": [
            ("animal-welfare", "Animal Welfare"),
            ("pet-care", "Pet Care"),
            ("therapy-animals", "Therapy Animals"),
        ],
    },
    {
        "id": "social-campus-life",
        "name": "Social & Campus Life",
        "children": [
            ("meeting-people", "Meeting People"),
            ("trivia", "Trivia"),
            ("karaoke", "Karaoke"),
            ("campus-traditions", "Campus Traditions"),
            ("social-games", "Social Games"),
        ],
    },
    {
        "id": "diy-crafts",
        "name": "DIY & Crafts",
        "children": [
            ("knitting", "Knitting"),
            ("crochet", "Crochet"),
            ("sewing", "Sewing"),
            ("woodworking", "Woodworking"),
            ("jewelry-making", "Jewelry Making"),
            ("origami", "Origami"),
        ],
    },
    {
        "id": "astronomy-space",
        "name": "Astronomy & Space",
        "children": [
            ("stargazing", "Stargazing"),
            ("telescopes", "Telescopes"),
            ("space-exploration", "Space Exploration"),
        ],
    },
    {
        "id": "travel-exploration",
        "name": "Travel & Exploration",
        "children": [
            ("travel-planning", "Travel Planning"),
            ("study-abroad", "Study Abroad"),
            ("cultural-exchange", "Cultural Exchange"),
        ],
    },
    {
        "id": "collecting-puzzles",
        "name": "Collecting & Puzzles",
        "children": [
            ("jigsaw-puzzles", "Jigsaw Puzzles"),
            ("logic-puzzles", "Logic Puzzles"),
            ("trading-cards", "Trading Cards"),
            ("collecting", "Collecting"),
        ],
    },
    {
        "id": "east-asian-cultures",
        "name": "East Asian Cultures",
        "children": [
            ("chinese-culture", "Chinese Culture"),
            ("korean-culture", "Korean Culture"),
            ("japanese-culture", "Japanese Culture"),
            ("taiwanese-culture", "Taiwanese Culture"),
            ("mongolian-culture", "Mongolian Culture"),
        ],
    },
    {
        "id": "southeast-asian-cultures",
        "name": "Southeast Asian Cultures",
        "children": [
            ("filipino-culture", "Filipino Culture"),
            ("vietnamese-culture", "Vietnamese Culture"),
            ("thai-culture", "Thai Culture"),
            ("indonesian-culture", "Indonesian Culture"),
            ("malaysian-culture", "Malaysian Culture"),
            ("cambodian-culture", "Cambodian Culture"),
            ("lao-culture", "Lao Culture"),
            ("hmong-culture", "Hmong Culture"),
        ],
    },
    {
        "id": "south-asian-cultures",
        "name": "South Asian Cultures",
        "children": [
            ("indian-culture", "Indian Culture"),
            ("pakistani-culture", "Pakistani Culture"),
            ("bangladeshi-culture", "Bangladeshi Culture"),
            ("nepali-culture", "Nepali Culture"),
            ("sri-lankan-culture", "Sri Lankan Culture"),
            ("bhutanese-culture", "Bhutanese Culture"),
        ],
    },
    {
        "id": "middle-east-north-africa",
        "name": "Middle Eastern & North African Cultures",
        "children": [
            ("arab-culture", "Arab Culture"),
            ("turkish-culture", "Turkish Culture"),
            ("persian-culture", "Persian Culture"),
            ("kurdish-culture", "Kurdish Culture"),
            ("israeli-culture", "Israeli Culture"),
            ("palestinian-culture", "Palestinian Culture"),
            ("north-african-cultures", "North African Cultures"),
        ],
    },
    {
        "id": "african-cultures",
        "name": "African Cultures",
        "children": [
            ("west-african-cultures", "West African Cultures"),
            ("east-african-cultures", "East African Cultures"),
            ("central-african-cultures", "Central African Cultures"),
            ("southern-african-cultures", "Southern African Cultures"),
            ("nigerian-culture", "Nigerian Culture"),
            ("ghanaian-culture", "Ghanaian Culture"),
            ("ethiopian-culture", "Ethiopian Culture"),
            ("yoruba-culture", "Yoruba Culture"),
        ],
    },
    {
        "id": "black-diaspora",
        "name": "Black & African Diaspora Cultures",
        "children": [
            ("african-american-culture", "African American Culture"),
            ("black-history", "Black History"),
            ("african-diaspora-arts", "African Diaspora Arts"),
            ("black-literature", "Black Literature"),
            ("black-student-community-events", "Black Student Community Events"),
        ],
    },
    {
        "id": "latin-caribbean-cultures",
        "name": "Latino, Hispanic & Caribbean Cultures",
        "children": [
            ("mexican-culture", "Mexican Culture"),
            ("puerto-rican-culture", "Puerto Rican Culture"),
            ("cuban-culture", "Cuban Culture"),
            ("dominican-culture", "Dominican Culture"),
            ("central-american-cultures", "Central American Cultures"),
            ("south-american-cultures", "South American Cultures"),
            ("brazilian-culture", "Brazilian Culture"),
            ("caribbean-cultures", "Caribbean Cultures"),
            ("hispanic-heritage", "Hispanic Heritage"),
        ],
    },
    {
        "id": "indigenous-cultures",
        "name": "Indigenous Cultures & Heritage",
        "children": [
            ("native-american-cultures", "Native American Cultures"),
            ("cherokee-history-and-culture", "Cherokee History and Culture"),
            ("indigenous-languages", "Indigenous Languages"),
            ("tribal-sovereignty", "Tribal Sovereignty"),
            ("indigenous-arts", "Indigenous Arts"),
        ],
    },
    {
        "id": "pacific-cultures",
        "name": "Pacific Islander & Oceanian Cultures",
        "children": [
            ("pacific-islander-cultures", "Pacific Islander Cultures"),
            ("native-hawaiian-culture", "Native Hawaiian Culture"),
            ("polynesian-cultures", "Polynesian Cultures"),
            ("micronesian-cultures", "Micronesian Cultures"),
            ("melanesian-cultures", "Melanesian Cultures"),
            ("maori-culture", "Maori Culture"),
        ],
    },
    {
        "id": "european-cultures",
        "name": "European Cultures",
        "children": [
            ("french-culture", "French Culture"),
            ("german-culture", "German Culture"),
            ("italian-culture", "Italian Culture"),
            ("spanish-culture", "Spanish Culture"),
            ("greek-culture", "Greek Culture"),
            ("irish-culture", "Irish Culture"),
            ("british-culture", "British Culture"),
            ("eastern-european-cultures", "Eastern European Cultures"),
        ],
    },
    {
        "id": "cultural-exchange",
        "name": "Cultural Exchange & Celebrations",
        "children": [
            ("international-coffee-hours", "International Coffee Hours"),
            ("cultural-festivals", "Cultural Festivals"),
            ("heritage-celebrations", "Heritage Celebrations"),
            ("cultural-food", "Cultural Food"),
            ("traditional-dance", "Traditional Dance"),
            ("traditional-music", "Traditional Music"),
            ("cultural-fashion", "Cultural Fashion"),
            ("storytelling", "Storytelling"),
            ("intercultural-dialogue", "Intercultural Dialogue"),
            ("international-student-connections", "International Student Connections"),
        ],
    },
    {
        "id": "faith-spirituality",
        "name": "Faith, Spirituality & Interfaith Activities",
        "children": [
            ("christian-traditions", "Christian Traditions"),
            ("muslim-traditions", "Muslim Traditions"),
            ("jewish-traditions", "Jewish Traditions"),
            ("hindu-traditions", "Hindu Traditions"),
            ("buddhist-traditions", "Buddhist Traditions"),
            ("sikh-traditions", "Sikh Traditions"),
            ("interfaith-dialogue", "Interfaith Dialogue"),
            ("secular-and-humanist-discussions", "Secular and Humanist Discussions"),
            ("religious-holiday-learning", "Religious Holiday Learning"),
        ],
    },
    {
        "id": "history-humanities",
        "name": "History & Humanities",
        "children": [
            ("history", "History"),
            ("philosophy", "Philosophy"),
            ("archaeology", "Archaeology"),
            ("museum-exhibitions", "Museum Exhibitions"),
            ("public-lectures", "Public Lectures"),
            ("folklore", "Folklore"),
        ],
    },
    {
        "id": "career-leadership",
        "name": "Career Development & Leadership",
        "children": [
            ("career-fairs", "Career Fairs"),
            ("internships", "Internships"),
            ("resume-workshops", "Resume Workshops"),
            ("networking", "Networking"),
            ("student-leadership", "Student Leadership"),
            ("public-speaking", "Public Speaking"),
            ("graduate-school-preparation", "Graduate School Preparation"),
        ],
    },
    {
        "id": "spectator-sports",
        "name": "Watching Sports & School Spirit",
        "children": [
            ("uga-football", "UGA Football"),
            ("uga-basketball", "UGA Basketball"),
            ("uga-volleyball", "UGA Volleyball"),
            ("uga-gymnastics", "UGA Gymnastics"),
            ("uga-baseball", "UGA Baseball"),
            ("uga-soccer", "UGA Soccer"),
            ("watch-parties", "Watch Parties"),
            ("school-spirit", "School Spirit"),
        ],
    },
]

# The same shape as the original prototype:
#   INTERESTS = [{"id", "name", "children": [{"id": "category:child", "name"}]}]
INTERESTS = [
    {
        "id": category["id"],
        "name": category["name"],
        "children": [
            {"id": category["id"] + ":" + child_id, "name": child_name}
            for child_id, child_name in category["children"]
        ],
    }
    for category in _INTEREST_DATA
]

CATEGORY_IDS = [category["id"] for category in INTERESTS]
PARENTS = {child["id"]: c["id"] for c in INTERESTS for child in c["children"]}  # child -> category
LABELS = {c["id"]: c["name"] for c in INTERESTS}  # every valid interest ID -> readable name
LABELS.update({child["id"]: c["name"] + " / " + child["name"]
               for c in INTERESTS for child in c["children"]})

# ----------------------------------------------------- COLLEGES AND MAJORS
# Source: "Majors Checklist by College & School" from UGA, last updated August 2026.
# To update it when UGA publishes a new checklist, edit the lists below by hand.
#   - Degree types (AB, BS, BBA ...) are left out: students pick a major, not a degree.
#   - Majors are listed alphabetically inside each college.
#   - Minors and certificates are not in the checklist, so they are not here.
#   - Two options are NOT in the checklist and are added below: Undecided and Other.
# Each major is written as (id, display name).

_COLLEGE_DATA = [
    {
        "id": "caes",
        "name": "College of Agricultural and Environmental Sciences",
        "majors": [
            ("agribusiness", "Agribusiness"),
            ("agricultural-and-applied-economics", "Agricultural and Applied Economics"),
            ("agricultural-and-environmental-science-communication", "Agricultural and Environmental Science Communication"),
            ("agricultural-education", "Agricultural Education"),
            ("agriscience-and-environmental-systems", "Agriscience and Environmental Systems"),
            ("animal-and-dairy-science", "Animal and Dairy Science"),
            ("animal-biosciences", "Animal Biosciences"),
            ("animal-health", "Animal Health"),
            ("applied-biotechnology", "Applied Biotechnology"),
            ("avian-biology", "Avian Biology"),
            ("biological-science", "Biological Science"),
            ("entomology", "Entomology"),
            ("environmental-economics-and-management", "Environmental Economics and Management"),
            ("environmental-resource-science", "Environmental Resource Science"),
            ("food-science", "Food Science"),
            ("horticulture", "Horticulture"),
            ("hospitality-and-food-industry-management", "Hospitality and Food Industry Management"),
            ("poultry-science", "Poultry Science"),
            ("regenerative-bioscience", "Regenerative Bioscience"),
            ("turfgrass-management", "Turfgrass Management"),
            ("water-and-soil-resources", "Water and Soil Resources"),
        ],
    },
    {
        "id": "engineering",
        "name": "College of Engineering",
        "majors": [
            ("agricultural-engineering", "Agricultural Engineering"),
            ("biochemical-engineering", "Biochemical Engineering"),
            ("biological-engineering", "Biological Engineering"),
            ("civil-engineering", "Civil Engineering"),
            ("computer-systems-engineering", "Computer Systems Engineering"),
            ("electrical-and-electronics-engineering", "Electrical and Electronics Engineering"),
            ("environmental-engineering", "Environmental Engineering"),
            ("mechanical-engineering", "Mechanical Engineering"),
        ],
    },
    {
        "id": "environment-and-design",
        "name": "College of Environment and Design",
        "majors": [
            ("landscape-architecture", "Landscape Architecture"),
        ],
    },
    {
        "id": "family-and-consumer-sciences",
        "name": "College of Family and Consumer Sciences",
        "majors": [
            ("consumer-economics", "Consumer Economics"),
            ("culinary-science-and-nutrition", "Culinary Science and Nutrition"),
            ("dietetics", "Dietetics"),
            ("family-and-consumer-sciences-education", "Family & Consumer Sciences Education"),
            ("fashion-merchandising", "Fashion Merchandising"),
            ("financial-planning", "Financial Planning"),
            ("furnishings-and-interiors", "Furnishings and Interiors"),
            ("housing-management-and-policy", "Housing Management and Policy"),
            ("human-development-and-family-science", "Human Development and Family Science"),
            ("nutritional-sciences", "Nutritional Sciences"),
            ("social-entrepreneurship-for-consumer-well-being", "Social Entrepreneurship for Consumer Well-Being"),
        ],
    },
    {
        "id": "pharmacy",
        "name": "College of Pharmacy",
        "majors": [
            ("pharmaceutical-and-biomedical-sciences", "Pharmaceutical and Biomedical Sciences"),
        ],
    },
    {
        "id": "public-health",
        "name": "College of Public Health",
        "majors": [
            ("environmental-health", "Environmental Health"),
            ("health-promotion", "Health Promotion"),
        ],
    },
    {
        "id": "veterinary-medicine",
        "name": "College of Veterinary Medicine",
        "majors": [
            ("biomedical-physiology", "Biomedical Physiology"),
        ],
    },
    {
        "id": "franklin",
        "name": "Franklin College of Arts and Sciences",
        "majors": [
            ("african-american-studies", "African American Studies"),
            ("anthropology", "Anthropology"),
            ("arabic", "Arabic"),
            ("art-animation", "Art - Animation"),
            ("art-ceramics", "Art - Ceramics"),
            ("art-drawing-and-painting", "Art - Drawing and Painting"),
            ("art-fabric-design", "Art - Fabric Design"),
            ("art-graphic-design", "Art - Graphic Design"),
            ("art-interior-design", "Art - Interior Design"),
            ("art-jewelry-and-metalwork", "Art - Jewelry and Metalwork"),
            ("art-photography-and-expanded-media", "Art - Photography and Expanded Media"),
            ("art-printmaking", "Art - Printmaking"),
            ("art-scientific-illustration", "Art - Scientific Illustration"),
            ("art-sculpture-and-technology", "Art - Sculpture and Technology"),
            ("art-education", "Art Education"),
            ("art-history", "Art History"),
            ("art-interdisciplinary-art", "Art: Interdisciplinary Art"),
            ("asian-languages-and-literature", "Asian Languages and Literature"),
            ("astrophysics", "Astrophysics"),
            ("atmospheric-sciences", "Atmospheric Sciences"),
            ("biochemistry-and-molecular-biology", "Biochemistry and Molecular Biology"),
            ("biology", "Biology"),
            ("cellular-biology", "Cellular Biology"),
            ("chemistry", "Chemistry"),
            ("classics", "Classics"),
            ("cognitive-science", "Cognitive Science"),
            ("communication-studies", "Communication Studies"),
            ("comparative-literature-and-intercultural-studies", "Comparative Literature and Intercultural Studies"),
            ("dance", "Dance"),
            ("english", "English"),
            ("film", "Film"),
            ("french", "French"),
            ("genetics", "Genetics"),
            ("geography", "Geography"),
            ("geology", "Geology"),
            ("german", "German"),
            ("history", "History"),
            ("latin-american-and-caribbean-studies", "Latin American and Caribbean Studies"),
            ("linguistics", "Linguistics"),
            ("mathematics", "Mathematics"),
            ("microbiology", "Microbiology"),
            ("music-major", "Music"),
            ("music-composition", "Music Composition"),
            ("music-education", "Music Education"),
            ("music-performance", "Music Performance"),
            ("music-theory", "Music Theory"),
            ("music-therapy", "Music Therapy"),
            ("neuroscience", "Neuroscience"),
            ("ocean-science", "Ocean Science"),
            ("philosophy", "Philosophy"),
            ("physics", "Physics"),
            ("plant-biology", "Plant Biology"),
            ("psychology", "Psychology"),
            ("religion", "Religion"),
            ("romance-languages", "Romance Languages"),
            ("russian", "Russian"),
            ("sociology", "Sociology"),
            ("spanish", "Spanish"),
            ("statistics", "Statistics"),
            ("theatre", "Theatre"),
            ("womens-and-gender-studies", "Women's and Gender Studies"),
        ],
    },
    {
        "id": "grady",
        "name": "Grady College of Journalism and Mass Communication",
        "majors": [
            ("advertising", "Advertising"),
            ("entertainment-and-media-studies", "Entertainment and Media Studies"),
            ("journalism", "Journalism"),
            ("public-relations", "Public Relations"),
        ],
    },
    {
        "id": "education",
        "name": "Mary Frances Early College of Education",
        "majors": [
            ("communication-sciences-and-disorders", "Communication Sciences and Disorders"),
            ("elementary-education", "Elementary Education"),
            ("english-education", "English Education"),
            ("exercise-and-sport-science", "Exercise and Sport Science"),
            ("health-and-physical-education", "Health and Physical Education"),
            ("mathematics-education", "Mathematics Education"),
            ("middle-grades-education", "Middle Grades Education"),
            ("science-education", "Science Education"),
            ("social-studies-education", "Social Studies Education"),
            ("special-education", "Special Education"),
            ("sport-management", "Sport Management"),
            ("tesol-and-world-language-education", "TESOL and World Language Education"),
            ("workforce-education", "Workforce Education"),
        ],
    },
    {
        "id": "odum",
        "name": "Odum School of Ecology",
        "majors": [
            ("ecology", "Ecology"),
        ],
    },
    {
        "id": "computing",
        "name": "School of Computing",
        "majors": [
            ("computer-science", "Computer Science"),
            ("data-science", "Data Science"),
        ],
    },
    {
        "id": "public-and-international-affairs",
        "name": "School of Public and International Affairs",
        "majors": [
            ("criminal-justice", "Criminal Justice"),
            ("international-affairs", "International Affairs"),
            ("political-science", "Political Science"),
        ],
    },
    {
        "id": "school-of-social-work",
        "name": "School of Social Work",
        "majors": [
            ("social-work", "Social Work"),
        ],
    },
    {
        "id": "terry",
        "name": "Terry College of Business",
        "majors": [
            ("accounting", "Accounting"),
            ("economics", "Economics"),
            ("finance", "Finance"),
            ("international-business", "International Business (Co-Major)"),
            ("management", "Management"),
            ("management-information-systems", "Management Information Systems"),
            ("marketing", "Marketing"),
            ("real-estate", "Real Estate"),
            ("risk-management-and-insurance", "Risk Management and Insurance"),
        ],
    },
    {
        "id": "warnell",
        "name": "Warnell School of Forestry and Natural Resources",
        "majors": [
            ("fisheries-and-wildlife", "Fisheries and Wildlife"),
            ("forestry", "Forestry"),
            ("natural-resource-management-and-sustainability", "Natural Resource Management and Sustainability"),
            ("parks-recreation-and-tourism-management", "Parks, Recreation, & Tourism Management"),
        ],
    },
]

COLLEGES = [
    {
        "id": college["id"],
        "name": college["name"],
        "majors": [{"id": major_id, "name": major_name} for major_id, major_name in college["majors"]],
    }
    for college in _COLLEGE_DATA
]
COLLEGE_IDS = [college["id"] for college in COLLEGES]

SPECIAL_MAJORS = [
    {"id": "undecided", "name": "Undecided"},
    {"id": "other", "name": "Other / not listed"},
]

MAX_MAJORS = 2
CO_MAJOR_IDS = ["international-business"]  # can only be chosen together with another major
EXCLUSIVE_MAJOR_IDS = ["undecided"]  # can't be combined with any other major

# Criminal Justice is listed under the School of Public and International Affairs,
# but the checklist notes it is also offered in Franklin College.
_ALSO_IN = {"criminal-justice": ["franklin"]}

MAJORS = [major for college in COLLEGES for major in college["majors"]] + SPECIAL_MAJORS
MAJOR_IDS = [major["id"] for major in MAJORS]
MAJOR_TO_COLLEGES = {
    major["id"]: [college["id"]] + _ALSO_IN.get(major["id"], [])
    for college in COLLEGES
    for major in college["majors"]
}
MAJOR_TO_COLLEGES.update({major["id"]: [] for major in SPECIAL_MAJORS})

# ----------------------------------------------------------------- EVENT TYPES
# STARTER LIST: the one "kind of event" the AI picks for each event. Not shown to users.
EVENT_TYPES = [
    "workshop", "talk", "social", "performance", "meeting",
    "competition", "volunteering", "career", "sports", "other",
]

# -------------------------------------------------------------------- helpers


def normalize_tag(text: str) -> str:
    """Lowercase and trim, so "Music " and "music" are treated the same."""
    return text.strip().lower()


def keep_valid(values: list[str], allowed: list[str]) -> list[str]:
    """Keep only the values that are in the allowed list (no repeats, original order).

    Use it on the AI's answer: anything the AI made up is quietly dropped.
    """
    allowed_set = set(allowed)
    kept: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        tag = normalize_tag(value)
        if tag in allowed_set and tag not in kept:
            kept.append(tag)
    return kept


def children_of(category_id: str) -> list[dict]:
    """The sub-interests inside one category (empty list if the category doesn't exist)."""
    for category in INTERESTS:
        if category["id"] == category_id:
            return category["children"]
    return []


def canonical_selection(selected) -> set[str]:
    """Check a user's chosen interests and tidy them.

    A specialty refines its category, so when both are chosen the category is
    dropped and only the specialty counts. Unknown IDs raise a ValueError.
    """
    selected = set(selected)
    unknown = selected - LABELS.keys()
    if unknown:
        raise ValueError("Unknown interests: " + ", ".join(sorted(unknown)))
    return selected - {PARENTS[tag] for tag in selected if tag in PARENTS}


def expand_with_parents(tags) -> set[str]:
    """An event tagged with a specialty also counts for its whole category.

    The reverse is NOT true: an event tagged with only a category says nothing
    about any one specialty.
    """
    tags = set(tags)
    return tags | {PARENTS[tag] for tag in tags if tag in PARENTS}


def check_majors(major_ids) -> list[str]:
    """Check the majors a user chose and return them tidied (lowercase, no repeats).

    Raises a ValueError with a message that is fine to show the user if:
    nothing is chosen, an ID is unknown, more than MAX_MAJORS are chosen,
    a co-major is chosen alone, or "Undecided" is mixed with another major.
    """
    chosen: list[str] = []
    for value in major_ids:
        major_id = normalize_tag(value) if isinstance(value, str) else ""
        if major_id not in chosen:
            chosen.append(major_id)

    if not chosen:
        raise ValueError("Choose at least one major (or Undecided).")
    unknown = [m for m in chosen if m not in MAJOR_IDS]
    if unknown:
        raise ValueError("Unknown majors: " + ", ".join(repr(m) for m in unknown))
    if len(chosen) > MAX_MAJORS:
        raise ValueError(f"Choose at most {MAX_MAJORS} majors.")
    if len(chosen) > 1 and any(m in EXCLUSIVE_MAJOR_IDS for m in chosen):
        raise ValueError("Undecided can't be combined with another major.")
    if all(m in CO_MAJOR_IDS for m in chosen):
        raise ValueError("International Business is a co-major: choose it together with another major.")
    return chosen


def colleges_for_majors(major_ids) -> set[str]:
    """The colleges a user's majors belong to (empty for Undecided and Other)."""
    return {college for major in major_ids for college in MAJOR_TO_COLLEGES.get(major, [])}


# ----------------------------------------------- text for the AI tagging prompt
# Sending every tag in one request is slow and makes the AI less accurate, so
# tagging is done in small steps:
#   1. the AI picks a few CATEGORIES from prompt_categories()
#   2. then it picks specialties from prompt_children(<those categories>)
#   3. it also picks the COLLEGES an event is meant for from prompt_colleges()


def prompt_categories() -> str:
    """One line per interest category: 'id: Name'."""
    return "\n".join(f"{c['id']}: {c['name']}" for c in INTERESTS)


def prompt_children(category_ids) -> str:
    """One line per specialty inside the chosen categories: 'full-id: Name'."""
    lines = []
    for category_id in category_ids:
        lines.extend(f"{child['id']}: {child['name']}" for child in children_of(category_id))
    return "\n".join(lines)


def prompt_colleges() -> str:
    """One line per college or school: 'id: Name'."""
    return "\n".join(f"{c['id']}: {c['name']}" for c in COLLEGES)


# ----------------------------------------------------------- for the frontend


def questionnaire_options() -> dict:
    """Everything the questionnaire needs, ready to send as JSON.

    The frontend should get this from the backend instead of keeping its own
    copy of the lists, so the two can never get out of sync.
    """
    return {
        "interests": copy.deepcopy(INTERESTS),
        "colleges": copy.deepcopy(COLLEGES),  # each college lists its majors
        "special_majors": copy.deepcopy(SPECIAL_MAJORS),
        "major_rules": {
            "min": 1,
            "max": MAX_MAJORS,
            "co_major_ids": list(CO_MAJOR_IDS),
            "exclusive_ids": list(EXCLUSIVE_MAJOR_IDS),
        },
    }