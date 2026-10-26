"""Seed curriculum vocabulary only when a reviewed textbook passage supports it."""
import re

from english7.modules.flashcards.domain import normalize_word
from english7.modules.flashcards.repository import SQLAlchemyFlashcardRepository
from english7.modules.knowledge.curriculum_ontology import get_curriculum_ontology


def seed_textbook_flashcards(session_factory) -> int:
    ontology = get_curriculum_ontology()
    count = 0
    with SQLAlchemyFlashcardRepository(session_factory).transaction() as tx:
        for unit, fragment in tx.verified_sources():
            content = normalize_word(fragment.normalized_text)
            for vocabulary in ontology.vocabulary:
                word = normalize_word(vocabulary.word)
                if vocabulary.unit_number != unit.number or not re.search(r'(?<!\w)' + re.escape(word) + r'(?:s|es|d|ed|ing)?(?!\w)', content):
                    continue
                deck = tx.textbook_deck(unit.id)
                if deck is None:
                    deck = tx.create_deck(name=f'Unit {unit.number}: {unit.title}', kind='textbook', unit_number=unit.number, unit_id=unit.id)
                if any(card.normalized_word == word for card in tx.cards(deck.id)):
                    continue
                example = vocabulary.example if normalize_word(vocabulary.example) in content else ''
                tx.create_card(deck_id=deck.id, word=vocabulary.word, normalized_word=word, meaning=vocabulary.meaning_vi, ipa=vocabulary.ipa, pos=vocabulary.pos, example=example, notes='', source_fragment_id=fragment.id, unit_number=unit.number, page=fragment.printed_page, is_published=True)
                count += 1
    return count


def main() -> None:
    from english7.db.session import get_session_factory
    print(f'Seeded {seed_textbook_flashcards(get_session_factory())} verified textbook flashcards')


if __name__ == '__main__':
    main()
