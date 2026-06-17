# Implied Volatility Surface — NVDA Options

Ce projet part d'un exercice scolaire d'interpolation numérique en C++ et a été étendu de manière autonome pour construire et visualiser la **surface de volatilité implicite** des options call NVIDIA en Python.

---

## Structure du projet

```
nvda-implied-volatility/
├── cpp/
│   └── interpolation.cpp       # Interpolation par spline cubique — partie scolaire
├── python/
│   ├── clean_data.py           # Nettoyage des données brutes
│   └── vol_surface.py          # Filtrage qualité + visualisation de la surface
├── data/
│   ├── nvda_calls_raw.xlsx     # Données brutes (options call NVDA, 5 mai 2026)
│   └── nvda_calls_clean.csv    # Données nettoyées (générées par clean_data.py)
├── output/
│   ├── vol_surface_cubic.png   # Surface interpolée — méthode cubic
│   └── vol_surface_linear.png  # Surface interpolée — méthode linear
├── .gitignore
└── README.md
```

---

## Partie 1 — Interpolation en C++ (partie scolaire)

### Objectif

Interpoler la volatilité implicite en deux dimensions à partir des données de marché : d'abord le long de l'axe des strikes pour un DTM donné, puis le long de l'axe du temps jusqu'à maturité.

### Algorithme : spline cubique naturelle

Une spline cubique naturelle garantit la continuité de la fonction, de sa dérivée première et de sa dérivée seconde à chaque nœud. Les conditions aux bords naturelles imposent une dérivée seconde nulle aux extrémités (M₀ = Mₙ = 0), ce qui évite les oscillations parasites en dehors de la plage de données.

La résolution du système tridiagonal est faite via l'**algorithme de Thomas** (élimination de Gauss adaptée aux matrices bandes), d'une complexité O(n) au lieu de O(n³) pour une élimination gaussienne générale.

**Formule d'interpolation sur l'intervalle [xⱼ, xⱼ₊₁] :**

$$S(x) = \frac{M_j}{6h_j}(x_{j+1}-x)^3 + \frac{M_{j+1}}{6h_j}(x-x_j)^3 + \left(\frac{y_j}{h_j} - \frac{M_j h_j}{6}\right)(x_{j+1}-x) + \left(\frac{y_{j+1}}{h_j} - \frac{M_{j+1} h_j}{6}\right)(x-x_j)$$

où Mᵢ sont les dérivées secondes calculées par l'algorithme de Thomas et hⱼ = xⱼ₊₁ − xⱼ.

### Fonctionnement (interactive)

1. Lecture du fichier `data/nvda_calls_clean.csv`
2. Groupement des données par DTM
3. Saisie d'un strike cible par l'utilisateur
4. Pour chaque DTM : interpolation de l'IV au strike cible → vecteur `ivAtStrike`
5. Saisie d'un DTM cible
6. Interpolation finale de l'IV le long de l'axe DTM

Le résultat est une interpolation **2D séquentielle** : strike d'abord, maturité ensuite.

---

## Partie 2 — Surface de volatilité en Python (extension personnelle)

### Objectif

Visualiser la surface complète de volatilité implicite en 3D plutôt qu'un seul point interpolé, en traitant la qualité des données de marché en amont.

### Données

Options call NVDA collectées le 5 mai 2026, couvrant 7 maturités :

| DTM | Maturité |
|-----|----------|
| 1   | 6 mai 2026 |
| 6   | 11 mai 2026 |
| 8   | 13 mai 2026 |
| 10  | 15 mai 2026 |
| 17  | 22 mai 2026 |
| 24  | 29 mai 2026 |
| 31  | 5 juin 2026 |

Plage de strikes : 160 $ à 265 $, soit environ 153 contrats initiaux.

### Filtrage qualité des données

Avant d'interpoler, les options illiquides sont exclues car leur IV, calculée par le marché à partir de prix sans profondeur réelle, est peu fiable.

| Critère | Seuil | Lignes supprimées | Raison financière |
|---|---|---|---|
| Bid = 0 | — | 12 | Aucun acheteur : le prix reflète une fourchette artificielle, pas un consensus de marché |
| Spread relatif `(Ask−Bid)/Ask` | > 50% | 3 | Fourchette trop large : l'IV peut varier du simple au double selon le côté utilisé |
| Volume = 0 ET Open Interest | < 10 | 0 | Contrat fantôme sans activité ni position ouverte |

**153 options initiales → 138 conservées.** Les options exclues sont presque toutes des deep OTM à DTM court (strike ≥ 225 $ avec DTM = 1 ou 6), qui affichaient des IV de 52 % à 88 % — valeurs aberrantes par rapport aux strikes voisins à ~40–50 %.

### Interpolation : griddata (triangulation de Delaunay)

L'approche retenue est `scipy.interpolate.griddata`, qui accepte des **données non-régulières** (scattered data), contrairement à une spline bivariée qui exige une grille rectangulaire. Avec 7 DTM inégalement espacés et des strikes différents selon les maturités, forcer une grille rectangulaire via `pivot_table + dropna` réduisait de 34 à 5 le nombre de strikes utilisables.

`griddata` construit une triangulation de Delaunay sur les 138 points (DTM, Strike) et interpole l'IV sur une grille fine 80×80.

### Méthode cubic vs. méthode linear

Deux versions de la surface ont été générées et comparées.

#### `method="cubic"` — Clough-Tocher

Sur chaque triangle de Delaunay, un polynôme de degré 3 est ajusté avec continuité C¹ aux bords. L'interpolation est lisse et dérivable partout.

**Problème avec ces données :** les 7 valeurs de DTM sont très inégalement espacées (1, 6, 8, 10, 17, 24, 31 jours). La triangulation de Delaunay produit des triangles très allongés dans la direction DTM entre les maturités peu denses. Sur ces triangles pathologiques, le schéma Clough-Tocher amplifie les oscillations de manière non physique : la surface présente des pics et des creux artificiels (dents de scie) autour des DTM 5–15, alors que les données sources sont propres et l'IV varie en réalité de façon monotone.

**Conséquence financière :** une surface cubic sur données éparses peut suggérer des arbitrages inexistants — par exemple une IV qui remonte entre deux maturités alors qu'elle devrait décroître, ou un smile déformé qui fausserait un pricing par interpolation.

#### `method="linear"` — Interpolation barycentrique

Sur chaque triangle, l'IV est une combinaison linéaire convexe des trois sommets. Le résultat est **borné par construction** : impossible d'obtenir une valeur hors de l'intervalle des points observés sur un triangle donné.

**Avantage :** fidèle aux données même si visuellement moins lisse. Sur des données financières avec peu de points dans une dimension, linear est plus honnête : il ne prétend pas connaître le comportement de la surface là où les données sont rares.

**Inconvénient :** la surface est facettée (C⁰ mais pas C¹) — on voit les arêtes des triangles. Ce n'est pas un problème pour l'analyse visuelle, mais ce serait insuffisant pour un pricing qui requiert des dérivées de la surface (vega par rapport à la maturité, par exemple).

#### Résumé du choix

| | Cubic | Linear |
|---|---|---|
| Régularité | C¹ (dérivable) | C⁰ (continue) |
| Risque d'oscillation | Élevé sur triangles allongés | Nul (borné par les données) |
| Fidélité aux données | Peut s'en écarter | Garantie |
| Usage recommandé | Données denses et régulières | Données éparses ou irrégulières ✓ |

Pour ce dataset (7 DTM, espacement irrégulier), **`linear` est retenu** comme méthode de référence.

---

## Lecture financière de la surface

### Smile et skew de volatilité

La surface révèle deux phénomènes bien documentés en finance de marché :

**Volatility skew (axe strike) :** Pour une maturité donnée, l'IV est plus élevée sur les options out-of-the-money (strikes élevés) que sur les options at-the-money. Sur NVDA, l'IV passe d'environ 40–45 % à 180–190 $ (ATM) à 50–55 % à 220 $+ (OTM). Ce skew reflète la demande asymétrique de protection : les investisseurs achètent davantage de calls OTM sur NVDA pour participer à la hausse (exposition aux actualités IA), ce qui gonfle leur IV.

**Term structure (axe DTM) :** Pour un strike donné, l'IV diminue en général à mesure que la maturité augmente. Les options très court terme (DTM = 1 à 10) ont une IV structurellement plus élevée car elles encapsulent le risque d'événements précis imminents (résultats, annonces). À 31 jours, l'incertitude est diluée dans le temps et l'IV se normalise.

### Ce que la surface permet de faire

- **Pricing d'options exotiques :** une surface cohérente est la première entrée d'un modèle de valorisation (Heston, SVI, local vol). Un point interpolé sur la surface donne l'IV à utiliser pour pricer un contrat non listé.
- **Détection d'arbitrage :** une surface non monotone (IV qui remonte avec la maturité sur un strike donné) peut signaler une opportunité de calendar spread. C'est pourquoi la méthode d'interpolation doit être choisie avec soin : cubic sur données éparses peut créer des faux signaux.
- **Calibration de modèles :** les traders calibrent les paramètres de modèles stochastiques (vol de vol, corrélation) en minimisant l'écart entre la surface modèle et la surface de marché observée ici.

---

## Dépendances Python

```
numpy
pandas
matplotlib
scipy
```

Installation : `pip install numpy pandas matplotlib scipy`

## Compilation C++

```bash
# Depuis la racine du projet
g++ -std=c++17 -o cpp/interpolation cpp/interpolation.cpp
cd cpp && ./interpolation
```

## Utilisation Python

```bash
# Optionnel : régénérer le CSV propre depuis le xlsx
python python/clean_data.py

# Générer les surfaces de volatilité (sauvegardées dans output/)
python python/vol_surface.py
```
