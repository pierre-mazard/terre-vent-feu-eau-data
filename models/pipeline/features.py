import numpy as np
import pandas as pd
from models.config_pipeline import ANNEE_DEBUT, ANNEE_FIN


def build_features(incendies: pd.DataFrame, communes: pd.DataFrame) -> pd.DataFrame:
    # ---------------------------------------------------------
    # 0. PANEL COMMUNES × ANNÉES
    # ---------------------------------------------------------
    annees = pd.DataFrame({"annee": range(ANNEE_DEBUT, ANNEE_FIN + 1)})
    communes_actives = communes[["code_insee"]].drop_duplicates()
    communes_actives["cle"] = 1
    annees["cle"] = 1

    panel = communes_actives.merge(annees, on="cle").drop(columns="cle")
    panel = panel.merge(communes, on="code_insee", how="left")

    # ---------------------------------------------------------
    # 1. Nettoyage incendies + dérivées
    # ---------------------------------------------------------
    inc = incendies.copy()

    # surfaces principales — CORRECTION ROBUSTE
    for col in [
        "surface_parcourue_ha",
        "surface_foret_ha",
        "surface_maquis_ha",
        "surface_autres_nat_ha",
        "surface_agricole_ha",
        "surface_autres_ha",
        "surface_autres_boisees_ha",
        "surface_non_boisees_nat_ha",
        "surface_non_boisees_art_ha",
    ]:
        if col in inc.columns:
            inc[col] = pd.to_numeric(inc[col], errors="coerce").fillna(0.0)
        else:
            inc[col] = 0.0

    # indicateurs de gravité — CORRECTION ROBUSTE
    for col in ["nb_deces", "nb_bat_detruits", "nb_bat_partiels"]:
        if col in inc.columns:
            inc[col] = pd.to_numeric(inc[col], errors="coerce").fillna(0)
        else:
            inc[col] = 0

    # été
    inc["est_ete"] = inc["mois"].isin([6, 7, 8, 9]).astype(int)

    # ---------------------------------------------------------
    # 1B. Détection automatique de l'identifiant de feu
    # ---------------------------------------------------------
    if "fire_id" in inc.columns:
        id_col = "fire_id"
    elif "numero" in inc.columns:
        id_col = "numero"
    else:
        inc["id_temp"] = np.arange(len(inc))
        id_col = "id_temp"

    # ---------------------------------------------------------
    # 2. Agrégations annuelles
    # ---------------------------------------------------------
    annuel = inc.groupby(["code_insee", "annee"], as_index=False).agg(
        nb_feux=(id_col, "size"),
        surface_ha=("surface_parcourue_ha", "sum"),
        surface_foret_ha=("surface_foret_ha", "sum"),
        surface_maquis_ha=("surface_maquis_ha", "sum"),
        surface_autres_nat_ha=("surface_autres_nat_ha", "sum"),
        surface_agricole_ha=("surface_agricole_ha", "sum"),
        surface_autres_ha=("surface_autres_ha", "sum"),
        surface_autres_boisees_ha=("surface_autres_boisees_ha", "sum"),
        surface_non_boisees_nat_ha=("surface_non_boisees_nat_ha", "sum"),
        surface_non_boisees_art_ha=("surface_non_boisees_art_ha", "sum"),
        surface_moyenne_ha=("surface_parcourue_ha", "mean"),
        feux_ete=("est_ete", "sum"),
        nb_deces=("nb_deces", "sum"),
        nb_bat_detruits=("nb_bat_detruits", "sum"),
        nb_bat_partiels=("nb_bat_partiels", "sum"),
    )

    panel = panel.merge(annuel, on=["code_insee", "annee"], how="left").fillna(0)
    panel = panel.sort_values(["code_insee", "annee"])

    # ---------------------------------------------------------
    # 3. Ratios et densités annuelles
    # ---------------------------------------------------------
    total_surface = (
        panel["surface_ha"]
        + panel["surface_foret_ha"]
        + panel["surface_maquis_ha"]
        + panel["surface_autres_nat_ha"]
        + panel["surface_agricole_ha"]
        + panel["surface_autres_ha"]
    )

    total_surface_safe = total_surface.replace(0, np.nan)

    panel["ratio_foret"] = (panel["surface_foret_ha"] / total_surface_safe).fillna(0)
    panel["ratio_agricole"] = (
        panel["surface_agricole_ha"] / total_surface_safe
    ).fillna(0)
    panel["ratio_maquis"] = (panel["surface_maquis_ha"] / total_surface_safe).fillna(0)
    panel["ratio_nat"] = (panel["surface_autres_nat_ha"] / total_surface_safe).fillna(0)
    panel["ratio_autres"] = (panel["surface_autres_ha"] / total_surface_safe).fillna(0)

    # densité de feux par km²
    panel["feux_par_km2"] = (
        panel["nb_feux"] / panel["superficie_km2"].replace(0, np.nan)
    ).fillna(0)

    # intensité moyenne par feu
    panel["surface_par_feu_ha"] = (
        panel["surface_ha"] / panel["nb_feux"].replace(0, np.nan)
    ).fillna(0)

    # gravité
    panel["batiments_touches"] = panel["nb_bat_detruits"] + panel["nb_bat_partiels"]
    panel["gravite_score"] = (
        panel["nb_deces"] * 10
        + panel["nb_bat_detruits"] * 3
        + panel["nb_bat_partiels"] * 1
    )

    # ---------------------------------------------------------
    # 4. Features temporelles (vectoriel)
    # ---------------------------------------------------------
    groupe = panel.groupby("code_insee")

    def roll(col, window, op="sum"):
        s = groupe[col].rolling(window, min_periods=1)
        if op == "sum":
            r = s.sum()
        elif op == "mean":
            r = s.mean()
        else:
            raise ValueError(f"op inconnu: {op}")
        return r.shift(1).reset_index(level=0, drop=True)

    panel["nb_feux_5a"] = roll("nb_feux", 5)
    panel["surface_5a_ha"] = roll("surface_ha", 5)
    panel["surface_foret_5a_ha"] = roll("surface_foret_ha", 5)
    panel["nb_feux_10a"] = roll("nb_feux", 10)
    panel["surface_10a_ha"] = roll("surface_ha", 10)
    panel["surface_moyenne_5a_ha"] = roll("surface_moyenne_ha", 5, op="mean")

    panel["part_feux_ete_5a"] = (
        roll("feux_ete", 5) / panel["nb_feux_5a"].replace(0, np.nan)
    ).fillna(0)

    # ---------------------------------------------------------
    # 5. Features mensuelles (mois dominant)
    # ---------------------------------------------------------
    mensuel = inc.groupby(["code_insee", "annee", "mois"]).size().unstack(fill_value=0)

    for m in range(1, 13):
        if m not in mensuel.columns:
            mensuel[m] = 0

    mensuel = mensuel.reset_index()

    mensuel["mois_reference"] = (
        mensuel[list(range(1, 13))].fillna(0).idxmax(axis=1).astype(int)
    )

    panel = panel.merge(
        mensuel[["code_insee", "annee", "mois_reference"]],
        on=["code_insee", "annee"],
        how="left",
    )

    panel["mois_reference"] = panel["mois_reference"].fillna(8)
    panel["mois_sin"] = np.sin(2 * np.pi * panel["mois_reference"] / 12)
    panel["mois_cos"] = np.cos(2 * np.pi * panel["mois_reference"] / 12)

    # ---------------------------------------------------------
    # 6. Cible : incendie l'année suivante
    # ---------------------------------------------------------
    panel["feux_annee_suivante"] = groupe["nb_feux"].shift(-1).fillna(0)
    panel["cible_incendie_suivant"] = (panel["feux_annee_suivante"] > 0).astype(int)

    return panel
