"""Téléchargement des cartes depuis le miroir, en arrière-plan.

Même raison d'être que `loader.py` : le faire dans le fil principal figerait la
fenêtre, Qt ne redessinant rien tant que sa boucle d'événements est occupée. Ici
l'attente se compte en dizaines de secondes et non en quelques-unes — 56 Mo sur
une ligne ordinaire —, donc le besoin est plus fort encore.

Le travailleur enchaîne deux temps : le **catalogue**, puis les **archives**. Ce
découpage n'est pas cosmétique — récupérer le catalogue seul suffit à dire
combien de cartes manquent, ce qui permet de répondre « rien à faire » sans
avoir rien téléchargé de lourd.
"""

from PySide6.QtCore import QObject, QThread, Signal

from ..mirror import (
    MirrorError,
    Outcome,
    fetch_manifest,
    fetch_mirror,
    missing_bytes,
    missing_cards,
)


class CardDownloader(QObject):
    """Travailleur destiné à vivre dans un QThread."""

    # (octets faits, octets attendus, nom de l'extension en cours)
    progress = Signal(int, int, str)
    # Le catalogue est là : (cartes manquantes, octets à télécharger)
    surveyed = Signal(int, int)
    # (cartes écrites, échecs) — `échecs` est une liste de (quoi, pourquoi)
    finished = Signal(int, list)
    failed = Signal(str)
    # Émis à la place de `finished` quand l'utilisateur a interrompu : sans lui,
    # une interruption ressemblerait trait pour trait à une fin normale, et
    # l'interface annoncerait « terminé » sur un dossier incomplet.
    cancelled = Signal(int)

    def __init__(self, directory: str, workers: int = 4):
        super().__init__()
        self._directory = directory
        self._workers = workers
        self._cancelled = False

    def cancel(self) -> None:
        """Demande l'arrêt. Vu par le fil avant chaque archive."""
        self._cancelled = True

    def run(self) -> None:
        try:
            manifest = fetch_manifest()
        except MirrorError as error:
            self.failed.emit(str(error))
            return
        if self._cancelled:
            self.cancelled.emit(0)
            return

        manquantes = missing_cards(manifest, self._directory)
        self.surveyed.emit(len(manquantes), missing_bytes(manifest, manquantes))
        if not manquantes:
            self.finished.emit(0, [])
            return

        try:
            tally, failures = fetch_mirror(
                manifest, self._directory, self._workers,
                progress=lambda faits, total, jeu: self.progress.emit(
                    faits, total, jeu),
                cancelled=lambda: self._cancelled,
            )
        except MirrorError as error:
            self.failed.emit(str(error))
            return
        except OSError as error:
            # Disque plein, dossier devenu non inscriptible : sans ce filet,
            # l'échec disparaîtrait avec le fil, sans trace pour l'utilisateur.
            self.failed.emit(str(error))
            return

        # La constante et non sa valeur : écrite en dur, ce compte tomberait
        # silencieusement à zéro le jour où le libellé change, et l'interface
        # annoncerait « 0 carte récupérée » sur un téléchargement réussi.
        ecrites = tally.get(Outcome.FETCHED, 0)
        if self._cancelled:
            self.cancelled.emit(ecrites)
            return
        self.finished.emit(ecrites, failures)


def start_download(parent, directory, on_progress, on_surveyed, on_finished,
                   on_failed, on_cancelled, workers: int = 4):
    """Lance un téléchargement et renvoie (thread, worker) à garder en vie.

    Qt détruit un QThread dont plus personne ne détient de référence, ce qui
    interromprait le téléchargement en silence — d'où le renvoi du couple.
    """
    thread = QThread(parent)
    worker = CardDownloader(directory, workers=workers)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.progress.connect(on_progress)
    worker.surveyed.connect(on_surveyed)
    worker.finished.connect(on_finished)
    worker.failed.connect(on_failed)
    worker.cancelled.connect(on_cancelled)
    for signal in (worker.finished, worker.failed, worker.cancelled):
        signal.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)

    thread.start()
    return thread, worker
