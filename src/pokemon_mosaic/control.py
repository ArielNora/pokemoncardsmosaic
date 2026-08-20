"""Contrôle d'une optimisation en cours : arrêt, pause, reprise.

L'optimisation est une boucle serrée qui tourne plusieurs secondes dans un fil de
fond. Pour que l'utilisateur puisse l'arrêter ou la suspendre, elle consulte
périodiquement cet objet — il n'y a pas d'autre moyen d'interrompre une boucle
Python sans risque.

Sans dépendance à Qt : le cœur reste utilisable et testable sans interface.
"""

import threading
import time


class RunControl:
    """Drapeaux partagés entre le fil qui calcule et celui qui commande.

    Les méthodes `stop`, `pause` et `resume` sont appelées depuis le fil de
    l'interface ; `checkpoint` depuis celui qui calcule.
    """

    def __init__(self):
        self._stop = threading.Event()
        # Posé = on avance. C'est le sens qui permet au calcul d'attendre sur
        # l'événement plutôt que de scruter un booléen.
        self._running = threading.Event()
        self._running.set()
        self._paused_seconds = 0.0

    # --- Commandes (fil de l'interface) -----------------------------------

    def stop(self) -> None:
        self._stop.set()
        # On relâche une éventuelle pause, sinon le calcul resterait bloqué à
        # attendre une reprise qui ne viendrait jamais.
        self._running.set()

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    # --- Consultation (fil de calcul) -------------------------------------

    def checkpoint(self) -> bool:
        """Bloque tant que la pause dure, puis dit s'il faut continuer.

        L'arrêt est consulté **avant** la pause : attendre d'abord une reprise
        laisserait le calcul bloqué indéfiniment si l'utilisateur clique Pause
        juste après Arrêter, et la fenêtre se figerait à la fermeture puisqu'elle
        attend ce fil.

        Le temps passé en pause est comptabilisé à part : il ne doit pas être
        décompté d'un budget de temps, sinon suspendre le calcul pour examiner la
        timeline le ferait expirer.
        """
        if self.stop_requested:
            return False
        if self.paused:
            started = time.monotonic()
            self._running.wait()
            self._paused_seconds += time.monotonic() - started
        return not self.stop_requested

    @property
    def paused_seconds(self) -> float:
        return self._paused_seconds
