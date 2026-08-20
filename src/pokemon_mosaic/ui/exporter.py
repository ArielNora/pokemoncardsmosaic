"""Écriture du poster en arrière-plan.

Un export pleine résolution relit les ~280 fichiers d'origine et assemble une
image de plusieurs dizaines de millions de pixels : plusieurs dizaines de
secondes pendant lesquelles la fenêtre resterait figée si le travail avait lieu
dans le fil principal.
"""

from PySide6.QtCore import QObject, QThread, Signal

from ..export import ExportCancelled, PosterSettings, export_poster


class ExportWorker(QObject):
    """Travailleur destiné à vivre dans un QThread."""

    progress = Signal(int, int, str)   # panneau commencé, total, fichier visé
    exported = Signal(list)            # chemins écrits
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, grid, cards, settings: PosterSettings, path: str,
                 full_resolution: bool = True):
        super().__init__()
        self._grid = grid
        self._cards = cards
        self._settings = settings
        self._path = path
        self._full_resolution = full_resolution
        self._cancelled = False

    def cancel(self) -> None:
        """Demande l'arrêt. Le travailleur le voit au début de la ligne suivante.

        Sans cela, fermer la fenêtre pendant un export détruirait un QThread
        encore actif, ce que Qt sanctionne par un abandon du processus.
        """
        self._cancelled = True

    def run(self) -> None:
        try:
            written = export_poster(
                self._grid, self._cards, self._settings, self._path,
                full_resolution=self._full_resolution,
                on_progress=lambda panel, total, target:
                    self.progress.emit(panel, total, target),
                check_cancelled=lambda: self._cancelled,
            )
        except ExportCancelled:
            self.cancelled.emit()
            return
        except Exception as error:  # noqa: BLE001 - remonté plutôt qu'avalé
            # Volontairement large : une exception qui s'échappe de ce slot
            # n'émettrait aucun signal, donc thread.quit() ne serait jamais
            # appelé et l'interface attendrait un export qui n'existe plus.
            self.failed.emit(str(error))
            return
        self.exported.emit(written)


def start_export(parent, grid, cards, settings, path, full_resolution=True,
                 **handlers):
    """Lance un export en fond. Renvoie (thread, worker) à garder en vie."""
    thread = QThread(parent)
    worker = ExportWorker(grid, cards, settings, path, full_resolution)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    for name, slot in handlers.items():
        getattr(worker, name).connect(slot)
    for signal in (worker.exported, worker.cancelled, worker.failed):
        signal.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)

    thread.start()
    return thread, worker
