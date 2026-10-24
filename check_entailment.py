import re
from backend.app.services.embedding_service import embedding_service

claim_text = "Adaptive closed-loop intervention achieved 92.4% retention at week 12 versus 78.1% in controls."
passage_text = "In the multicenter randomized trial, participants randomized to adaptive closed-loop protocol achieved 92.4% retention at week 12 compared to 78.1% in static controls. Secondary fatigue was reduced solely in the severe baseline fatigue subgroup. Headaches were never recorded."

claim_emb = embedding_service.embed_text(claim_text)
passage_emb = embedding_service.embed_text(passage_text)
sim_score = embedding_service.cosine_similarity(claim_emb, passage_emb)

claim_words = set(re.findall(r"\b[a-zA-Z0-9%.-]{3,}\b", claim_text.lower()))
stopwords = {"the", "and", "that", "this", "were", "with", "from", "have", "been", "also", "then"}
informative_claim_words = claim_words - stopwords

passage_lower = passage_text.lower()
matched_words = [w for w in informative_claim_words if w in passage_lower]
match_ratio = len(matched_words) / max(len(informative_claim_words), 1)

claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", claim_text))
matched_numbers = [n for n in claim_numbers if n in passage_text]
number_match_ratio = len(matched_numbers) / max(len(claim_numbers), 1) if claim_numbers else 1.0

print("sim_score:", sim_score)
print("claim_words:", claim_words)
print("informative_claim_words:", informative_claim_words)
print("matched_words:", matched_words)
print("match_ratio:", match_ratio)
print("claim_numbers:", claim_numbers)
print("matched_numbers:", matched_numbers)
print("number_match_ratio:", number_match_ratio)
