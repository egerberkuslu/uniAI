"""Tests for Turkish-aware normalization and prompting."""

from src.models.enums import Role, AccessScope
from src.models.user import Permission, User
from src.router.context_builder import ContextBuilder
from src.text.normalization import (
    augment_for_embedding,
    looks_turkish,
    normalize_for_matching,
    tokenize_for_matching,
)


def _user() -> User:
    return User(
        id=1,
        name="Test User",
        email="test@example.com",
        role=Role.ADMIN,
        department="all",
        permissions=(Permission(resource="orders", action="read", scope=AccessScope.ALL),),
    )


class TestNormalization:
    def test_normalize_turkish_letters(self):
        assert normalize_for_matching("Öğrenci İşleri ve Sınıf") == "ogrenci isleri ve sinif"

    def test_tokenize_turkish_ascii_equivalents(self):
        assert tokenize_for_matching("Ders kayıt yönergesi") == ("ders", "kayit", "yonerge")

    def test_tokenize_reduces_common_suffixes(self):
        assert tokenize_for_matching("yönergesine bölümünde öğrencileri") == ("yonerge", "bolum", "ogrenc")

    def test_augment_for_embedding_adds_ascii_variant(self):
        augmented = augment_for_embedding("Öğrenci danışmanı")
        assert "ogrenci danismani" in augmented

    def test_detects_turkish_queries(self):
        assert looks_turkish("Öğrenci not ortalaması nedir?")


class TestContextBuilder:
    def test_system_prompt_requests_turkish_response(self):
        prompt = ContextBuilder.build_system_prompt(_user(), "Mezuniyet gereksinimleri nedir?")
        assert "Respond in Turkish." in prompt
