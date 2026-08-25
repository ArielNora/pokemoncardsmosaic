# Empaquetage macOS

```bash
paquet/construire.sh
```

Produit `dist/Pokémon Mosaic.app`, **118 Mo**, autonome : ni Python ni Qt à
installer.

## Ce que le paquet contient

Le code et les traductions. **Pas les illustrations** : 56 Mo qui changent à
chaque extension et appartiennent à leurs ayants droit. Au premier lancement,
l'application propose le dossier de cartes s'il existe, sinon l'utilisateur le
désigne lui-même à l'étape 1.

Les modules PySide6 inutilisés — moteur web, QML, multimédia, base de données —
sont exclus, ainsi qu'`opencv`, `scipy` et `scikit-learn`, qui ne servent qu'à
`experiments/`.

## Où l'application range ses fichiers

| | Depuis le dépôt | Une fois installée |
|---|---|---|
| Cartes | `data/pokemoncards/` | `~/Library/Application Support/Pokémon Mosaic/pokemoncards/` |
| Mosaïques | `output/` | `~/Pictures/Pokémon Mosaic/` |

Écrire à côté de l'exécutable est impossible : un `.app` installé dans
`/Applications` est en lecture seule pour l'utilisateur courant.

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
