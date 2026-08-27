# Empaquetage macOS

```bash
paquet/construire.sh
```

Produit `dist/Pokémon Mosaic.app`, **118 Mo**, autonome : ni Python ni Qt à
installer.

## Ce que le paquet contient

Le code et les traductions. **Pas les illustrations** : 56 Mo qui changent à
chaque extension et appartiennent à leurs ayants droit. **Pas le catalogue non
plus** — l'application va chercher `cards.json` au miroir, ce qui évite qu'une
copie embarquée le jour de la construction diverge de celle qui est publiée.

Au premier lancement, l'étape 1 s'ouvre sur deux boutons : télécharger les
cartes depuis le miroir, ou désigner un dossier qui les contient déjà. Le
dossier retenu est mémorisé, l'écran d'accueil ne reparaît donc qu'une fois.

Les modules PySide6 inutilisés — moteur web, QML, multimédia, base de données —
sont exclus, ainsi qu'`opencv`, `scipy` et `scikit-learn`, qui ne servent qu'à
`experiments/`.

## Où l'application range ses fichiers

| | Depuis le dépôt | Une fois installée |
|---|---|---|
| Cartes | `data/pokemoncards/` | celui que l'utilisateur désigne, proposé sous `~/Pictures/Pokémon Mosaic/cartes/` |
| Mosaïques | `output/` | `~/Pictures/Pokémon Mosaic/` |
| Préréglages | `~/Library/Preferences/Pokémon Mosaic/presets/` | idem |
| Dossier retenu | réglages `Pokémon Mosaic` | idem |

Écrire à côté de l'exécutable est impossible : un `.app` installé dans
`/Applications` est en lecture seule pour l'utilisateur courant. Le dossier de
cartes est **proposé** et non imposé : `~/Pictures` est visible et sauvegardé,
là où un recoin de données applicatives ne l'est pas.

## ⚠️ La signature

**Le paquet n'est pas signé valablement.** `codesign --verify` et `spctl`
rendent tous deux 1 :

```
a sealed resource is missing or invalid
code has no resources but signature indicates they must be present
```

C'est un défaut connu de la combinaison PyInstaller + `.app` macOS, et la
signature ad-hoc de PyInstaller échoue de la même façon.

**Conséquence pratique** : l'application démarre sur la machine qui l'a
construite — elle n'y porte pas d'attribut de quarantaine — et démarre aussi
depuis un autre emplacement, vérifié. Mais **transmise à quelqu'un d'autre**,
Gatekeeper la refusera ; il faudrait alors un clic droit → Ouvrir, ou lever la
quarantaine à la main.

Une distribution propre suppose de toute façon un **Developer ID** Apple
(compte payant) et une notarisation, qui imposent de reprendre la signature
entièrement. Tant que l'application ne sort pas de vos machines, ce défaut n'a
pas de conséquence.

## Autres systèmes

Non traité. PyInstaller construit pour le système sur lequel il tourne : un
paquet Windows ou Linux demande une machine correspondante.
