"""Chargement des cartes en arrière-plan.

Les ~280 cartes prennent environ 4 secondes à charger. Le faire dans le fil
principal figerait la fenêtre : Qt ne redessine rien tant que la boucle
d'événements est occupée.
"""

from PySide6.QtCore import QObject, QThread, Signal

from ..cards import load_cards


class _Cancelled(Exception):
    """Signal interne : le chargement a été interrompu à la demande."""


class CardLoader(QObject):
    """Travailleur destiné à vivre dans un QThread."""

    progress = Signal(int, int)
    folder_loaded = Signal(str, list)
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, data_dir: str, scale: float = 0.25, strip_size: float = 0.1):
        super().__init__()
        self._data_dir = data_dir
        self._scale = scale
        self._strip_size = strip_size
        self._cancelled = False

    def cancel(self) -> None:
        """Demande l'arrêt du chargement.

        Appelée depuis le fil principal ; le travailleur voit le drapeau au
        prochain rappel de progression. Sans cela, fermer la fenêtre pendant les
        ~4 s de chargement détruirait un QThread encore actif, ce que Qt
        sanctionne par un abandon du processus.
        """
        self._cancelled = True

    def _check_cancelled(self) -> None:
        if self._cancelled:
            raise _Cancelled

    def _report(self, done: int, total: int) -> None:
        self._check_cancelled()
        self.progress.emit(done, total)

    def run(self) -> None:
        try:
            card_set = load_cards(
                self._data_dir,
                scale=self._scale,
                strip_size=self._strip_size,
                progress=self._report,
                check_cancelled=self._check_cancelled,
                on_folder=lambda folder, cards: self.folder_loaded.emit(folder, cards),
            )
        except _Cancelled:
            return
        except Exception as error:  # noqa: BLE001 - tout échec du fil de fond
            # doit remonter à l'interface, sinon il disparaîtrait sans trace.
            self.failed.emit(str(error))
            return

        if not len(card_set):
            self.failed.emit(f"Aucune image trouvée dans {self._data_dir}")
            return
        self.loaded.emit(card_set)


def start_loading(parent, data_dir, on_progress, on_folder, on_loaded, on_failed,
                  scale: float = 0.25, strip_size: float = 0.1):
    """Lance un chargement et renvoie (thread, worker) à garder en vie.

    Qt détruit un QThread dont plus personne ne détient de référence, ce qui
    interromprait le chargement en silence, d'où le renvoi du couple.
    """
    thread = QThread(parent)
    worker = CardLoader(data_dir, scale=scale, strip_size=strip_size)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.progress.connect(on_progress)
    worker.folder_loaded.connect(on_folder)
    worker.loaded.connect(on_loaded)
    worker.failed.connect(on_failed)
    worker.loaded.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)

    thread.start()
    return thread, worker
