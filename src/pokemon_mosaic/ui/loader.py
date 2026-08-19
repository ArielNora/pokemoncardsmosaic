"""Chargement des cartes en arrière-plan.

Les ~280 cartes prennent environ 4 secondes à charger. Le faire dans le fil
principal figerait la fenêtre : Qt ne redessine rien tant que la boucle
d'événements est occupée.
"""

from PySide6.QtCore import QObject, QThread, Signal

from ..cards import load_cards


class CardLoader(QObject):
    """Travailleur destiné à vivre dans un QThread."""

    progress = Signal(int, int)
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, data_dir: str, scale: float = 0.25, strip_size: float = 0.1):
        super().__init__()
        self._data_dir = data_dir
        self._scale = scale
        self._strip_size = strip_size

    def run(self) -> None:
        try:
            card_set = load_cards(
                self._data_dir,
                scale=self._scale,
                strip_size=self._strip_size,
                progress=lambda done, total: self.progress.emit(done, total),
            )
        except Exception as error:  # remonté à l'interface, jamais avalé
            self.failed.emit(str(error))
            return

        if not len(card_set):
            self.failed.emit(f"Aucune image trouvée dans {self._data_dir}")
            return
        self.loaded.emit(card_set)


def start_loading(parent, data_dir, on_progress, on_loaded, on_failed):
    """Lance un chargement et renvoie (thread, worker) à garder en vie.

    Qt détruit un QThread dont plus personne ne détient de référence, ce qui
    interromprait le chargement en silence — d'où le renvoi du couple.
    """
    thread = QThread(parent)
    worker = CardLoader(data_dir)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.progress.connect(on_progress)
    worker.loaded.connect(on_loaded)
    worker.failed.connect(on_failed)
    worker.loaded.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)

    thread.start()
    return thread, worker
