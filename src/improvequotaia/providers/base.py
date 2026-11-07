"""Base commune des modules « outil ». Un module = une classe Provider avec detect() et fetch().

Pour ajouter un outil : créer un fichier dans ce dossier, sous-classer Provider, puis l'ajouter
à ALL_PROVIDERS dans providers/__init__.py. fetch() est appelé dans un thread : pas de Qt ici.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from ..pace import Pace

FIVE_H = 5 * 3600
WEEK = 7 * 86400


class ProviderError(Exception):
    """Erreur affichée dans l'en-tête de la section (les dernières valeurs restent affichées)."""


class ToolMissing(ProviderError):
    """Outil absent ou non connecté : la section est masquée."""


@dataclass
class Bucket:
    key: str                      # identifiant unique et stable
    group: str                    # identifiant du groupe (sélectionnable dans « Affichage »)
    group_label: str              # nom affiché du groupe
    win: str                      # "5h", "7d" ou autre identifiant de fenêtre
    frac: Optional[float]         # part consommée 0..1 (None = inconnue)
    reset_at: Optional[datetime]
    window_s: Optional[int]       # durée de la fenêtre en secondes (pour le rythme)
    disabled: bool = False
    win_label: Optional[str] = None  # précision affichée avant la fenêtre (ex. « Premium », « Pro »)
    note: Optional[str] = None    # texte à la place du compte à rebours (ex. « désactivé »)
    tooltip: Optional[str] = None
    pace: Optional[Pace] = field(default=None, compare=False)


@dataclass
class ProviderResult:
    buckets: List[Bucket]
    updated_at: float
    source: Optional[str] = None       # ex. « Claude Code », « API »
    note: Optional[str] = None         # infobulle de l'en-tête (ex. erreur secondaire)
    title_extra: Optional[str] = None  # ex. « Pro · Opus 5.5 (xhigh) »


class Provider:
    id: str = ""
    label: str = ""                      # nom affiché (assistant, réglages)
    title: str = ""                      # titre de section
    groups: List[Tuple[str, str]] = []   # groupes connus : (identifiant, nom affiché)
    interval: float = 10.0
    experimental: bool = False

    def detect(self) -> bool:
        """Vrai si l'outil semble installé sur cet ordinateur (assistant de démarrage)."""
        raise NotImplementedError

    def fetch(self) -> ProviderResult:
        """Récupère les quotas. Lève ToolMissing / ProviderError en cas de problème."""
        raise NotImplementedError


def window_id(minutes: Optional[float]) -> str:
    if minutes is None:
        return "?"
    if 280 <= minutes <= 310:
        return "5h"
    if 9900 <= minutes <= 10200:
        return "7d"
    if 1380 <= minutes <= 1500:
        return "1d"
    if 39000 <= minutes <= 46000:  # 27 à 32 jours
        return "1mo"
    return f"{int(minutes)}m"
