# Qualite des donnees

Genere le 08/09/2026 a 20:50 par `data/ingestion_pipeline/qualite.py`.

| # | Test | Mesure | Attendu | Verdict |
|---|------|--------|---------|---------|
| 1 | Unicite de la cle metier (annee, numero) | 0 doublon(s) | 0 | **OK** |
| 2 | Taux de geocodage (jointure INSEE reussie) | 99.31% | >= 97% | **OK** |
| 3 | Plage temporelle | 1973 - 2024 | 1973 - 2024 | **OK** |
| 4 | Aucune surface negative | 0 ligne(s) | 0 | **OK** |
| 5 | Surface foret <= surface parcourue | 0 ligne(s) (0.000%) | < 1 % | **OK** |
| 6 | Controle croise staging -> fires | 140246 brut distinct / 140246 charges | ecart < 0,1 % | **OK** |
