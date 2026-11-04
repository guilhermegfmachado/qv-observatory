"""Seeded synthetic corpus for tests and the site demo. NOT real data.

Built so the analyses have something to find: 'resilience' rises in EU policy from 2019 and
in art discourse about two years later, with its collocates shifting from infrastructure
vocabulary to care vocabulary.
"""
from __future__ import annotations

import random
from pathlib import Path

FILLER = {
    "en": "The committee discussed the annual budget and the schedule for the next meeting.",
    "pt": "A comissão discutiu o orçamento anual e o calendário da próxima reunião.",
    "nl": "De commissie besprak de jaarlijkse begroting en het schema voor de volgende vergadering.",
    "fr": "Le comité a discuté du budget annuel et du calendrier de la prochaine réunion.",
}
EARLY = {
    "en": "Resilience of energy infrastructure and supply chains requires investment.",
    "pt": "A resiliência das infraestruturas energéticas e das cadeias de abastecimento exige investimento.",
    "nl": "Veerkracht van energie-infrastructuur en toeleveringsketens vraagt om investeringen.",
    "fr": "La résilience des infrastructures énergétiques et des chaînes d'approvisionnement exige des investissements.",
}
LATE = {
    "en": "Resilience grows from community, care and collective healing after loss.",
    "pt": "A resiliência nasce da comunidade, do cuidado e da cura colectiva depois da perda.",
    "nl": "Veerkracht groeit uit gemeenschap, zorg en collectief herstel na verlies.",
    "fr": "La résilience naît de la communauté, du soin et de la guérison collective après la perte.",
}
ONSET = {"policy": 2019, "parliament": 2020, "news": 2020, "art": 2021}


def build(root: Path, seed: int = 7, per_month: int = 6) -> int:
    rng = random.Random(seed)
    n = 0
    for domain, onset in ONSET.items():
        for lang in FILLER:
            for year in range(2017, 2026):
                for month in range(1, 13):
                    for k in range(per_month if lang == "en" else per_month // 2):
                        months_in = (year - onset) * 12 + month
                        p = 0 if months_in < 0 else min(0.7, 0.05 + months_in / 60)
                        parts = [FILLER[lang]] * rng.randint(2, 4)
                        if rng.random() < p:
                            late = rng.random() < min(1.0, max(0.0, (year - 2020) / 4))
                            parts.append((LATE if late else EARLY)[lang])
                        rng.shuffle(parts)
                        d = root / domain / lang
                        d.mkdir(parents=True, exist_ok=True)
                        (d / f"{year}-{month:02d}-{1 + k:02d}__doc-{k}.txt").write_text(
                            f"# Synthetic {domain} {lang} {year}-{month:02d} #{k}\n" + " ".join(parts),
                            encoding="utf-8")
                        n += 1
    return n


if __name__ == "__main__":
    import sys
    print(build(Path(sys.argv[1])), "documents written")
