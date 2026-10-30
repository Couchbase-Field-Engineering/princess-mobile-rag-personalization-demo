# Databricks notebook source
# MAGIC %md
# MAGIC # Guest personalization - daily export for the mobile app
# MAGIC
# MAGIC Runs every morning (see `../jobs/guest_personalization_daily_export.job.json`, 05:00 America/New_York).
# MAGIC
# MAGIC 1. Join upcoming reservations with Guest 360 (loyalty, preferences, sailing history, onboard spend).
# MAGIC 2. Score every passenger with the registered personalization model (`pcl-personalization`, alias `champion`).
# MAGIC 3. Write the Delta table `pcl_prod.guest360.passenger_reservation_personalization`.
# MAGIC 4. Export the same rows as JSON Lines to a Unity Catalog volume partitioned by `dt=`,
# MAGIC    with `_SUCCESS` and `_manifest.json` - the drop the demo backend's loader picks up and
# MAGIC    publishes to Couchbase (operational + Couchbase Lite sync) and the AOM Knowledge Base.
# MAGIC
# MAGIC In this repo the same output is produced locally by `databricks/generate_mock_dump.py`
# MAGIC (mock data, identical schema), so the demo runs without a Databricks workspace.

# COMMAND ----------

dbutils.widgets.text("catalog", "pcl_prod")
dbutils.widgets.text("schema", "guest360")
dbutils.widgets.text("export_volume", "/Volumes/pcl_prod/guest360/exports/passenger_reservation_personalization")
dbutils.widgets.text("horizon_days", "150")
dbutils.widgets.text("num_files", "4")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
EXPORT = dbutils.widgets.get("export_volume")
HORIZON = int(dbutils.widgets.get("horizon_days"))
NUM_FILES = int(dbutils.widgets.get("num_files"))
SCHEMA_VERSION = "guest_personalization_v3"

import datetime as dt
import json

from pyspark.sql import functions as F
from pyspark.sql import Window

export_date = dt.date.today().isoformat()
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------
# MAGIC %md ## 1. Upcoming passenger reservations + Guest 360

# COMMAND ----------

res = (
    spark.table("reservations_current")
    .where(F.col("booking_status") == "Confirmed")
    .where(F.col("embark_date").between(F.current_date(), F.date_add(F.current_date(), HORIZON)))
)
sailings = spark.table("sailings").select(
    "sailing_id", "ship_code", "ship_name", "itinerary_code", "itinerary_name", "nights",
    "embark_port_code", "embark_port", "embark_date", "debark_date",
    F.col("port_days").alias("ports"),  # array<struct<day,date,port_code,port,arrive,depart,type>>
)
party = (
    spark.table("reservation_passengers")
    .groupBy("booking_id")
    .agg(F.collect_list(F.struct("guest_id", F.concat_ws(" ", "first_name", "last_name").alias("name"),
                                 "age_band", "relationship")).alias("party"))
)
guests = spark.table("guest_profile")          # names, contact, home city, language, consent
loyalty = spark.table("captains_circle_status")   # tier, points, cruises_completed, member_since
prefs = spark.table("guest_preferences")       # interests[], dietary[], celebration, bed, pillow, ...
history = (
    spark.table("sailing_history")
    .withColumn("rn", F.row_number().over(Window.partitionBy("guest_id").orderBy(F.desc("sail_date"))))
    .where("rn <= 12")
    .groupBy("guest_id")
    .agg(F.collect_list(F.struct("ship_code", "ship_name", "sail_date", "nights", "cabin_class",
                                 "onboard_spend_usd", "excursions_booked", "specialty_dining_nights", "nps"))
         .alias("past_sailings"),
         F.avg("onboard_spend_usd").alias("avg_onboard_spend_usd"))
)
spend_mix = spark.table("onboard_spend_mix_12m")   # beverage, dining, excursions, spa, casino, retail shares
purchased = spark.table("presail_purchases")       # packages[], excursions[], dining[], spa[] per guest & sailing

base = (
    res.join(sailings, "sailing_id").join(party, "booking_id")
    .join(guests, "guest_id").join(loyalty, "guest_id")
    .join(prefs, "guest_id", "left").join(history, "guest_id", "left")
    .join(spend_mix, "guest_id", "left").join(purchased, ["guest_id", "sailing_id"], "left")
    .where(F.col("consent.personalization_opt_in"))
)

# COMMAND ----------
# MAGIC %md ## 2. Score with the personalization model

# COMMAND ----------

import mlflow

mlflow.set_registry_uri("databricks-uc")
model_uri = f"models:/{CATALOG}.ml.pcl_personalization@champion"
score_udf = mlflow.pyfunc.spark_udf(spark, model_uri, result_type="string")  # returns JSON of ml_scores
model_version = mlflow.MlflowClient().get_model_version_by_alias(f"{CATALOG}.ml.pcl_personalization", "champion").version

feature_cols = [c for c in base.columns if c not in ("first_name", "last_name", "email")]
scored = base.withColumn("ml_scores_json", score_udf(F.struct(*feature_cols)))

# COMMAND ----------
# MAGIC %md ## 3. Shape to the export schema and write Delta

# COMMAND ----------

ml_schema = ("struct<model_version:string,scored_at:string,upgrade_propensity:double,price_sensitivity:double,"
             "beverage_package_propensity:double,specialty_dining_propensity:double,excursion_propensity:double,"
             "spa_propensity:double,wifi_propensity:double,premier_propensity:double,casino_propensity:double,"
             "churn_risk:double,predicted_onboard_spend_usd:double,recommended_upgrade_category:string,"
             "recommended_bid_per_night_usd:int,segment:string,next_best_action:string>")

out = scored.select(
    F.lit(export_date).alias("export_date"),
    F.lit(SCHEMA_VERSION).alias("schema_version"),
    "guest_id", "captains_circle_number", "first_name", "last_name", "email", "age_band",
    "home_city", "home_state", "home_country", "preferred_language",
    F.struct(F.lit("Captain's Circle").alias("program"), "tier", "points", "cruises_completed",
             "member_since").alias("loyalty"),
    F.struct("booking_id", "booking_status", "booked_date", "booking_channel", "lead_guest",
             "sailing_id", "ship_code", "ship_name", "itinerary_code", "itinerary_name", "nights",
             "embark_port_code", "embark_port", "embark_date", "debark_date", "ports",
             F.datediff("embark_date", F.current_date()).alias("days_to_sail"),
             F.size("party").alias("party_size"), "party", "stateroom", "fare_paid_usd", "balance_due_usd",
             "checkin_status", "arrival_slot", "dining_assignment").alias("reservation"),
    F.struct("interests", "dietary", "celebration", "bed_configuration", "pillow", "stateroom_location_pref",
             "communication_channel", "travels_with_kids").alias("preferences"),
    F.struct("past_sailings", "avg_onboard_spend_usd", "lifetime_value_usd", "upgrades_accepted",
             "upgrade_bids_placed", "last_nps").alias("history"),
    F.struct("beverage", "dining", "excursions", "spa", "casino", "retail").alias("onboard_spend_mix"),
    F.struct("packages", "excursions", "dining", "spa").alias("purchased_for_sailing"),
    F.from_json("ml_scores_json", ml_schema).alias("ml_scores"),
    "consent",
    F.struct(F.lit(f"{CATALOG}.{SCHEMA}.passenger_reservation_personalization").alias("source_table"),
             F.lit("guest_personalization_daily_export").alias("pipeline"),
             F.lit(spark.conf.get("spark.databricks.clusterUsageTags.sparkVersion", "")).alias("dbr_version"))
    .alias("_ingest"),
)

(out.write.format("delta").mode("overwrite").option("replaceWhere", f"export_date = '{export_date}'")
    .partitionBy("export_date").saveAsTable("passenger_reservation_personalization"))

# COMMAND ----------
# MAGIC %md ## 4. Export JSON Lines for the app (dt= partition + _SUCCESS + _manifest.json)

# COMMAND ----------

path = f"{EXPORT}/dt={export_date}"
daily = spark.table("passenger_reservation_personalization").where(F.col("export_date") == export_date)
daily.repartition(NUM_FILES).write.mode("overwrite").json(path)   # Spark writes part-*.json + _SUCCESS

files = [f for f in dbutils.fs.ls(path) if f.name.startswith("part-")]
manifest = {
    "table": f"{CATALOG}.{SCHEMA}.passenger_reservation_personalization",
    "export_date": export_date, "schema_version": SCHEMA_VERSION,
    "model_version": f"pcl-personalization-v{model_version}", "format": "jsonl",
    "rows": daily.count(), "bookings": daily.select("reservation.booking_id").distinct().count(),
    "bytes": sum(f.size for f in files), "files": [{"file": f.name, "bytes": f.size} for f in files],
}
dbutils.fs.put(f"{path}/_manifest.json", json.dumps(manifest, indent=2), overwrite=True)
print(json.dumps(manifest, indent=2))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Delivery to the demo backend
# MAGIC The backend watches `DUMP_DIR` for a newer `dt=*/_SUCCESS`. Point it at wherever this volume lands:
# MAGIC * copy it down: `databricks fs cp -r dbfs:/Volumes/.../dt=<date> ./data/databricks-dump/dt=<date>`
# MAGIC * or mount the cloud storage location behind the volume into the backend container at `/data/databricks-dump`.
