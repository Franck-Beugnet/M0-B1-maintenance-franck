import pandas as pd

df = pd.read_csv(r"C:\data\sources\ia\M0-B1-maintenance-franck\data\maintenance_data.csv")

print("=== Distribution criticité ===")
print(df["criticite"].value_counts())
print(df["criticite"].value_counts(normalize=True).round(2))

print("\n=== Stats par criticité ===")
cols = ["age_machine_jours", "derniere_maintenance_jours", "temperature_moyenne", "vibration_moyenne", "pression_moyenne", "nb_incidents_3_mois"]
print(df.groupby("criticite")[cols].mean().round(1))

print("\n=== Min/Max globaux ===")
print(df[cols].agg(["min","max"]).round(1))

print("\n=== Type machine x criticité ===")
print(pd.crosstab(df["type_machine"], df["criticite"]))
