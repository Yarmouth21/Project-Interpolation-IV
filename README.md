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
│   ├── vol_surface.py          # Filtrage qualité + visualisation de la surface
│   └── validate_surface.py     # Validation out-of-sample + benchmark de vitesse
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

**Vérification chiffrée :** l'IV observée sur les 138 options culmine à 72,0 %. La surface `cubic` monte jusqu'à **80,6 %** sur la grille interpolée, soit 8,6 points de volatilité au-dessus du maximum de marché, dans une zone où aucune option n'est cotée. La surface `linear` plafonne à 71,7 %, à l'intérieur des données par construction.

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

## Partie 3 — Validation quantitative de la surface

Une surface visuellement plausible n'est pas nécessairement fidèle. Pour mesurer la qualité de la reconstruction, chaque option est retirée du jeu d'entraînement, la surface est reconstruite sans elle, puis l'IV interpolée à ce point est comparée à l'IV de marché observée. Le filtrage qualité est appliqué **avant** le découpage, pour éviter toute fuite d'information.

Script : `python/validate_surface.py`

### Erreur out-of-sample

Référence : IV moyenne 45,7 %, dispersion 8,24 points de volatilité — c'est la variabilité que l'interpolation doit expliquer.

**Leave-one-out** (138 reconstructions, une par option) :

| Méthode | MAE | RMSE | R² | p95 | Max | Couverture |
|---|---|---|---|---|---|---|
| `griddata` **linear** | **1,13** pts de vol | 2,04 | 0,936 | 5,05 | 10,00 | 96 % |
| `griddata` **cubic** | 1,18 pts de vol | 1,89 | 0,945 | 5,07 | 6,94 | 96 % |
| Baseline : moyenne du smile par maturité | 5,88 pts de vol | 7,52 | 0,163 | 15,43 | 25,66 | 100 % |

**5-fold × 10 répétitions** (20 % des points retirés en bloc — test plus sévère, l'interpolation ne peut plus s'appuyer sur les voisins immédiats) :

| Méthode | MAE | RMSE | R² |
|---|---|---|---|
| `griddata` linear | 1,35 pts de vol | 2,32 | 0,917 |
| `griddata` cubic | 1,46 pts de vol | 2,35 | 0,915 |

La baseline est indispensable à la lecture du R² : sur une surface lisse, un R² élevé peut n'être qu'un artefact. Ici la baseline « moyenne du smile de la même maturité » plafonne à R² = 0,16, ce qui confirme que l'essentiel du signal capté vient bien de la structure en strike, pas de la seule term structure.

**Couverture 96 %** : environ 5 points, situés aux coins de l'enveloppe convexe, en sortent une fois retirés. `griddata` n'extrapole pas et renvoie `NaN` ; ces points sont exclus du calcul plutôt que comptés comme erreur nulle.

### Où se concentre l'erreur

Ventilation par zone de strike (leave-one-out, méthode linear) :

| Zone | n | MAE | RMSE |
|---|---|---|---|
| < 180 $ (ITM) | 23 | **3,61** | 4,50 |
| 180–200 $ (ATM) | 34 | 0,82 | 1,14 |
| 200–220 $ (OTM) | 38 | 0,46 | 0,64 |
| > 220 $ (deep OTM) | 38 | 0,57 | 0,86 |

L'erreur est très concentrée du côté ITM, là où le skew est le plus convexe : une interpolation linéaire par morceaux coupe la corde de la courbe et sous-estime systématiquement l'IV. Sur le cœur de la surface (ATM et OTM, 110 des 133 points évalués), l'écart tombe à **±0,5 à 0,8 point de volatilité**.

Par maturité, le comportement est homogène (MAE de 0,39 à 1,75 point de vol, le maximum étant à DTM = 8) : aucune maturité ne dégrade la surface à elle seule.

### Ordre de grandeur

Une MAE de 1,3 point de volatilité se compare aux 1 à 2 points d'écart d'IV induits par le spread bid-ask sur ces mêmes contrats. **L'erreur d'interpolation est du même ordre que le bruit du marché sous-jacent** — améliorer la méthode d'interpolation sans données plus profondes n'aurait donc guère de sens.

### Temps de calcul

Grille 80 × 80, soit 6 400 points interpolés, méthode linear :

| Approche | Temps | Par point |
|---|---|---|
| Surface complète (Delaunay construit une fois, évaluation vectorisée) | **1,4 ms** | 0,2 µs |
| Même interpolateur interrogé point par point en boucle Python | 18 ms | 2,8 µs |
| Chaînage de splines 1D par point (approche de la partie C++) | 3 060 ms | 479 µs |

Le coût de la surface complète se décompose en 1,3 ms de triangulation de Delaunay et 0,07 ms d'évaluation. Le gain vient donc de l'**amortissement de la structure géométrique** : elle est construite une seule fois pour les 6 400 points, alors que le chaînage de splines de la partie C++ réajuste 8 splines cubiques (7 en strike, 1 en DTM) à chaque requête.

### Limites

- Le dataset est un **snapshot** : 138 options, 7 maturités, une seule date de cotation (5 mai 2026). Les chiffres ci-dessus mesurent la cohérence interne de la surface à un instant donné, pas sa stabilité dans le temps.
- Le leave-one-out est optimiste sur des données denses : retirer un point entouré de ses voisins est un exercice facile. Le 5-fold à 20 % est la métrique à retenir.
- Le comparatif de vitesse oppose deux algorithmes distincts, il ne mesure pas une optimisation du même code.

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

# Reproduire les métriques de validation de la Partie 3
python python/validate_surface.py
```
