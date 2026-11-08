"""Which interests each major is related to.

Most events are open to every major, so we don't tag events with majors. Instead,
each major points to the interests (from app/taxonomy.py) that students in that
major usually care about. If an event's tags overlap with those interests, the
event gets a small "related to your major" boost when we rank it.

HOW TO READ AND EDIT THIS FILE
- Each line is:  "major-id": [interest IDs, most important first]
- An entry can be a whole category ("music") or one specialty ("music:guitar").
- A category entry matches any event in that category. A specialty entry only
  matches events tagged with exactly that specialty, so it is the stronger signal.
- This is a judgment call, not a fact. If a line looks wrong to you, change it:
  tests/test_major_interests.py checks that every ID is real.
- Undecided and Other have no related interests, so they never get a boost.

Save this file as: app/matching/major_interests.py
"""

from app import taxonomy

MAJOR_INTERESTS: dict[str, list[str]] = {
    # ---- College of Agricultural and Environmental Sciences ----
    "agribusiness": ["business-entrepreneurship", "environment-sustainability"],
    "agricultural-and-applied-economics": ["finance-investing", "business-entrepreneurship"],
    "agricultural-and-environmental-science-communication": ["environment-sustainability", "writing-literature"],
    "agricultural-education": ["education-mentoring", "gardening-plants"],
    "agriscience-and-environmental-systems": ["environment-sustainability", "science-research", "gardening-plants"],
    "animal-and-dairy-science": ["animals-pets", "science-research"],
    "animal-biosciences": ["animals-pets", "science-research"],
    "animal-health": ["animals-pets", "healthcare-medicine"],
    "applied-biotechnology": ["science-research", "healthcare-medicine"],
    "avian-biology": ["nature-wildlife", "nature-wildlife:birdwatching", "science-research", "science-research:biology"],
    "biological-science": ["science-research", "science-research:biology", "healthcare-medicine"],
    "entomology": ["nature-wildlife", "science-research"],
    "environmental-economics-and-management": ["environment-sustainability", "finance-investing", "business-entrepreneurship"],
    "environmental-resource-science": ["environment-sustainability", "science-research"],
    "food-science": ["food-cooking", "science-research"],
    "horticulture": ["gardening-plants", "nature-wildlife"],
    "hospitality-and-food-industry-management": ["food-cooking", "business-entrepreneurship", "travel-exploration"],
    "poultry-science": ["animals-pets", "science-research"],
    "regenerative-bioscience": ["science-research", "healthcare-medicine"],
    "turfgrass-management": ["gardening-plants", "environment-sustainability"],
    "water-and-soil-resources": ["environment-sustainability", "science-research"],
    # ---- College of Engineering ----
    "agricultural-engineering": ["engineering-making", "environment-sustainability"],
    "biochemical-engineering": ["engineering-making", "science-research", "science-research:chemistry"],
    "biological-engineering": ["engineering-making", "engineering-making:biomedical", "science-research", "science-research:biology"],
    "civil-engineering": ["engineering-making", "engineering-making:civil"],
    "computer-systems-engineering": ["engineering-making", "engineering-making:computer", "technology-coding"],
    "electrical-and-electronics-engineering": ["engineering-making", "engineering-making:electrical"],
    "environmental-engineering": ["engineering-making", "engineering-making:environmental", "environment-sustainability"],
    "mechanical-engineering": ["engineering-making", "engineering-making:mechanical"],
    # ---- College of Environment and Design ----
    "landscape-architecture": ["visual-art-design", "environment-sustainability", "gardening-plants"],
    # ---- College of Family and Consumer Sciences ----
    "consumer-economics": ["finance-investing", "business-entrepreneurship"],
    "culinary-science-and-nutrition": ["food-cooking", "fitness-wellness", "science-research"],
    "dietetics": ["food-cooking", "healthcare-medicine", "fitness-wellness"],
    "family-and-consumer-sciences-education": ["education-mentoring", "food-cooking"],
    "fashion-merchandising": ["fashion-personal-style", "business-entrepreneurship"],
    "financial-planning": ["finance-investing", "business-entrepreneurship"],
    "furnishings-and-interiors": ["visual-art-design", "diy-crafts"],
    "housing-management-and-policy": ["law-government-policy", "community-service"],
    "human-development-and-family-science": ["psychology-human-behavior", "education-mentoring", "community-service"],
    "nutritional-sciences": ["fitness-wellness", "healthcare-medicine", "food-cooking"],
    "social-entrepreneurship-for-consumer-well-being": ["business-entrepreneurship", "community-service"],
    # ---- College of Pharmacy, College of Public Health, College of Veterinary Medicine ----
    "pharmaceutical-and-biomedical-sciences": ["healthcare-medicine", "science-research"],
    "environmental-health": ["healthcare-medicine", "healthcare-medicine:public-health", "environment-sustainability"],
    "health-promotion": ["healthcare-medicine", "healthcare-medicine:public-health", "fitness-wellness", "community-service"],
    "biomedical-physiology": ["science-research", "healthcare-medicine"],
    # ---- Franklin College of Arts and Sciences ----
    "african-american-studies": ["black-diaspora", "history-humanities", "social-justice-advocacy"],
    "anthropology": ["history-humanities", "languages-global-cultures", "cultural-exchange"],
    "arabic": ["languages-global-cultures", "languages-global-cultures:arabic", "middle-east-north-africa"],
    "art-animation": ["visual-art-design", "film-photography"],
    "art-ceramics": ["visual-art-design", "visual-art-design:pottery", "diy-crafts"],
    "art-drawing-and-painting": ["visual-art-design", "visual-art-design:drawing", "visual-art-design:painting"],
    "art-fabric-design": ["visual-art-design", "fashion-personal-style", "diy-crafts"],
    "art-graphic-design": ["visual-art-design", "visual-art-design:graphic-design"],
    "art-interior-design": ["visual-art-design", "diy-crafts"],
    "art-jewelry-and-metalwork": ["visual-art-design", "diy-crafts", "fashion-personal-style"],
    "art-photography-and-expanded-media": ["film-photography", "visual-art-design"],
    "art-printmaking": ["visual-art-design", "diy-crafts"],
    "art-scientific-illustration": ["visual-art-design", "visual-art-design:illustration", "science-research"],
    "art-sculpture-and-technology": ["visual-art-design", "visual-art-design:sculpture", "technology-coding"],
    "art-education": ["visual-art-design", "education-mentoring"],
    "art-history": ["visual-art-design", "history-humanities"],
    "art-interdisciplinary-art": ["visual-art-design"],
    "asian-languages-and-literature": ["languages-global-cultures", "east-asian-cultures", "writing-literature"],
    "astrophysics": ["astronomy-space", "science-research", "science-research:physics"],
    "atmospheric-sciences": ["science-research", "environment-sustainability"],
    "biochemistry-and-molecular-biology": ["science-research", "science-research:biology", "science-research:chemistry"],
    "biology": ["science-research", "science-research:biology", "healthcare-medicine"],
    "cellular-biology": ["science-research", "science-research:biology", "healthcare-medicine"],
    "chemistry": ["science-research", "science-research:chemistry"],
    "classics": ["history-humanities", "languages-global-cultures", "writing-literature"],
    "cognitive-science": ["psychology-human-behavior", "science-research", "technology-coding", "technology-coding:ai"],
    "communication-studies": ["career-leadership", "writing-literature", "psychology-human-behavior"],
    "comparative-literature-and-intercultural-studies": ["writing-literature", "languages-global-cultures", "cultural-exchange"],
    "dance": ["dance-performing-arts", "dance-performing-arts:dance"],
    "english": ["writing-literature", "history-humanities"],
    "film": ["film-photography", "film-photography:film"],
    "french": ["languages-global-cultures:french", "languages-global-cultures", "european-cultures"],
    "genetics": ["science-research", "science-research:biology", "healthcare-medicine"],
    "geography": ["environment-sustainability", "travel-exploration", "science-research"],
    "geology": ["science-research", "outdoors-adventure", "environment-sustainability"],
    "german": ["languages-global-cultures:german", "languages-global-cultures", "european-cultures"],
    "history": ["history-humanities", "history-humanities:history"],
    "latin-american-and-caribbean-studies": ["latin-caribbean-cultures", "languages-global-cultures", "history-humanities"],
    "linguistics": ["languages-global-cultures", "science-research"],
    "mathematics": ["science-research", "technology-coding"],
    "microbiology": ["science-research", "science-research:biology", "healthcare-medicine"],
    "music-major": ["music"],
    "music-composition": ["music", "music:songwriting"],
    "music-education": ["music", "education-mentoring"],
    "music-performance": ["music", "music:live-music", "music:concerts"],
    "music-theory": ["music"],
    "music-therapy": ["music", "psychology-human-behavior", "healthcare-medicine"],
    "neuroscience": ["psychology-human-behavior", "science-research", "healthcare-medicine"],
    "ocean-science": ["science-research", "environment-sustainability", "nature-wildlife"],
    "philosophy": ["history-humanities", "history-humanities:philosophy"],
    "physics": ["science-research", "science-research:physics", "astronomy-space"],
    "plant-biology": ["science-research", "gardening-plants", "nature-wildlife"],
    "psychology": ["psychology-human-behavior", "psychology-human-behavior:psychology", "science-research"],
    "religion": ["faith-spirituality", "history-humanities"],
    "romance-languages": ["languages-global-cultures", "european-cultures", "latin-caribbean-cultures"],
    "russian": ["languages-global-cultures", "european-cultures"],
    "sociology": ["social-justice-advocacy", "community-service", "psychology-human-behavior"],
    "spanish": ["languages-global-cultures:spanish", "languages-global-cultures", "latin-caribbean-cultures"],
    "statistics": ["science-research", "technology-coding"],
    "theatre": ["dance-performing-arts", "dance-performing-arts:theater", "dance-performing-arts:acting"],
    "womens-and-gender-studies": ["social-justice-advocacy", "history-humanities"],
    # ---- Grady College of Journalism and Mass Communication ----
    "advertising": ["business-entrepreneurship", "business-entrepreneurship:marketing", "visual-art-design", "visual-art-design:graphic-design"],
    "entertainment-and-media-studies": ["film-photography", "music"],
    "journalism": ["writing-literature", "law-government-policy"],
    "public-relations": ["business-entrepreneurship", "business-entrepreneurship:marketing", "career-leadership"],
    # ---- Mary Frances Early College of Education ----
    "communication-sciences-and-disorders": ["healthcare-medicine", "psychology-human-behavior", "education-mentoring"],
    "elementary-education": ["education-mentoring", "education-mentoring:teaching"],
    "english-education": ["education-mentoring", "writing-literature"],
    "exercise-and-sport-science": ["fitness-wellness", "sports-recreation", "healthcare-medicine"],
    "health-and-physical-education": ["fitness-wellness", "sports-recreation", "education-mentoring"],
    "mathematics-education": ["education-mentoring", "science-research"],
    "middle-grades-education": ["education-mentoring"],
    "science-education": ["education-mentoring", "science-research"],
    "social-studies-education": ["education-mentoring", "history-humanities"],
    "special-education": ["education-mentoring", "psychology-human-behavior", "community-service"],
    "sport-management": ["sports-recreation", "spectator-sports", "business-entrepreneurship"],
    "tesol-and-world-language-education": ["education-mentoring", "languages-global-cultures"],
    "workforce-education": ["education-mentoring", "career-leadership"],
    # ---- Odum School of Ecology ----
    "ecology": ["environment-sustainability", "nature-wildlife", "nature-wildlife:ecology", "science-research"],
    # ---- School of Computing ----
    "computer-science": ["technology-coding", "technology-coding:computer-science", "technology-coding:programming"],
    "data-science": ["technology-coding", "technology-coding:ai", "science-research"],
    # ---- School of Public and International Affairs ----
    "criminal-justice": ["law-government-policy", "law-government-policy:law", "social-justice-advocacy"],
    "international-affairs": ["law-government-policy", "languages-global-cultures", "cultural-exchange"],
    "political-science": ["law-government-policy", "law-government-policy:politics", "law-government-policy:government"],
    # ---- School of Social Work ----
    "social-work": ["community-service", "social-justice-advocacy", "psychology-human-behavior"],
    # ---- Terry College of Business ----
    "accounting": ["finance-investing", "business-entrepreneurship", "career-leadership"],
    "economics": ["finance-investing", "finance-investing:markets", "business-entrepreneurship"],
    "finance": ["finance-investing", "finance-investing:investing", "finance-investing:markets", "career-leadership"],
    "international-business": ["business-entrepreneurship", "languages-global-cultures", "cultural-exchange"],
    "management": ["business-entrepreneurship", "career-leadership"],
    "management-information-systems": ["technology-coding", "business-entrepreneurship"],
    "marketing": ["business-entrepreneurship", "business-entrepreneurship:marketing"],
    "real-estate": ["business-entrepreneurship", "finance-investing"],
    "risk-management-and-insurance": ["finance-investing", "business-entrepreneurship"],
    # ---- Warnell School of Forestry and Natural Resources ----
    "fisheries-and-wildlife": ["nature-wildlife", "nature-wildlife:wildlife", "outdoors-adventure", "environment-sustainability"],
    "forestry": ["nature-wildlife", "environment-sustainability", "outdoors-adventure"],
    "natural-resource-management-and-sustainability": [
        "environment-sustainability", "environment-sustainability:sustainability", "environment-sustainability:conservation",
    ],
    "parks-recreation-and-tourism-management": ["outdoors-adventure", "sports-recreation", "sports-recreation:recreation", "travel-exploration"],
    # ---- Special choices: no related interests, so no boost ----
    "undecided": [],
    "other": [],
}


def related_interests(major_id: str) -> list[str]:
    """The interests related to one major (empty for an unknown major)."""
    return list(MAJOR_INTERESTS.get(taxonomy.normalize_tag(major_id), []))


def interests_for_majors(major_ids: list[str]) -> list[str]:
    """All interests related to any of the majors: no repeats, in order."""
    return list(dict.fromkeys(i for major in major_ids for i in related_interests(major)))


def major_matches(event_tags: list[str], major_ids: list[str]) -> dict[str, list[str]]:
    """For each major that relates to this event, which related interests matched.

    An event tagged with a specialty also counts for that specialty's category, but
    a category-only event never counts for a specialty. Majors with no match are left out.
    Keys follow the order of `major_ids`.
    """
    real_tags = taxonomy.keep_valid(list(event_tags), list(taxonomy.LABELS))
    event_interests = set(taxonomy.expand_with_parents(real_tags))
    matches: dict[str, list[str]] = {}
    for major in major_ids:
        hits = [i for i in related_interests(major) if i in event_interests]
        if hits:
            matches[major] = hits
    return matches